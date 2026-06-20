from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from src.server.postgres.models import AgentName, TaskStatus
from src.server.postgres.repositories import AssistantStateRepository, TaskRepository, WorkspaceRepository
import src.server.services.assistant as assistant_service
from src.server.services.assistant import AssistantService, PullRequestSummary


pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    """Run anyio tests on asyncio only."""
    return "asyncio"


class FakeDatabase:
    """Minimal async-session provider for repository monkeypatch tests."""

    def __init__(self) -> None:
        self.session_obj = object()

    @asynccontextmanager
    async def session(self):
        yield self.session_obj


def assistant_settings(**overrides):
    """Build minimal assistant settings."""
    defaults = {
        "assistant_enabled": True,
        "assistant_github_token": "gh-token",
        "assistant_test_commands": {"owner/repo": ["pytest"]},
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def pr_summary(
    repo: str = "owner/repo",
    number: int = 12,
    *,
    draft: bool = False,
    created_at: str | None = None,
) -> PullRequestSummary:
    """Build a pull request summary."""
    return PullRequestSummary(
        repo=repo,
        number=number,
        title="Improve thing",
        state="open",
        draft=draft,
        html_url=f"https://github.com/{repo}/pull/{number}",
        author="agent",
        created_at=created_at or f"2026-01-{number:02d}T00:00:00Z",
        head_sha=f"sha-{number}",
        head_ref="feature",
        base_ref="main",
        mergeable=True,
        mergeable_state="clean",
    )


class FakeRunner:
    def __init__(self) -> None:
        self.requests = []

    async def submit_task(self, request):
        self.requests.append(request)
        return uuid.uuid4()


def _assistant_workspace(repo: str = "owner/repo"):
    return SimpleNamespace(
        agent_instance_id=uuid.uuid4(),
        github_repo=repo,
        project="nexus",
    )


def _patch_state_repository(monkeypatch, storage: dict[str, str | None]) -> None:
    async def fake_get(session, key):
        return storage.get(key)

    async def fake_set(session, *, key, value):
        storage[key] = value
        return SimpleNamespace(key=key, value=value)

    monkeypatch.setattr(AssistantStateRepository, "get", fake_get)
    monkeypatch.setattr(AssistantStateRepository, "set", fake_set)


def _patch_open_prs(
    monkeypatch,
    pulls_by_repo: dict[str, list[PullRequestSummary]],
) -> list[str]:
    listed: list[str] = []

    async def fake_list_open_pull_requests(token: str, repo: str) -> list[PullRequestSummary]:
        assert token == "gh-token"
        listed.append(repo)
        return pulls_by_repo.get(repo, [])

    monkeypatch.setattr(assistant_service, "_list_open_pull_requests", fake_list_open_pull_requests)
    return listed


async def test_assistant_scan_dispatches_review_tasks_for_active_assistant_workspace_repos(monkeypatch):
    """Verify scheduled scans queue Assistant review tasks from workspace repos."""
    workspace = _assistant_workspace()
    state_storage: dict[str, str | None] = {}

    async def fake_workspaces(session, *, agent, limit=200):
        assert agent == AgentName.assistant
        return [workspace]

    async def no_existing_task(session, **kwargs):
        return None

    _patch_state_repository(monkeypatch, state_storage)
    monkeypatch.setattr(WorkspaceRepository, "list_active_for_agent", fake_workspaces)
    monkeypatch.setattr(TaskRepository, "get_latest_by_external_pull_request_url", no_existing_task)

    listed_repos = _patch_open_prs(monkeypatch, {"owner/repo": [pr_summary()]})
    runner = FakeRunner()
    service = AssistantService(
        settings=assistant_settings(),
        database=FakeDatabase(),
        runner=runner,
    )

    queued = await service.scan_all()

    assert queued == 1
    assert listed_repos == ["owner/repo"]
    assert len(runner.requests) == 1
    request = runner.requests[0]
    assert request.agent.value == "assistant"
    assert request.agent_instance_id == workspace.agent_instance_id
    assert request.external_pull_request_url == "https://github.com/owner/repo/pull/12"
    assert "Review pull request owner/repo#12" in request.question
    assert "Expected head SHA from dispatch: sha-12" in request.question


async def test_assistant_scan_dispatches_for_each_assistant_workspace_on_same_repo(monkeypatch):
    """Verify scheduled scans queue one review task per Assistant workspace."""
    workspaces = [_assistant_workspace(), _assistant_workspace()]
    state_storage: dict[str, str | None] = {}

    async def fake_workspaces(session, *, agent, limit=200):
        assert agent == AgentName.assistant
        return workspaces

    async def no_existing_task(session, **kwargs):
        return None

    _patch_state_repository(monkeypatch, state_storage)
    monkeypatch.setattr(WorkspaceRepository, "list_active_for_agent", fake_workspaces)
    monkeypatch.setattr(TaskRepository, "get_latest_by_external_pull_request_url", no_existing_task)

    listed_repos = _patch_open_prs(monkeypatch, {"owner/repo": [pr_summary()]})
    runner = FakeRunner()
    service = AssistantService(
        settings=assistant_settings(),
        database=FakeDatabase(),
        runner=runner,
    )

    queued = await service.scan_all()

    assert queued == 2
    assert listed_repos == ["owner/repo"]
    assert [request.agent_instance_id for request in runner.requests] == [
        workspaces[0].agent_instance_id,
        workspaces[1].agent_instance_id,
    ]
    assert len(state_storage) == 2


async def test_assistant_scan_dedupes_same_pr_head(monkeypatch):
    """Verify scan dedupe is by workspace, repo, PR number, and head SHA."""
    workspace = _assistant_workspace()
    state_storage: dict[str, str | None] = {}

    async def fake_workspaces(session, *, agent, limit=200):
        return [workspace]

    async def no_existing_task(session, **kwargs):
        return None

    _patch_state_repository(monkeypatch, state_storage)
    monkeypatch.setattr(WorkspaceRepository, "list_active_for_agent", fake_workspaces)
    monkeypatch.setattr(TaskRepository, "get_latest_by_external_pull_request_url", no_existing_task)

    _patch_open_prs(monkeypatch, {"owner/repo": [pr_summary()]})
    runner = FakeRunner()
    service = AssistantService(
        settings=assistant_settings(),
        database=FakeDatabase(),
        runner=runner,
    )

    assert await service.scan_all() == 1
    assert await service.scan_all() == 0
    assert len(runner.requests) == 1


async def test_assistant_scan_leaves_existing_review_thread_to_github_feedback_poller(monkeypatch):
    """Verify scheduled scans do not create a second task for an existing PR thread."""
    workspace = _assistant_workspace()
    state_storage: dict[str, str | None] = {}

    async def fake_workspaces(session, *, agent, limit=200):
        return [workspace]

    async def existing_waiting_review_task(session, **kwargs):
        return SimpleNamespace(id=uuid.uuid4(), status=TaskStatus.waiting_for_review)

    _patch_state_repository(monkeypatch, state_storage)
    monkeypatch.setattr(WorkspaceRepository, "list_active_for_agent", fake_workspaces)
    monkeypatch.setattr(TaskRepository, "get_latest_by_external_pull_request_url", existing_waiting_review_task)
    _patch_open_prs(monkeypatch, {"owner/repo": [pr_summary(number=12, created_at="2026-01-12T00:00:00Z")]})
    runner = FakeRunner()
    service = AssistantService(
        settings=assistant_settings(),
        database=FakeDatabase(),
        runner=runner,
    )

    queued = await service.scan_all()

    assert queued == 0
    assert runner.requests == []


async def test_assistant_scan_queues_at_most_three_oldest_pull_requests(monkeypatch):
    """Verify scheduled scans bound review task fanout by PR creation time."""
    workspace = _assistant_workspace()
    state_storage: dict[str, str | None] = {}

    async def fake_workspaces(session, *, agent, limit=200):
        return [workspace]

    async def no_existing_task(session, **kwargs):
        return None

    _patch_state_repository(monkeypatch, state_storage)
    monkeypatch.setattr(WorkspaceRepository, "list_active_for_agent", fake_workspaces)
    monkeypatch.setattr(TaskRepository, "get_latest_by_external_pull_request_url", no_existing_task)
    _patch_open_prs(
        monkeypatch,
        {
            "owner/repo": [
                pr_summary(number=20, created_at="2026-01-20T00:00:00Z"),
                pr_summary(number=10, created_at="2026-01-10T00:00:00Z"),
                pr_summary(number=11, created_at="2026-01-11T00:00:00Z", draft=True),
                pr_summary(number=12, created_at="2026-01-12T00:00:00Z"),
                pr_summary(number=13, created_at="2026-01-13T00:00:00Z"),
                pr_summary(number=14, created_at="2026-01-14T00:00:00Z"),
            ]
        },
    )
    runner = FakeRunner()
    service = AssistantService(
        settings=assistant_settings(),
        database=FakeDatabase(),
        runner=runner,
    )

    queued = await service.scan_all()

    assert queued == 3
    assert [request.external_pull_request_url for request in runner.requests] == [
        "https://github.com/owner/repo/pull/10",
        "https://github.com/owner/repo/pull/12",
        "https://github.com/owner/repo/pull/13",
    ]


async def test_assistant_scan_continues_when_one_repo_pr_listing_fails(monkeypatch):
    """Verify a GitHub API failure for one repo does not stop the whole scan."""
    workspaces = [
        _assistant_workspace(repo="broken/repo"),
        _assistant_workspace(repo="owner/repo"),
    ]
    state_storage: dict[str, str | None] = {}

    async def fake_workspaces(session, *, agent, limit=200):
        return workspaces

    async def no_existing_task(session, **kwargs):
        return None

    async def fake_list_open_pull_requests(token: str, repo: str) -> list[PullRequestSummary]:
        if repo == "broken/repo":
            raise RuntimeError("GitHub unavailable")
        return [pr_summary(repo=repo, number=15)]

    _patch_state_repository(monkeypatch, state_storage)
    monkeypatch.setattr(WorkspaceRepository, "list_active_for_agent", fake_workspaces)
    monkeypatch.setattr(TaskRepository, "get_latest_by_external_pull_request_url", no_existing_task)
    monkeypatch.setattr(assistant_service, "_list_open_pull_requests", fake_list_open_pull_requests)
    runner = FakeRunner()
    service = AssistantService(
        settings=assistant_settings(),
        database=FakeDatabase(),
        runner=runner,
    )

    queued = await service.scan_all()

    assert queued == 1
    assert len(runner.requests) == 1
    assert runner.requests[0].external_pull_request_url == "https://github.com/owner/repo/pull/15"


async def test_open_pr_scan_uses_direct_github_rest(monkeypatch):
    """Verify open PR discovery uses GitHub REST without a dedicated client."""
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            captured["raised"] = True

        def json(self):
            return [
                {
                    "number": 9,
                    "title": "Small fix",
                    "state": "open",
                    "draft": False,
                    "created_at": "2026-01-09T00:00:00Z",
                    "html_url": "https://github.com/owner/repo/pull/9",
                    "user": {"login": "tela"},
                    "head": {"sha": "head-sha", "ref": "branch"},
                    "base": {"ref": "main"},
                    "mergeable": True,
                    "mergeable_state": "clean",
                }
            ]

    class FakeAsyncClient:
        def __init__(self, *, timeout):
            captured["timeout"] = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, *, headers, params):
            captured["url"] = url
            captured["headers"] = headers
            captured["params"] = params
            return FakeResponse()

    monkeypatch.setattr(assistant_service.httpx, "AsyncClient", FakeAsyncClient)

    pulls = await assistant_service._list_open_pull_requests("token", "owner/repo", timeout=3.0)

    assert len(pulls) == 1
    assert pulls[0].number == 9
    assert pulls[0].created_at == "2026-01-09T00:00:00Z"
    assert pulls[0].head_sha == "head-sha"
    assert captured["url"] == "https://api.github.com/repos/owner/repo/pulls"
    assert captured["headers"]["Authorization"] == "Bearer token"
    assert captured["params"] == {
        "state": "open",
        "sort": "created",
        "direction": "asc",
        "per_page": 100,
        "page": 1,
    }
    assert captured["raised"] is True
