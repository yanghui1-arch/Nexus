from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import cast

import httpx

from src.logger import logger
from src.server.config import Settings
from src.server.postgres.database import Database
from src.server.postgres.models import AgentName, TaskCategory, TaskStatus, WorkspaceRecord
from src.server.postgres.repositories import (
    AssistantStateRepository,
    TaskRepository,
    WorkspaceRepository,
)
from src.server.runner import AgentTaskRunner
from src.server.schemas import AgentKind, TaskCreateRequest


GITHUB_API_BASE_URL = "https://api.github.com"
MAX_REVIEW_TASKS_PER_WORKSPACE_SCAN = 3
OPEN_PR_SCAN_PAGE_SIZE = 100
OPEN_PR_SCAN_MAX_PAGES = 1


@dataclass(frozen=True)
class PullRequestSummary:
    """Minimal GitHub PR fields needed to dispatch an Assistant review."""

    repo: str
    number: int
    title: str
    state: str
    draft: bool
    html_url: str
    author: str | None
    created_at: str
    head_sha: str
    head_ref: str
    base_ref: str
    mergeable: bool | None = None
    mergeable_state: str | None = None


class AssistantService:
    """Discovers open PRs for active Assistant workspaces and dispatches review tasks."""

    def __init__(
        self,
        *,
        settings: Settings,
        database: Database,
        runner: AgentTaskRunner | None = None,
    ) -> None:
        self._settings = settings
        self._database = database
        self._runner = runner

    async def scan_all(self) -> int:
        """Scan every active Assistant workspace and queue review tasks for open PRs."""
        github_token = self._settings.assistant_github_token
        if not self._settings.assistant_enabled or not github_token:
            return 0
        if self._runner is None:
            raise RuntimeError("AssistantService requires AgentTaskRunner to dispatch review tasks.")

        async with self._database.session() as session:
            workspaces = await WorkspaceRepository.list_active_for_agent(
                session,
                agent=AgentName.assistant,
            )
        workspaces_by_repo: dict[str, list[WorkspaceRecord]] = {}
        # Key: Assistant agent_instance_id. Value: review tasks dispatched for
        # that Assistant workspace during this scan cycle.
        queued_by_workspace: dict[uuid.UUID, int] = {}
        for workspace in workspaces:
            repo = (workspace.github_repo or "").strip()
            if repo:
                workspaces_by_repo.setdefault(repo, []).append(workspace)
                queued_by_workspace[workspace.agent_instance_id] = 0

        # One repository may be shared by multiple Assistant workspaces. We fetch
        # each repo's oldest open PR page once, then try those PRs against every
        # bound workspace while tracking a separate per-workspace dispatch cap.
        queued = 0
        for repo in sorted(workspaces_by_repo):
            repo_workspaces = workspaces_by_repo[repo]
            try:
                open_pulls = await _list_open_pull_requests(github_token, repo)
            except Exception as exc:
                logger.exception("Assistant failed to list open pull requests for %s: %s", repo, str(exc))
                continue

            # Large repos can have thousands of open PRs. GitHub returns the oldest
            # page first, and this local sort keeps mocked/test data deterministic.
            pulls = sorted(
                (pull for pull in open_pulls if not pull.draft),
                key=lambda pull: (pull.created_at or "9999-12-31T23:59:59Z", pull.number),
            )
            for pull in pulls:
                if all(
                    queued_by_workspace[workspace.agent_instance_id] >= MAX_REVIEW_TASKS_PER_WORKSPACE_SCAN
                    for workspace in repo_workspaces
                ):
                    break
                for workspace in repo_workspaces:
                    if queued_by_workspace[workspace.agent_instance_id] >= MAX_REVIEW_TASKS_PER_WORKSPACE_SCAN:
                        continue
                    try:
                        if await self._queue_review_task(workspace=workspace, repo=repo, pull=pull):
                            queued_by_workspace[workspace.agent_instance_id] += 1
                            queued += 1
                    except Exception as exc:
                        logger.exception(
                            "Assistant failed to queue review for %s#%s in Assistant workspace %s: %s",
                            repo,
                            pull.number,
                            workspace.agent_instance_id,
                            str(exc),
                        )
        return queued

    async def _queue_review_task(
        self,
        *,
        workspace: WorkspaceRecord,
        repo: str,
        pull: PullRequestSummary,
    ) -> bool:
        runner = self._runner
        if runner is None:
            raise RuntimeError("AssistantService requires AgentTaskRunner to dispatch review tasks.")

        agent_instance_id = workspace.agent_instance_id
        pull_request_url = pull.html_url or f"https://github.com/{repo}/pull/{pull.number}"

        if pull.head_sha:
            dedupe_key = _dispatch_dedupe_key(agent_instance_id, repo, pull.number, pull.head_sha)
            async with self._database.session() as session:
                if await AssistantStateRepository.get(session, dedupe_key):
                    return False

        async with self._database.session() as session:
            existing_task = await TaskRepository.get_latest_by_external_pull_request_url(
                session,
                agent_instance_id=agent_instance_id,
                external_pull_request_url=pull_request_url,
                category=TaskCategory.review,
            )
        # Once a PR has an Assistant review task, scheduled scans stop creating
        # new tasks for it. GitHubFeedbackPoller owns follow-up comments/reviews.
        if existing_task is not None and existing_task.status in {
            TaskStatus.queued,
            TaskStatus.running,
            TaskStatus.waiting_for_review,
        }:
            return False

        task_id = await runner.submit_task(
            TaskCreateRequest(
                agent_instance_id=agent_instance_id,
                agent=AgentKind.assistant,
                question=_build_review_prompt(
                    repo=repo,
                    pull=pull,
                    pull_request_url=pull_request_url,
                ),
                external_pull_request_url=pull_request_url,
            )
        )

        if pull.head_sha:
            async with self._database.session() as session:
                await AssistantStateRepository.set(
                    session,
                    key=_dispatch_dedupe_key(agent_instance_id, repo, pull.number, pull.head_sha),
                    value=str(task_id),
                )

        return True


def _dispatch_dedupe_key(agent_instance_id: uuid.UUID, repo: str, pull_number: int, head_sha: str) -> str:
    return f"assistant:review-task:{agent_instance_id}:{repo}#{pull_number}:{head_sha}"


async def _list_open_pull_requests(
    token: str,
    repo: str,
    *,
    base_url: str = GITHUB_API_BASE_URL,
    timeout: float = 15.0,
    max_pages: int = OPEN_PR_SCAN_MAX_PAGES,
) -> list[PullRequestSummary]:
    items: list[dict[str, object]] = []
    page = 1
    async with httpx.AsyncClient(timeout=timeout) as client:
        while page <= max_pages:
            response = await client.get(
                f"{base_url}/repos/{repo}/pulls",
                headers=_github_headers(token),
                params={
                    "state": "open",
                    "sort": "created",
                    "direction": "asc",
                    "per_page": OPEN_PR_SCAN_PAGE_SIZE,
                    "page": page,
                },
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, list):
                break
            for item in payload:
                if isinstance(item, dict):
                    items.append({str(key): value for key, value in item.items()})
            if len(payload) < OPEN_PR_SCAN_PAGE_SIZE:
                break
            page += 1
    return [_format_pull_summary(repo, item) for item in items]


def _github_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _format_pull_summary(repo: str, payload: dict[str, object]) -> PullRequestSummary:
    head = cast(dict[str, object], payload["head"])
    base = cast(dict[str, object], payload["base"])
    user = cast(dict[str, object], payload["user"])
    author = user.get("login")
    mergeable_state = payload.get("mergeable_state")
    return PullRequestSummary(
        repo=repo,
        number=int(payload.get("number") or 0),
        title=str(payload.get("title") or ""),
        state=str(payload.get("state") or ""),
        draft=bool(payload.get("draft")),
        html_url=str(payload.get("html_url") or ""),
        author=str(author) if author else None,
        created_at=str(payload.get("created_at") or ""),
        head_sha=str(head.get("sha") or ""),
        head_ref=str(head.get("ref") or ""),
        base_ref=str(base.get("ref") or ""),
        mergeable=payload["mergeable"] if isinstance(payload.get("mergeable"), bool) else None,
        mergeable_state=str(mergeable_state) if mergeable_state else None,
    )


def _build_review_prompt(
    *,
    repo: str,
    pull: PullRequestSummary,
    pull_request_url: str,
) -> str:
    lines = [
        f"Review pull request {repo}#{pull.number}.",
        f"Title: {pull.title}",
        f"PR URL: {pull_request_url}",
        "Trigger source: scheduled scan",
    ]
    if pull.head_sha:
        lines.append(f"Expected head SHA from dispatch: {pull.head_sha}")
    lines.extend(
        [
            "",
            "Run the Assistant PR review workflow from your system prompt.",
            "Use the configured GitHub token for all GitHub API calls.",
            "Run the configured test commands for this repository before approving or merging.",
            "Submit a formal GitHub review, then merge only if the conservative gate is satisfied.",
        ]
    )
    return "\n".join(lines)
