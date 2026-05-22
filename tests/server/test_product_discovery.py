from __future__ import annotations

import asyncio
import uuid
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

from src.server.product_discovery import ProductDiscoveryPoller
from src.server.postgres.models import AgentName, TaskCategory, TaskRecord, TaskStatus
from src.server.postgres.repositories import AgentInstanceRepository, TaskRepository, UserRepository, WorkspaceRepository


class FakeDatabase:
    @asynccontextmanager
    async def session(self):
        """Return a fake database session."""
        yield object()


class FakeRunner:
    def __init__(self):
        """Initialize the test helper."""
        self.submit_task = AsyncMock(side_effect=self._submit_task)
        self.created = []

    async def _submit_task(self, payload):
        """Support submit task tests."""
        self.created.append(payload)
        return uuid.uuid4()


def _settings(**overrides):
    """Create test settings."""
    values = {
        "product_discovery_poll_interval_seconds": 3600,
        "product_discovery_poll_task_limit": 20,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_poll_once_dispatches_only_dispatchable_instances(monkeypatch):
    """Verify poll once dispatches only dispatchable instances."""
    candidate = SimpleNamespace(id=uuid.uuid4(), agent=AgentName.marc)
    runner = FakeRunner()
    captured = {}

    async def fake_list(session, *, limit):
        """Provide a fake list."""
        captured["limit"] = limit
        return [candidate]

    async def fake_workspace(session, agent_instance_id):
        """Provide a fake workspace."""
        return SimpleNamespace(
            id=uuid.uuid4(),
            github_repo="owner/repo",
            project="nexus",
            last_used_at="2026-01-01T00:00:00+00:00",
            updated_at="2026-01-01T00:00:00+00:00",
        )

    async def fake_pending_count(session, *, agent_instance_id):
        """Provide a fake active PM task count."""
        return 0

    monkeypatch.setattr(AgentInstanceRepository, "list_product_discovery_candidates", fake_list)
    monkeypatch.setattr(WorkspaceRepository, "get_by_agent_instance_id", fake_workspace)
    monkeypatch.setattr(TaskRepository, "count_active_pm_tasks", fake_pending_count)

    poller = ProductDiscoveryPoller(
        settings=_settings(),
        database=FakeDatabase(),
        runner=runner,
    )

    result = asyncio.run(poller.poll_once())

    assert result == 1
    assert captured["limit"] == 20
    runner.submit_task.assert_awaited_once()
    payload = runner.submit_task.await_args.args[0]
    assert payload.agent_instance_id == candidate.id
    assert payload.agent == AgentName.marc


def test_poll_once_skips_when_stop_requested(monkeypatch):
    """Verify poll once skips when stop requested."""
    candidate = SimpleNamespace(id=uuid.uuid4(), agent=AgentName.marc)

    async def fake_list(session, *, limit):
        """Provide a fake list."""
        return [candidate]

    runner = FakeRunner()
    monkeypatch.setattr(AgentInstanceRepository, "list_product_discovery_candidates", fake_list)

    poller = ProductDiscoveryPoller(
        settings=_settings(),
        database=FakeDatabase(),
        runner=runner,
    )
    poller._stop_event.set()

    result = asyncio.run(poller.poll_once())

    assert result == 0
    runner.submit_task.assert_not_awaited()


def test_poll_once_continues_after_submit_failure(monkeypatch):
    """Verify poll once continues after submit failure."""
    first = SimpleNamespace(id=uuid.uuid4(), agent=AgentName.marc)
    second = SimpleNamespace(id=uuid.uuid4(), agent=AgentName.marc)
    calls = []

    async def fake_list(session, *, limit):
        """Provide a fake list."""
        calls.append(limit)
        return [first, second]

    async def fake_submit(payload):
        """Provide a fake submit."""
        if payload.agent_instance_id == first.id:
            raise RuntimeError("dispatch failed")
        return uuid.UUID("00000000-0000-0000-0000-000000000002")

    async def fake_workspace(session, agent_instance_id):
        """Provide a fake workspace."""
        return SimpleNamespace(
            id=uuid.uuid4(),
            github_repo="owner/repo",
            project="nexus",
            last_used_at="2026-01-01T00:00:00+00:00",
            updated_at="2026-01-01T00:00:00+00:00",
        )

    async def fake_pending_count(session, *, agent_instance_id):
        """Provide a fake active PM task count."""
        return 0

    runner = FakeRunner()
    runner.submit_task = AsyncMock(side_effect=fake_submit)
    monkeypatch.setattr(AgentInstanceRepository, "list_product_discovery_candidates", fake_list)
    monkeypatch.setattr(WorkspaceRepository, "get_by_agent_instance_id", fake_workspace)
    monkeypatch.setattr(TaskRepository, "count_active_pm_tasks", fake_pending_count)

    poller = ProductDiscoveryPoller(
        settings=_settings(),
        database=FakeDatabase(),
        runner=runner,
    )

    result = asyncio.run(poller.poll_once())

    assert result == 1
    assert calls == [20]
    assert runner.submit_task.await_count == 2


def test_product_discovery_poller_start_and_stop(monkeypatch):
    """Verify product discovery poller start and stop."""
    async def run():
        """Run the async test body."""
        poller = ProductDiscoveryPoller(
            settings=_settings(product_discovery_poll_interval_seconds=1),
            database=FakeDatabase(),
            runner=FakeRunner(),
        )

        async def fake_run_loop():
            """Provide a fake run loop."""
            return None

        monkeypatch.setattr(poller, "_run_loop", fake_run_loop)
        poller.start()
        assert poller._task is not None
        await poller.stop()
        assert poller._task is None

    asyncio.run(run())


async def test_product_discovery_candidates_allow_waiting_for_review_pm_tasks(db_session):
    """Verify product discovery candidates allow waiting for review pm tasks."""
    user = await UserRepository.upsert_github_user(
        db_session, github_id="discovery-waiting", github_login="marc-waiting", email=None
    )
    instance = await AgentInstanceRepository.create(
        db_session,
        agent=AgentName.marc,
        client_id="marc-waiting-review",
        display_name="Marc Waiting Review",
        user_id=user.id,
    )
    db_session.add(
        TaskRecord(
            agent=AgentName.marc,
            agent_instance_id=instance.id,
            category=TaskCategory.pm,
            question="产品提案",
            status=TaskStatus.waiting_for_review,
        )
    )
    await db_session.commit()

    candidates = await AgentInstanceRepository.list_product_discovery_candidates(db_session)

    assert [candidate.id for candidate in candidates] == [instance.id]


async def test_product_discovery_candidates_block_running_pm_tasks(db_session):
    """Verify product discovery candidates block running pm tasks."""
    user = await UserRepository.upsert_github_user(
        db_session, github_id="discovery-running", github_login="marc-running", email=None
    )
    instance = await AgentInstanceRepository.create(
        db_session,
        agent=AgentName.marc,
        client_id="marc-running",
        display_name="Marc Running",
        user_id=user.id,
    )
    db_session.add(
        TaskRecord(
            agent=AgentName.marc,
            agent_instance_id=instance.id,
            category=TaskCategory.pm,
            question="产品提案",
            status=TaskStatus.running,
        )
    )
    await db_session.commit()

    candidates = await AgentInstanceRepository.list_product_discovery_candidates(db_session)

    assert candidates == []
