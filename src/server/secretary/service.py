from __future__ import annotations

import uuid
from dataclasses import dataclass

from src.logger import logger
from src.server.config import Settings
from src.server.postgres.database import Database
from src.server.postgres.models import AgentName, TaskCategory, TaskStatus
from src.server.postgres.repositories import (
    SecretaryStateRepository,
    TaskRepository,
    WorkspaceRepository,
)
from src.server.runner import AgentTaskRunner
from src.server.schemas import AgentKind, TaskCreateRequest

from .github import GithubSecretaryClient


@dataclass(frozen=True)
class ReviewTaskDispatchResult:
    """Result of dispatching a PR review task."""

    repo: str
    pull_number: int
    pull_request_url: str
    task_id: uuid.UUID | None
    created: bool
    message: str


class SecretaryService:
    """Discovers PRs and dispatches Assistant review tasks."""

    def __init__(
        self,
        *,
        settings: Settings,
        database: Database,
        runner: AgentTaskRunner | None = None,
        github_client: GithubSecretaryClient | None = None,
    ) -> None:
        """Initialize the service."""
        self._settings = settings
        self._database = database
        self._runner = runner
        github_token = getattr(settings, "secretary_github_token", None)
        self._github = github_client or (
            GithubSecretaryClient(github_token)
            if github_token
            else None
        )

    @property
    def enabled(self) -> bool:
        """Return whether scheduled PR discovery can run."""
        return bool(
            getattr(self._settings, "secretary_enabled", False)
            and getattr(self._settings, "secretary_github_token", None)
        )

    async def scan_all(self) -> int:
        """Scan repositories bound to active Assistant workspaces and queue review tasks."""
        async with self._database.session() as session:
            workspaces = await WorkspaceRepository.list_active_for_agent(
                session,
                agent=AgentName.assistant,
            )
        repos = sorted({workspace.github_repo for workspace in workspaces if workspace.github_repo})
        return await self.scan_repos(repos)

    async def scan_repos(self, repos: list[str]) -> int:
        """Queue review tasks for open PRs in the provided repositories."""
        if not self.enabled or self._github is None:
            return 0
        queued = 0
        for repo in repos:
            pulls = await self._github.list_open_pull_requests(repo)
            for pull in pulls:
                if pull.draft:
                    continue
                try:
                    result = await self.review_one(
                        repo,
                        pull.number,
                        pull_request_url=pull.html_url,
                        head_sha=pull.head_sha,
                        force=False,
                        source="scheduled scan",
                    )
                except Exception as exc:
                    logger.exception("Secretary failed to queue review for %s#%s: %s", repo, pull.number, str(exc))
                    continue
                if result.created:
                    queued += 1
        return queued

    async def review_one(
        self,
        repo: str,
        pull_number: int,
        *,
        pull_request_url: str | None = None,
        head_sha: str | None = None,
        force: bool = False,
        source: str = "manual",
    ) -> ReviewTaskDispatchResult:
        """Queue one Assistant review task for a pull request."""
        if self._runner is None:
            raise RuntimeError("Secretary service needs an AgentTaskRunner to dispatch review tasks.")

        normalized_repo = repo.strip()
        pr_url = pull_request_url or f"https://github.com/{normalized_repo}/pull/{pull_number}"
        workspace = await self._workspace_for_repo(normalized_repo)
        if workspace is None:
            raise RuntimeError(f"No active Assistant workspace is bound to {normalized_repo}.")

        if not force and head_sha:
            dedupe_key = _dispatch_dedupe_key(normalized_repo, pull_number, head_sha)
            async with self._database.session() as session:
                existing_task_id = await SecretaryStateRepository.get(session, dedupe_key)
            if existing_task_id:
                return ReviewTaskDispatchResult(
                    repo=normalized_repo,
                    pull_number=pull_number,
                    pull_request_url=pr_url,
                    task_id=uuid.UUID(existing_task_id),
                    created=False,
                    message="Review task already dispatched for this PR head.",
                )

        if not force:
            async with self._database.session() as session:
                existing_task = await TaskRepository.get_latest_by_external_pull_request_url(
                    session,
                    agent_instance_id=workspace.agent_instance_id,
                    external_pull_request_url=pr_url,
                    category=TaskCategory.review,
                )
            if existing_task is not None and existing_task.status in {TaskStatus.queued, TaskStatus.running}:
                return ReviewTaskDispatchResult(
                    repo=normalized_repo,
                    pull_number=pull_number,
                    pull_request_url=pr_url,
                    task_id=existing_task.id,
                    created=False,
                    message="Review task is already queued or running for this PR.",
                )

        task_id = await self._runner.submit_task(
            TaskCreateRequest(
                agent_instance_id=workspace.agent_instance_id,
                agent=AgentKind.assistant,
                question=_build_review_prompt(
                    repo=normalized_repo,
                    pull_number=pull_number,
                    pull_request_url=pr_url,
                    head_sha=head_sha,
                    source=source,
                    discord_reply=source == "discord command",
                ),
                external_pull_request_url=pr_url,
            )
        )

        if head_sha:
            async with self._database.session() as session:
                await SecretaryStateRepository.set(
                    session,
                    key=_dispatch_dedupe_key(normalized_repo, pull_number, head_sha),
                    value=str(task_id),
                )

        return ReviewTaskDispatchResult(
            repo=normalized_repo,
            pull_number=pull_number,
            pull_request_url=pr_url,
            task_id=task_id,
            created=True,
            message="Review task queued.",
        )

    async def latest_status(self, repo: str, pull_number: int):
        """Return the latest Assistant review task for one PR."""
        pr_url = f"https://github.com/{repo.strip()}/pull/{pull_number}"
        async with self._database.session() as session:
            return await TaskRepository.get_latest_by_external_pull_request_url(
                session,
                external_pull_request_url=pr_url,
                category=TaskCategory.review,
            )

    async def _workspace_for_repo(self, repo: str):
        """Return the first active Assistant workspace bound to a repository."""
        async with self._database.session() as session:
            workspaces = await WorkspaceRepository.list_active_for_agent(
                session,
                agent=AgentName.assistant,
            )
        for workspace in workspaces:
            if workspace.github_repo == repo:
                return workspace
        return None


def _dispatch_dedupe_key(repo: str, pull_number: int, head_sha: str) -> str:
    """Build a stable dispatch dedupe key for one PR head."""
    return f"secretary:review-task:{repo}#{pull_number}:{head_sha}"


def _build_review_prompt(
    *,
    repo: str,
    pull_number: int,
    pull_request_url: str,
    head_sha: str | None,
    source: str,
    discord_reply: bool,
) -> str:
    """Build the Assistant task prompt for one PR review."""
    lines = [
        f"Review pull request {repo}#{pull_number}.",
        f"PR URL: {pull_request_url}",
        f"Trigger source: {source}",
    ]
    if head_sha:
        lines.append(f"Expected head SHA from dispatch: {head_sha}")
    lines.extend(
        [
            "",
            "Run the Assistant PR review workflow from your system prompt.",
            "Use the configured GitHub token for all GitHub API calls.",
            "Run the configured test commands for this repository before approving or merging.",
            "Submit a formal GitHub review, then merge only if the conservative gate is satisfied.",
            "Do not DM normal merges, merge conflicts, routine CI failures, or missing test configuration.",
        ]
    )
    if discord_reply:
        lines.append("This was explicitly requested through Discord; send one concise DM when finished.")
    return "\n".join(lines)
