from __future__ import annotations

import re
import shlex
import uuid
from dataclasses import dataclass
from typing import Callable

import httpx
from mwin import track

from src.logger import logger
from src.sandbox import Sandbox
from src.server.postgres.database import Database
from src.server.postgres.models import TaskWorkItemStatus
from src.server.postgres.repositories import (
    TaskRepository,
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
        """Return the default local repository path."""
        repo_name = self.repo.rsplit("/", 1)[-1] if self.repo else "repo"
        return f"/workspace/{repo_name}"


def _quote_git_command(local_path: str, *args: str) -> str:
    """Quote a command for git output."""
    return " ".join(["git", "-C", shlex.quote(local_path), *(shlex.quote(arg) for arg in args)])


async def _git_stdout(sandbox: Sandbox, local_path: str, *args: str) -> str:
    """Return stdout from a git command."""
    result = await sandbox.run_shell(_quote_git_command(local_path, *args))
    if not result or not result.get("success", False):
        stderr = result.get("stderr", "") if result else "git command failed"
        stdout = result.get("stdout", "") if result else ""
        detail = stderr or stdout or "git command failed"
        raise RuntimeError(detail.strip())
    return result.get("stdout", "").strip()


class NexusReviewTools:
    def __init__(self, sandbox: Sandbox, context: NexusTaskContext | None) -> None:
        """Initialize the object."""
        self._sandbox = sandbox
        self._context = context

    @track(step_type="tool")
    async def create_task_work_items(self, items: list[dict[str, str]]) -> dict:
        """Create Nexus task work items."""
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
        """Finish the current Nexus work item."""
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

    @track(step_type="tool")
    async def bind_pr_to_task(
        self,
        token: str,
        pull_request_url: str,
    ) -> dict:
        """Bind an existing GitHub pull request to the current Nexus task.

        Args:
            token: GitHub personal access token used to verify that the pull request
                exists before Nexus persists the binding.
            pull_request_url: Existing GitHub pull request URL that should be
                attached to the current Nexus task.

        Returns:
            A result dictionary containing:
                - success: Whether the binding succeeded.
                - pr_url: The persisted pull request URL when binding succeeds.
                - message: A human-readable status or error message.
        """
        if self._context is None:
            return {"success": False, "pr_url": "", "message": "Nexus task context is not available."}
        if not token:
            return {"success": False, "pr_url": "", "message": "token is required."}
        if not pull_request_url:
            return {"success": False, "pr_url": "", "message": "pull_request_url is required."}

        async with self._context.database.session() as session:
            task = await TaskRepository.get(session, self._context.task_id)
        if task is None:
            return {"success": False, "pr_url": "", "message": "Current Nexus task was not found."}
        if task.external_pull_request_url:
            return {
                "success": False,
                "pr_url": task.external_pull_request_url,
                "message": (
                    f"Current Nexus task is already bound to pull request "
                    f"{task.external_pull_request_url}. Do not call bind_pr_to_task again."
                ),
            }

        match = re.match(
            r"^https?://(?:www\.)?github\.com/(?P<repo>[^/\s]+/[^/\s]+)/pull/(?P<number>\d+)(?:[/?#].*)?$",
            pull_request_url,
            re.IGNORECASE,
        )
        if match is None:
            return {
                "success": False,
                "pr_url": "",
                "message": "pull_request_url must match https://github.com/<owner>/<repo>/pull/<number>.",
            }

        repo = match.group("repo")
        if repo.casefold() != self._context.repo.casefold():
            return {
                "success": False,
                "pr_url": "",
                "message": f"pull request repo {repo} does not match current task repo {self._context.repo}.",
            }

        pull_number = int(match.group("number"))
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"https://api.github.com/repos/{repo}/pulls/{pull_number}",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28",
                    },
                )
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                error_detail = e.response.json().get("message", e.response.text)
                return {
                    "success": False,
                    "pr_url": "",
                    "message": f"GitHub API error {e.response.status_code}: {error_detail}. Please retry it.",
                }

        data = response.json()
        pr_url = data.get("html_url", f"https://github.com/{repo}/pull/{pull_number}")
        async with self._context.database.session() as session:
            task = await TaskRepository.set_external_pull_request_url(
                session,
                self._context.task_id,
                external_pull_request_url=pr_url,
            )
        if task is None:
            return {"success": False, "pr_url": "", "message": "Current Nexus task was not found."}

        logger.info("Task %s bound to GitHub pull request %s.", self._context.task_id, pr_url)
        return {
            "success": True,
            "pr_url": pr_url,
            "message": f"Nexus bound the current task to pull request {pr_url}.",
        }

    @property
    def all_tools(self) -> dict[str, Callable]:
        """Return all tools exposed by this toolkit."""
        return {
            "create_task_work_items": self.create_task_work_items,
            "finish_current_task_work_item": self.finish_current_task_work_item,
            "bind_pr_to_task": self.bind_pr_to_task,
        }


async def _infer_base_commit(sandbox: Sandbox, local_path: str) -> str:
    """Infer the base commit for work-item review scope."""
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
