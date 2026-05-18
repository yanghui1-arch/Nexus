from __future__ import annotations

import shlex
import uuid
from dataclasses import dataclass
from typing import Callable

from mwin import track

from src.logger import logger
from src.sandbox import Sandbox
from src.server.postgres.database import Database
from src.server.postgres.models import TaskWorkItemStatus
from src.server.postgres.repositories import (
    TaskWorkItemRepository,
)


@dataclass
class NexusTaskContext:
    task_id: uuid.UUID
    database: Database
    repo: str
    current_work_item_id: uuid.UUID | None = None

    @property
    def default_local_path(self) -> str:
        repo_name = self.repo.rsplit("/", 1)[-1] if self.repo else "repo"
        return f"/workspace/{repo_name}"


def _quote_git_command(local_path: str, *args: str) -> str:
    return " ".join(["git", "-C", shlex.quote(local_path), *(shlex.quote(arg) for arg in args)])


async def _git_stdout(sandbox: Sandbox, local_path: str, *args: str) -> str:
    result = await sandbox.run_shell(_quote_git_command(local_path, *args))
    if not result or not result.get("success", False):
        stderr = result.get("stderr", "") if result else "git command failed"
        stdout = result.get("stdout", "") if result else ""
        detail = stderr or stdout or "git command failed"
        raise RuntimeError(detail.strip())
    return result.get("stdout", "").strip()


class NexusReviewTools:
    def __init__(self, sandbox: Sandbox, context: NexusTaskContext | None) -> None:
        self._sandbox = sandbox
        self._context = context

    @track(step_type="tool")
    async def create_task_work_items(self, items: list[dict[str, str]]) -> dict:
        if self._context is None:
            return {"success": False, "message": "Nexus task context is not available."}

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

        logger.info("Task %s has %s Nexus work items.", self._context.task_id, len(records))
        return {
            "success": True,
            "count": len(records),
            "message": "Nexus persisted the work items for this task.",
        }

    @track(step_type="tool")
    async def finish_current_task_work_item(
        self,
        summary: str,
        local_path: str | None = None,
    ) -> dict:
        if self._context is None or self._context.current_work_item_id is None:
            return {"success": False, "message": "No current Nexus work item is assigned."}

        summary = summary.strip()
        if not summary:
            return {"success": False, "message": "summary is required."}

        async with self._context.database.session() as session:
            work_item = await TaskWorkItemRepository.get(
                session,
                self._context.current_work_item_id,
            )

        if work_item is None or work_item.task_id != self._context.task_id:
            return {"success": False, "message": "Current Nexus work item was not found."}
        if work_item.status != TaskWorkItemStatus.running:
            return {"success": False, "message": f"Current work item is {work_item.status.value}."}

        repo_path = local_path or work_item.local_path or self._context.default_local_path
        try:
            dirty_status = await _git_stdout(self._sandbox, repo_path, "status", "--porcelain")
            if dirty_status:
                return {"success": False, "message": "Commit or clean changes before finishing."}

            head_commit = await _git_stdout(self._sandbox, repo_path, "rev-parse", "HEAD")
            base_commit = work_item.base_commit or await _infer_base_commit(self._sandbox, repo_path)
        except RuntimeError as exc:
            return {"success": False, "message": f"Failed to capture work item review scope: {exc}"}

        async with self._context.database.session() as session:
            await TaskWorkItemRepository.mark_ready_for_review(
                session,
                work_item.id,
                summary=summary,
                base_commit=base_commit,
                head_commit=head_commit,
                local_path=repo_path,
            )

        logger.info(
            "Task %s work item %s is ready for review.",
            self._context.task_id,
            work_item.order_index,
        )
        return {
            "success": True,
            "status": "ready_for_review",
            "message": "Nexus marked the work item ready for review.",
        }

    @property
    def all_tools(self) -> dict[str, Callable]:
        return {
            "create_task_work_items": self.create_task_work_items,
            "finish_current_task_work_item": self.finish_current_task_work_item,
        }


async def _infer_base_commit(sandbox: Sandbox, local_path: str) -> str:
    for args in (
        ("merge-base", "HEAD", "origin/main"),
        ("merge-base", "HEAD", "origin/master"),
        ("rev-parse", "HEAD^"),
    ):
        try:
            return await _git_stdout(sandbox, local_path, *args)
        except RuntimeError:
            continue
    raise RuntimeError("Unable to infer base commit for the work item review scope.")
