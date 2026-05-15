from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx

from src.logger import logger
from src.server.config import Settings
from src.server.postgres.database import Database
from src.server.postgres.models import (
    GithubPullRequestFeedbackKind,
    GithubPullRequestFeedbackStatus,
    TaskRecord,
    TaskStatus,
)
from src.server.postgres.repositories import (
    GithubPullRequestFeedbackRepository,
    TaskRepository,
)
from src.server.runner import AgentTaskRunner


_PULL_REQUEST_NUMBER_RE = re.compile(r"/pull/(?P<number>\d+)")


@dataclass(frozen=True)
class _GithubFeedbackItem:
    kind: GithubPullRequestFeedbackKind
    external_id: int
    author: str | None
    body: str | None
    review_state: str | None
    file_path: str | None
    line: int | None
    original_line: int | None
    commit_id: str | None
    html_url: str | None
    created_at: datetime | None
    updated_at: datetime | None
    payload: dict[str, Any]


class GithubFeedbackPoller:
    """Background poller that syncs GitHub PR feedback back into an existing Nexus task.

    The poller does not create new TaskRecord rows. Instead, it persists discovered
    GitHub feedback, marks unhandled items as pending, and re-queues the original
    task so the worker can continue from task.checkpoint.
    """

    def __init__(
        self,
        *,
        settings: Settings,
        database: Database,
        runner: AgentTaskRunner,
    ) -> None:
        self._settings = settings
        self._database = database
        self._runner = runner
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task[Any] | None = None
        self._viewer_login_by_token: dict[str, str | None] = {}

    def start(self) -> None:
        if self._settings.github_feedback_poll_interval_seconds <= 0:
            logger.info("GitHub feedback poller is disabled.")
            return
        if self._task is not None:
            return
        self._task = asyncio.create_task(
            self._run_loop(),
            name="nexus-github-feedback-poller",
        )
        logger.info("Github feedback poller starts.")

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task is None:
            return
        await self._task
        self._task = None

    async def poll_once(self) -> int:
        # Scan only tasks that still point at an open external PR and can accept follow-up feedback.
        async with self._database.session() as session:
            tasks = await TaskRepository.list_external_pull_request_candidates(
                session,
                limit=self._settings.github_feedback_poll_task_limit,
            )

        if not tasks:
            return 0

        discovered_count = 0
        async with httpx.AsyncClient(
            timeout=self._settings.github_feedback_http_timeout_seconds,
        ) as client:
            for task in tasks:
                if self._stop_event.is_set():
                    break
                try:
                    discovered_count += await self._poll_task(client, task)
                except Exception as exce:
                    logger.exception(
                        "Failed to sync GitHub feedback for task %s: %s.",
                        task.id,
                        str(exce)
                    )
        return discovered_count

    async def _run_loop(self) -> None:
        # The loop is intentionally sleep-driven and runs as its own asyncio task so it
        # does not block FastAPI request handling or the main application event loop.
        while not self._stop_event.is_set():
            try:
                await self.poll_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("GitHub feedback poller iteration failed.")

            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self._settings.github_feedback_poll_interval_seconds,
                )
            except asyncio.TimeoutError:
                continue

    async def _poll_task(
        self,
        client: httpx.AsyncClient,
        task: TaskRecord,
    ) -> int:
        # A task can only participate in this flow if it already opened a real GitHub PR.
        if not task.repo or not task.external_pull_request_url:
            return 0

        pull_request_number = _extract_pull_request_number(task.external_pull_request_url)
        if pull_request_number is None:
            logger.warning(
                "Task %s has an unsupported pull request URL: %s",
                task.id,
                task.external_pull_request_url,
            )
            return 0

        token = self._settings.github_tokens.get(task.agent.value)
        if not token:
            logger.warning(
                "Task %s cannot sync GitHub feedback because agent %s has no GitHub token.",
                task.id,
                task.agent.value,
            )
            return 0

        pull_request = await self._fetch_pull_request(client, token, task.repo, pull_request_number)
        if not pull_request:
            return 0

        if task.status in {TaskStatus.waiting_for_review, TaskStatus.waiting_for_merge}:
            # Once a reviewable task is backed by a real GitHub PR, GitHub becomes the
            # source of truth for terminal PR outcomes:
            # - merged PR -> merged task
            # - closed but unmerged PR -> closed task
            #
            # We intentionally do not auto-manage intermediate review states here anymore.
            if pull_request.get("merged_at"):
                async with self._database.session() as session:
                    updated = await TaskRepository.set_merged(session, task.id)
                if updated is not None:
                    logger.info("Synced task %s review status from %s to merged.", task.id, task.status.value)
                return 0

            if pull_request.get("state") == "closed":
                async with self._database.session() as session:
                    updated = await TaskRepository.set_closed(session, task.id)
                if updated is not None:
                    logger.info("Synced task %s review status from %s to closed.", task.id, task.status.value)
                return 0

        if pull_request.get("state") != "open" or pull_request.get("merged_at"):
            return 0

        viewer_login = await self._resolve_viewer_login(client, token)
        feedback_items = await self._fetch_feedback_items(
            client,
            token,
            task.repo,
            pull_request_number,
        )

        discovered_count = 0
        async with self._database.session() as session:
            for item in feedback_items:
                # Persist every remote feedback item locally so we can deduplicate, recover
                # after restarts, and distinguish new feedback from already processed feedback.
                status, ignored_reason = _classify_feedback(item, viewer_login)
                _, created = await GithubPullRequestFeedbackRepository.upsert_discovered(
                    session,
                    task_id=task.id,
                    pull_request_number=pull_request_number,
                    kind=item.kind,
                    external_id=item.external_id,
                    status=status,
                    author=item.author,
                    body=item.body,
                    review_state=item.review_state,
                    file_path=item.file_path,
                    line=item.line,
                    original_line=item.original_line,
                    commit_id=item.commit_id,
                    html_url=item.html_url,
                    external_created_at=item.created_at,
                    external_updated_at=item.updated_at,
                    ignored_reason=ignored_reason,
                    payload=item.payload,
                )
                if created and status == GithubPullRequestFeedbackStatus.pending:
                    discovered_count += 1

            # Only wake the task up when the pending feedback is newer than the task's current
            # state. This prevents the poller from re-queueing the same already-answered
            # feedback on every poll iteration.
            has_pending_feedback = await GithubPullRequestFeedbackRepository.has_pending_newer_than(
                session,
                task.id,
                cutoff=task.updated_at,
            )

        if discovered_count > 0 or has_pending_feedback:
            # Re-dispatch the original task instead of creating a new task. This keeps the
            # conversation history continuous and prevents GitHub feedback from showing up
            # as a brand new code review task in the UI.
            dispatched = await self._runner.dispatch_github_feedback(task.id)
            if dispatched:
                logger.info(
                    "Queued task %s to process pending GitHub feedback for PR #%s.",
                    task.id,
                    pull_request_number,
                )

        return discovered_count
    async def _resolve_viewer_login(
        self,
        client: httpx.AsyncClient,
        token: str,
    ) -> str | None:
        # Cache the token owner login because we use it to ignore self-authored comments
        # and there is no value in hitting /user on every poll iteration.
        if token in self._viewer_login_by_token:
            return self._viewer_login_by_token[token]

        response = await client.get(
            "https://api.github.com/user",
            headers=_github_headers(token),
        )
        response.raise_for_status()
        payload = response.json()
        login = payload.get("login")
        resolved = login.strip() if isinstance(login, str) and login.strip() else None
        self._viewer_login_by_token[token] = resolved
        return resolved

    async def _fetch_pull_request(
        self,
        client: httpx.AsyncClient,
        token: str,
        repo: str,
        pull_request_number: int,
    ) -> dict[str, Any]:
        response = await client.get(
            f"https://api.github.com/repos/{repo}/pulls/{pull_request_number}",
            headers=_github_headers(token),
        )
        response.raise_for_status()
        return response.json()

    async def _fetch_feedback_items(
        self,
        client: httpx.AsyncClient,
        token: str,
        repo: str,
        pull_request_number: int,
    ) -> list[_GithubFeedbackItem]:
        # GitHub splits PR discussion into three APIs: issue comments, reviews, and
        # inline review comments. We fetch all three and normalize them into one local shape.
        comments_task = self._fetch_paginated(
            client,
            token,
            f"https://api.github.com/repos/{repo}/issues/{pull_request_number}/comments",
        )
        reviews_task = self._fetch_paginated(
            client,
            token,
            f"https://api.github.com/repos/{repo}/pulls/{pull_request_number}/reviews",
        )
        review_comments_task = self._fetch_paginated(
            client,
            token,
            f"https://api.github.com/repos/{repo}/pulls/{pull_request_number}/comments",
        )
        comments, reviews, review_comments = await asyncio.gather(
            comments_task,
            reviews_task,
            review_comments_task,
        )

        items: list[_GithubFeedbackItem] = []
        items.extend(_build_pr_comment_items(comments))
        items.extend(_build_pr_review_items(reviews))
        items.extend(_build_pr_review_comment_items(review_comments))
        return items

    async def _fetch_paginated(
        self,
        client: httpx.AsyncClient,
        token: str,
        url: str,
    ) -> list[dict[str, Any]]:
        # These endpoints are paginated and a busy PR can easily exceed the first page,
        # so we always walk pages until GitHub returns fewer than the page size.
        page = 1
        items: list[dict[str, Any]] = []

        while True:
            response = await client.get(
                url,
                headers=_github_headers(token),
                params={"page": page, "per_page": 100},
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, list) or not payload:
                break

            items.extend(payload)
            if len(payload) < 100:
                break
            page += 1

        return items


def _extract_pull_request_number(value: str) -> int | None:
    match = _PULL_REQUEST_NUMBER_RE.search(value)
    if match is None:
        return None
    return int(match.group("number"))


def _github_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _parse_github_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _build_pr_comment_items(payloads: list[dict[str, Any]]) -> list[_GithubFeedbackItem]:
    items: list[_GithubFeedbackItem] = []
    for payload in payloads:
        items.append(
            _GithubFeedbackItem(
                kind=GithubPullRequestFeedbackKind.pr_comment,
                external_id=int(payload["id"]),
                author=_user_login(payload.get("user")),
                body=_normalize_text(payload.get("body")),
                review_state=None,
                file_path=None,
                line=None,
                original_line=None,
                commit_id=None,
                html_url=payload.get("html_url"),
                created_at=_parse_github_datetime(payload.get("created_at")),
                updated_at=_parse_github_datetime(payload.get("updated_at")),
                payload=payload,
            )
        )
    return items


def _build_pr_review_items(payloads: list[dict[str, Any]]) -> list[_GithubFeedbackItem]:
    items: list[_GithubFeedbackItem] = []
    for payload in payloads:
        items.append(
            _GithubFeedbackItem(
                kind=GithubPullRequestFeedbackKind.pr_review,
                external_id=int(payload["id"]),
                author=_user_login(payload.get("user")),
                body=_normalize_text(payload.get("body")),
                review_state=_normalize_text(payload.get("state")),
                file_path=None,
                line=None,
                original_line=None,
                commit_id=None,
                html_url=payload.get("html_url"),
                created_at=_parse_github_datetime(payload.get("submitted_at")),
                updated_at=_parse_github_datetime(payload.get("submitted_at")),
                payload=payload,
            )
        )
    return items


def _build_pr_review_comment_items(payloads: list[dict[str, Any]]) -> list[_GithubFeedbackItem]:
    items: list[_GithubFeedbackItem] = []
    for payload in payloads:
        items.append(
            _GithubFeedbackItem(
                kind=GithubPullRequestFeedbackKind.pr_review_comment,
                external_id=int(payload["id"]),
                author=_user_login(payload.get("user")),
                body=_normalize_text(payload.get("body")),
                review_state=None,
                file_path=_normalize_text(payload.get("path")),
                line=payload.get("line"),
                original_line=payload.get("original_line"),
                commit_id=_normalize_text(payload.get("commit_id")),
                html_url=payload.get("html_url"),
                created_at=_parse_github_datetime(payload.get("created_at")),
                updated_at=_parse_github_datetime(payload.get("updated_at")),
                payload=payload,
            )
        )
    return items


def _user_login(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    login = payload.get("login")
    if not isinstance(login, str):
        return None
    stripped = login.strip()
    return stripped or None


def _classify_feedback(
    item: _GithubFeedbackItem,
    viewer_login: str | None,
) -> tuple[GithubPullRequestFeedbackStatus, str | None]:
    # We only queue actionable external feedback. Empty bodies and the bot's own replies
    # are stored for bookkeeping but should not wake the agent up again.
    if item.body is None:
        return GithubPullRequestFeedbackStatus.ignored, "empty_body"
    if viewer_login and item.author and item.author.lower() == viewer_login.lower():
        return GithubPullRequestFeedbackStatus.ignored, "self_authored"
    return GithubPullRequestFeedbackStatus.pending, None
