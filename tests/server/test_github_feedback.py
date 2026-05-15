from __future__ import annotations

import asyncio
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx

from src.server.github_feedback import GithubFeedbackPoller
from src.server.postgres.models import (
    GithubPullRequestFeedbackStatus,
    TaskStatus,
)
from src.server.postgres.repositories import (
    GithubPullRequestFeedbackRepository,
    TaskRepository,
)


class FakeDatabase:
    @asynccontextmanager
    async def session(self):
        yield object()


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self._payload


def _make_settings():
    return SimpleNamespace(
        github_tokens={"sophie": "test-token"},
        github_feedback_poll_interval_seconds=60,
        github_feedback_poll_task_limit=20,
        github_feedback_http_timeout_seconds=10.0,
    )


def test_poll_once_discovers_feedback_and_reuses_existing_task(monkeypatch):
    task = SimpleNamespace(
        id=uuid.uuid4(),
        repo="owner/repo",
        external_pull_request_url="https://github.com/owner/repo/pull/12",
        agent=SimpleNamespace(value="sophie"),
        status=TaskStatus.waiting_for_review,
        result="existing result",
        updated_at=datetime.fromisoformat("2024-01-01T00:00:00+00:00"),
    )
    captured_statuses = []
    runner = SimpleNamespace(dispatch_github_feedback=AsyncMock(return_value=True))

    async def fake_list_candidates(session, *, limit):
        assert limit == 20
        return [task]

    async def fake_upsert(session, **kwargs):
        captured_statuses.append(
            {
                "kind": kwargs["kind"].value,
                "status": kwargs["status"],
                "author": kwargs["author"],
            }
        )
        return SimpleNamespace(id=uuid.uuid4()), True

    async def fake_has_pending_newer_than(session, task_id, *, cutoff):
        assert task_id == task.id
        assert cutoff == task.updated_at
        return False

    async def fake_get(self, url, headers=None, params=None):
        page = 1 if params is None else params.get("page", 1)
        if url.endswith("/user"):
            return FakeResponse({"login": "nexus-bot"})
        if url.endswith("/pulls/12"):
            return FakeResponse({"state": "open", "merged_at": None})
        if url.endswith("/issues/12/comments"):
            if page > 1:
                return FakeResponse([])
            return FakeResponse(
                [
                    {
                        "id": 101,
                        "user": {"login": "nexus-bot"},
                        "body": "I already replied here.",
                        "created_at": "2024-01-01T00:00:00Z",
                        "updated_at": "2024-01-01T00:00:00Z",
                        "html_url": "https://github.com/owner/repo/pull/12#issuecomment-101",
                    }
                ]
            )
        if url.endswith("/pulls/12/reviews"):
            if page > 1:
                return FakeResponse([])
            return FakeResponse(
                [
                    {
                        "id": 201,
                        "user": {"login": "reviewer"},
                        "state": "CHANGES_REQUESTED",
                        "body": "Please add a regression test.",
                        "submitted_at": "2024-01-02T00:00:00Z",
                        "html_url": "https://github.com/owner/repo/pull/12#pullrequestreview-201",
                    }
                ]
            )
        if url.endswith("/pulls/12/comments"):
            if page > 1:
                return FakeResponse([])
            return FakeResponse(
                [
                    {
                        "id": 301,
                        "user": {"login": "reviewer"},
                        "body": "Rename this variable.",
                        "path": "src/main.py",
                        "line": 42,
                        "original_line": 42,
                        "commit_id": "abc123",
                        "created_at": "2024-01-03T00:00:00Z",
                        "updated_at": "2024-01-03T00:00:00Z",
                        "html_url": "https://github.com/owner/repo/pull/12#discussion_r301",
                    }
                ]
            )
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(TaskRepository, "list_external_pull_request_candidates", fake_list_candidates)
    monkeypatch.setattr(GithubPullRequestFeedbackRepository, "upsert_discovered", fake_upsert)
    monkeypatch.setattr(
        GithubPullRequestFeedbackRepository,
        "has_pending_newer_than",
        fake_has_pending_newer_than,
    )
    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    poller = GithubFeedbackPoller(
        settings=_make_settings(),
        database=FakeDatabase(),
        runner=runner,
    )
    discovered = asyncio.run(poller.poll_once())

    assert discovered == 2
    runner.dispatch_github_feedback.assert_awaited_once_with(task.id)
    assert captured_statuses == [
        {
            "kind": "pr_comment",
            "status": GithubPullRequestFeedbackStatus.ignored,
            "author": "nexus-bot",
        },
        {
            "kind": "pr_review",
            "status": GithubPullRequestFeedbackStatus.pending,
            "author": "reviewer",
        },
        {
            "kind": "pr_review_comment",
            "status": GithubPullRequestFeedbackStatus.pending,
            "author": "reviewer",
        },
    ]


def test_poll_once_does_not_redispatch_stale_pending_feedback(monkeypatch):
    task = SimpleNamespace(
        id=uuid.uuid4(),
        repo="owner/repo",
        external_pull_request_url="https://github.com/owner/repo/pull/12",
        agent=SimpleNamespace(value="sophie"),
        status=TaskStatus.waiting_for_review,
        result="existing result",
        updated_at=datetime.fromisoformat("2024-01-10T00:00:00+00:00"),
    )
    runner = SimpleNamespace(dispatch_github_feedback=AsyncMock(return_value=True))

    async def fake_list_candidates(session, *, limit):
        return [task]

    async def fake_upsert(session, **kwargs):
        return SimpleNamespace(id=uuid.uuid4()), False

    async def fake_has_pending_newer_than(session, task_id, *, cutoff):
        assert task_id == task.id
        assert cutoff == task.updated_at
        return False

    async def fake_get(self, url, headers=None, params=None):
        page = 1 if params is None else params.get("page", 1)
        if url.endswith("/user"):
            return FakeResponse({"login": "nexus-bot"})
        if url.endswith("/pulls/12"):
            return FakeResponse({"state": "open", "merged_at": None})
        if page > 1:
            return FakeResponse([])
        if url.endswith("/issues/12/comments"):
            return FakeResponse(
                [
                    {
                        "id": 101,
                        "user": {"login": "reviewer"},
                        "body": "Already handled feedback.",
                        "created_at": "2024-01-01T00:00:00Z",
                        "updated_at": "2024-01-01T00:00:00Z",
                        "html_url": "https://github.com/owner/repo/pull/12#issuecomment-101",
                    }
                ]
            )
        if url.endswith("/pulls/12/reviews") or url.endswith("/pulls/12/comments"):
            return FakeResponse([])
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(TaskRepository, "list_external_pull_request_candidates", fake_list_candidates)
    monkeypatch.setattr(GithubPullRequestFeedbackRepository, "upsert_discovered", fake_upsert)
    monkeypatch.setattr(
        GithubPullRequestFeedbackRepository,
        "has_pending_newer_than",
        fake_has_pending_newer_than,
    )
    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    poller = GithubFeedbackPoller(
        settings=_make_settings(),
        database=FakeDatabase(),
        runner=runner,
    )
    discovered = asyncio.run(poller.poll_once())

    assert discovered == 0
    runner.dispatch_github_feedback.assert_not_awaited()


def test_poll_once_marks_merged_task_when_pull_request_is_merged(monkeypatch):
    task = SimpleNamespace(
        id=uuid.uuid4(),
        repo="owner/repo",
        external_pull_request_url="https://github.com/owner/repo/pull/12",
        agent=SimpleNamespace(value="sophie"),
        status=TaskStatus.waiting_for_merge,
        result="ready to merge",
        updated_at=datetime.fromisoformat("2024-01-10T00:00:00+00:00"),
    )
    runner = SimpleNamespace(dispatch_github_feedback=AsyncMock(return_value=True))
    captured = {}

    async def fake_list_candidates(session, *, limit):
        return [task]

    async def fake_fetch_pull_request(self, client, token, repo, pull_request_number):
        return {"state": "closed", "merged_at": "2024-01-11T00:00:00Z"}

    async def fake_set_merged(session, task_id):
        captured["task_id"] = task_id
        return SimpleNamespace(status=TaskStatus.merged)

    monkeypatch.setattr(TaskRepository, "list_external_pull_request_candidates", fake_list_candidates)
    monkeypatch.setattr(GithubFeedbackPoller, "_fetch_pull_request", fake_fetch_pull_request)
    monkeypatch.setattr(TaskRepository, "set_merged", fake_set_merged)

    poller = GithubFeedbackPoller(
        settings=_make_settings(),
        database=FakeDatabase(),
        runner=runner,
    )
    discovered = asyncio.run(poller.poll_once())

    assert discovered == 0
    assert captured == {"task_id": task.id}
    runner.dispatch_github_feedback.assert_not_awaited()


def test_poll_once_marks_task_closed_when_pull_request_is_closed_unmerged(monkeypatch):
    task = SimpleNamespace(
        id=uuid.uuid4(),
        repo="owner/repo",
        external_pull_request_url="https://github.com/owner/repo/pull/12",
        agent=SimpleNamespace(value="sophie"),
        status=TaskStatus.waiting_for_review,
        result="waiting for review",
        updated_at=datetime.fromisoformat("2024-01-10T00:00:00+00:00"),
    )
    runner = SimpleNamespace(dispatch_github_feedback=AsyncMock(return_value=True))
    captured = {}

    async def fake_list_candidates(session, *, limit):
        return [task]

    async def fake_fetch_pull_request(self, client, token, repo, pull_request_number):
        return {"state": "closed", "merged_at": None}

    async def fake_set_closed(session, task_id):
        captured["task_id"] = task_id
        return SimpleNamespace(status=TaskStatus.closed)

    monkeypatch.setattr(TaskRepository, "list_external_pull_request_candidates", fake_list_candidates)
    monkeypatch.setattr(GithubFeedbackPoller, "_fetch_pull_request", fake_fetch_pull_request)
    monkeypatch.setattr(TaskRepository, "set_closed", fake_set_closed)

    poller = GithubFeedbackPoller(
        settings=_make_settings(),
        database=FakeDatabase(),
        runner=runner,
    )
    discovered = asyncio.run(poller.poll_once())

    assert discovered == 0
    assert captured == {"task_id": task.id}
    runner.dispatch_github_feedback.assert_not_awaited()


def test_poll_once_does_not_promote_open_pull_request_to_waiting_for_merge(monkeypatch):
    task = SimpleNamespace(
        id=uuid.uuid4(),
        repo="owner/repo",
        external_pull_request_url="https://github.com/owner/repo/pull/12",
        agent=SimpleNamespace(value="sophie"),
        status=TaskStatus.waiting_for_review,
        result="review finished",
        updated_at=datetime.fromisoformat("2024-01-10T00:00:00+00:00"),
    )
    runner = SimpleNamespace(dispatch_github_feedback=AsyncMock(return_value=True))

    async def fake_list_candidates(session, *, limit):
        return [task]

    async def fake_fetch_pull_request(self, client, token, repo, pull_request_number):
        return {
            "state": "open",
            "merged_at": None,
            "draft": False,
            "mergeable_state": "clean",
        }

    async def fake_resolve_viewer_login(self, client, token):
        return "nexus-bot"

    async def fake_fetch_feedback_items(self, client, token, repo, pull_request_number):
        return []

    async def fake_has_pending_newer_than(session, task_id, *, cutoff):
        return False

    async def fail_set_waiting_for_merge(session, task_id, *, result):
        raise AssertionError("open pull requests should not be auto-promoted to waiting_for_merge")

    monkeypatch.setattr(TaskRepository, "list_external_pull_request_candidates", fake_list_candidates)
    monkeypatch.setattr(GithubFeedbackPoller, "_fetch_pull_request", fake_fetch_pull_request)
    monkeypatch.setattr(GithubFeedbackPoller, "_resolve_viewer_login", fake_resolve_viewer_login)
    monkeypatch.setattr(GithubFeedbackPoller, "_fetch_feedback_items", fake_fetch_feedback_items)
    monkeypatch.setattr(
        GithubPullRequestFeedbackRepository,
        "has_pending_newer_than",
        fake_has_pending_newer_than,
    )
    monkeypatch.setattr(TaskRepository, "set_waiting_for_merge", fail_set_waiting_for_merge)

    poller = GithubFeedbackPoller(
        settings=_make_settings(),
        database=FakeDatabase(),
        runner=runner,
    )
    discovered = asyncio.run(poller.poll_once())

    assert discovered == 0
    runner.dispatch_github_feedback.assert_not_awaited()
