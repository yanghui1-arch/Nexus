from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from src.extensions.discord.client import DiscordMessage
from src.server.postgres.models import AgentName, TaskCategory, TaskStatus
from src.server.postgres.repositories import SecretaryStateRepository, TaskRepository, WorkspaceRepository
from src.server.secretary.commands import SecretaryCommandProcessor, parse_command
from src.server.secretary.github import summarize_checks
from src.server.secretary.service import SecretaryService
from src.server.secretary.types import CheckSummary, PullRequestContext, PullRequestSummary


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


def secretary_settings(**overrides):
    """Build minimal secretary settings."""
    defaults = {
        "secretary_enabled": True,
        "secretary_github_token": "gh-token",
        "secretary_discord_bot_token": "discord-token",
        "secretary_discord_user_id": "user-1",
        "secretary_test_commands": {"owner/repo": ["pytest"]},
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def pr_summary(repo: str = "owner/repo", number: int = 12, *, draft: bool = False) -> PullRequestSummary:
    """Build a pull request summary."""
    return PullRequestSummary(
        repo=repo,
        number=number,
        title="Improve thing",
        state="open",
        draft=draft,
        html_url=f"https://github.com/{repo}/pull/{number}",
        author="agent",
        head_sha=f"sha-{number}",
        head_ref="feature",
        base_ref="main",
        mergeable=True,
        mergeable_state="clean",
    )


class FakeGithub:
    def __init__(self, pulls_by_repo: dict[str, list[PullRequestSummary]]) -> None:
        self.pulls_by_repo = pulls_by_repo
        self.listed: list[str] = []

    async def list_open_pull_requests(self, repo):
        self.listed.append(repo)
        return self.pulls_by_repo.get(repo, [])


class FakeRunner:
    def __init__(self) -> None:
        self.requests = []

    async def submit_task(self, request):
        self.requests.append(request)
        return uuid.uuid4()


class FakeDiscord:
    def __init__(self, messages: list[DiscordMessage] | None = None) -> None:
        self.messages = messages or []
        self.sent: list[str] = []

    async def create_dm(self, recipient_id):
        return "channel-1"

    async def send_message(self, channel_id, content, embeds=None):
        self.sent.append(content)
        return {"id": f"sent-{len(self.sent)}"}

    async def fetch_messages(self, channel_id, *, after=None, limit=50):
        return self.messages


def _assistant_workspace():
    return SimpleNamespace(
        agent_instance_id=uuid.uuid4(),
        github_repo="owner/repo",
        project="nexus",
    )


def _patch_state_repository(monkeypatch, storage: dict[str, str | None]) -> None:
    async def fake_get(session, key):
        return storage.get(key)

    async def fake_set(session, *, key, value):
        storage[key] = value
        return SimpleNamespace(key=key, value=value)

    monkeypatch.setattr(SecretaryStateRepository, "get", fake_get)
    monkeypatch.setattr(SecretaryStateRepository, "set", fake_set)


async def test_secretary_scan_dispatches_review_tasks_for_active_assistant_workspace_repos(monkeypatch):
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

    github = FakeGithub({"owner/repo": [pr_summary()]})
    runner = FakeRunner()
    service = SecretaryService(
        settings=secretary_settings(),
        database=FakeDatabase(),
        runner=runner,
        github_client=github,
    )

    queued = await service.scan_all()

    assert queued == 1
    assert github.listed == ["owner/repo"]
    assert len(runner.requests) == 1
    request = runner.requests[0]
    assert request.agent.value == "assistant"
    assert request.agent_instance_id == workspace.agent_instance_id
    assert request.external_pull_request_url == "https://github.com/owner/repo/pull/12"
    assert "Review pull request owner/repo#12" in request.question
    assert "Expected head SHA from dispatch: sha-12" in request.question


async def test_secretary_scan_dedupes_same_pr_head(monkeypatch):
    """Verify scan dedupe is by repo, PR number, and head SHA."""
    workspace = _assistant_workspace()
    state_storage: dict[str, str | None] = {}

    async def fake_workspaces(session, *, agent, limit=200):
        return [workspace]

    async def no_existing_task(session, **kwargs):
        return None

    _patch_state_repository(monkeypatch, state_storage)
    monkeypatch.setattr(WorkspaceRepository, "list_active_for_agent", fake_workspaces)
    monkeypatch.setattr(TaskRepository, "get_latest_by_external_pull_request_url", no_existing_task)

    github = FakeGithub({"owner/repo": [pr_summary()]})
    runner = FakeRunner()
    service = SecretaryService(
        settings=secretary_settings(),
        database=FakeDatabase(),
        runner=runner,
        github_client=github,
    )

    assert await service.scan_all() == 1
    assert await service.scan_all() == 0
    assert len(runner.requests) == 1


def test_parse_secretary_commands():
    """Verify Discord command parsing."""
    assert parse_command("scan").name == "scan"
    parsed = parse_command("review owner/repo#12")
    assert parsed.name == "review"
    assert parsed.repo == "owner/repo"
    assert parsed.pull_number == 12
    parsed = parse_command("status https://github.com/owner/repo/pull/99")
    assert parsed.name == "status"
    assert parsed.repo == "owner/repo"
    assert parsed.pull_number == 99


async def test_command_processor_dispatches_review_task(monkeypatch):
    """Verify Discord DM commands queue Assistant review tasks."""
    state_storage: dict[str, str | None] = {}
    _patch_state_repository(monkeypatch, state_storage)
    discord = FakeDiscord(
        [
            DiscordMessage(
                id="101",
                channel_id="channel-1",
                author_id="user-1",
                content="review owner/repo#12",
            )
        ]
    )

    class FakeService:
        calls: list[tuple[str, int, bool]] = []

        async def scan_all(self):
            return 0

        async def review_one(self, repo, pull_number, *, force=False, **kwargs):
            self.calls.append((repo, pull_number, force))
            return SimpleNamespace(
                repo=repo,
                pull_number=pull_number,
                pull_request_url="https://github.com/owner/repo/pull/12",
                task_id=uuid.uuid4(),
                created=True,
                message="Review task queued.",
            )

        async def latest_status(self, repo, pull_number):
            return None

    service = FakeService()
    processor = SecretaryCommandProcessor(
        settings=secretary_settings(),
        database=FakeDatabase(),
        service=service,
        discord_client=discord,
    )

    processed = await processor.poll_once()

    assert processed == 1
    assert service.calls == [("owner/repo", 12, True)]
    assert "Review task queued" in discord.sent[0]


async def test_command_processor_advances_cursor_for_ignored_messages(monkeypatch):
    """Verify ignored Discord messages do not get fetched forever."""
    state_storage: dict[str, str | None] = {}
    _patch_state_repository(monkeypatch, state_storage)
    discord = FakeDiscord(
        [
            DiscordMessage(
                id="102",
                channel_id="channel-1",
                author_id="bot-user",
                content="Review task queued",
            )
        ]
    )

    class FakeService:
        async def scan_all(self):
            return 0

        async def review_one(self, repo, pull_number, *, force=False):
            return None

        async def latest_status(self, repo, pull_number):
            return None

    processor = SecretaryCommandProcessor(
        settings=secretary_settings(),
        database=FakeDatabase(),
        service=FakeService(),
        discord_client=discord,
    )

    processed = await processor.poll_once()

    assert processed == 0
    assert state_storage["discord:last_command_id"] == "102"
    assert discord.sent == []


def test_summarize_checks_requires_available_checks():
    """Verify check summary treats missing checks as unavailable."""
    context = PullRequestContext(
        summary=pr_summary(),
        body="body",
        files=[],
        reviews=[],
        comments=[],
        review_comments=[],
        check_runs=[],
        statuses=[],
    )

    checks = summarize_checks(context)

    assert isinstance(checks, CheckSummary)
    assert checks.available is False
    assert checks.all_successful is False
