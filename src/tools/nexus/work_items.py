from __future__ import annotations

from typing import Callable

from mwin import track
from openai import pydantic_function_tool
from pydantic import BaseModel, Field

from src.logger import logger
from src.sandbox import Sandbox
from src.server.postgres.models import TaskWorkItemStatus
from src.server.postgres.repositories import (
    TaskWorkItemRepository,
    VirtualPullRequestRepository,
)
from src.tools.nexus.context import NexusTaskContext
from src.tools.nexus.git import git_stdout, parse_numstat


class TaskWorkItemInput(BaseModel):
    title: str = Field(description="Short review-sized work item title")
    description: str = Field(description="Concrete implementation scope for this work item")


class CreateTaskWorkItems(BaseModel):
    """Create Nexus-owned internal work items for a large task.

    Provide ordered work items only. Nexus injects task identity from execution context.
    """

    items: list[TaskWorkItemInput] = Field(
        min_length=1,
        description="Ordered internal work items split from the original task",
    )


class FinishCurrentTaskWorkItem(BaseModel):
    """Finish the currently assigned Nexus work item and create its virtual PR."""

    summary: str = Field(description="Reviewer-facing summary of the implemented work item")
    local_path: str | None = Field(
        default=None,
        description="Local repository path. Defaults to the fetched repository path Nexus captured for this work item.",
    )


CREATE_TASK_WORK_ITEMS = pydantic_function_tool(
    CreateTaskWorkItems,
    name="create_task_work_items",
)
FINISH_CURRENT_TASK_WORK_ITEM = pydantic_function_tool(
    FinishCurrentTaskWorkItem,
    name="finish_current_task_work_item",
)

NEXUS_WORK_ITEM_TOOL_DEFINITIONS: list = [
    CREATE_TASK_WORK_ITEMS,
    FINISH_CURRENT_TASK_WORK_ITEM,
]


class NexusReviewTools:
    def __init__(self, sandbox: Sandbox, context: NexusTaskContext | None) -> None:
        self._sandbox = sandbox
        self._context = context

    @track(step_type="tool")
    async def create_task_work_items(self, items: list[dict[str, str]]) -> dict:
        if self._context is None:
            return {
                "success": False,
                "message": "Nexus task context is not available.",
            }

        normalized: list[dict[str, str]] = []
        for index, item in enumerate(items, start=1):
            title = (item.get("title") or "").strip()
            description = (item.get("description") or "").strip()
            if not title or not description:
                return {
                    "success": False,
                    "message": f"Work item {index} must include title and description.",
                }
            normalized.append({"title": title, "description": description})

        async with self._context.database.session() as session:
            records = await TaskWorkItemRepository.create_many(
                session,
                task_id=self._context.task_id,
                items=normalized,
            )

        logger.info(
            "Task %s has %s Nexus work items.",
            self._context.task_id,
            len(records),
        )
        return {
            "success": True,
            "count": len(records),
            "items": [
                {
                    "order_index": record.order_index,
                    "title": record.title,
                    "description": record.description,
                    "status": record.status.value,
                }
                for record in records
            ],
            "message": "Nexus persisted the work items for this task.",
        }

    @track(step_type="tool")
    async def finish_current_task_work_item(
        self,
        summary: str,
        local_path: str | None = None,
    ) -> dict:
        if self._context is None or self._context.current_work_item_id is None:
            return {
                "success": False,
                "message": "No current Nexus work item is assigned.",
            }

        summary = summary.strip()
        if not summary:
            return {
                "success": False,
                "message": "summary is required.",
            }

        async with self._context.database.session() as session:
            work_item = await TaskWorkItemRepository.get(
                session,
                self._context.current_work_item_id,
            )

        if work_item is None or work_item.task_id != self._context.task_id:
            return {
                "success": False,
                "message": "Current Nexus work item was not found for this task.",
            }
        if work_item.status != TaskWorkItemStatus.running:
            return {
                "success": False,
                "message": f"Current Nexus work item is {work_item.status.value}, not running.",
            }
        if not work_item.base_commit:
            return {
                "success": False,
                "message": "Missing base_commit. Fetch the repository before editing so Nexus can capture the base.",
            }

        repo_path = local_path or work_item.local_path or self._context.default_local_path
        try:
            dirty_status = await git_stdout(self._sandbox, repo_path, "status", "--porcelain")
            if dirty_status:
                return {
                    "success": False,
                    "message": "Repository has uncommitted changes. Commit or clean them before finishing the Nexus work item.",
                }
            head_commit = await git_stdout(self._sandbox, repo_path, "rev-parse", "HEAD")
            revision_range = f"{work_item.base_commit}..{head_commit}"
            numstat = await git_stdout(self._sandbox, repo_path, "diff", "--numstat", revision_range)
            diff = await git_stdout(self._sandbox, repo_path, "diff", revision_range)
        except RuntimeError as exc:
            return {
                "success": False,
                "message": f"Failed to capture git diff for Nexus virtual PR: {exc}",
            }

        changed_files, additions, deletions = parse_numstat(numstat)

        async with self._context.database.session() as session:
            virtual_pr = await VirtualPullRequestRepository.upsert_for_work_item(
                session,
                task_id=self._context.task_id,
                work_item_id=work_item.id,
                base_commit=work_item.base_commit,
                head_commit=head_commit,
                summary=summary,
                changed_files=changed_files,
                additions=additions,
                deletions=deletions,
                diff=diff,
            )
            await TaskWorkItemRepository.mark_ready_for_review(
                session,
                work_item.id,
                summary=summary,
                head_commit=head_commit,
            )

        logger.info(
            "Task %s work item %s produced virtual PR %s (%s files, +%s/-%s).",
            self._context.task_id,
            work_item.order_index,
            virtual_pr.id,
            len(changed_files),
            additions,
            deletions,
        )
        return {
            "success": True,
            "status": "ready_for_review",
            "changed_files": changed_files,
            "additions": additions,
            "deletions": deletions,
            "message": "Nexus created the virtual PR for the current work item.",
        }

    @property
    def all_tools(self) -> dict[str, Callable]:
        return {
            "create_task_work_items": self.create_task_work_items,
            "finish_current_task_work_item": self.finish_current_task_work_item,
        }
