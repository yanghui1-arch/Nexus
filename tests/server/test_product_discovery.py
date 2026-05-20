from __future__ import annotations

import asyncio
import uuid
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

from src.server.product_discovery import ProductDiscoveryPoller
from src.server.postgres.models import AgentName, TaskCategory, TaskRecord, TaskStatus
from src.server.postgres.repositories import AgentInstanceRepository, UserRepository, WorkspaceRepository


class FakeDatabase:
    @asynccontextmanager
    async def session(self):
        yield object()


class FakeRunner:
    def __init__(self):
        self.submit_task = AsyncMock(side_effect=self._submit_task)
        self.created = []

    async def _submit_task(self, payload):
        self.created.append(payload)
        return uuid.uuid4()


def _settings(**overrides):
    values = {
        "product_discovery_poll_interval_seconds": 3600,
        "product_discovery_poll_task_limit": 20,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_poll_once_dispatches_only_dispatchable_instances(monkeypatch):
    candidate = SimpleNamespace(id=uuid.uuid4(), agent=AgentName.marc)
    runner = FakeRunner()
    captured = {}

    async def fake_list(session, *, limit):
        captured["limit"] = limit
        return [candidate]

    async def fake_workspace(session, agent_instance_id):
        return SimpleNamespace(github_repo="owner/repo", project="nexus")

    monkeypatch.setattr(AgentInstanceRepository, "list_product_discovery_candidates", fake_list)
    monkeypatch.setattr(WorkspaceRepository, "get_by_agent_instance_id", fake_workspace)

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
    candidate = SimpleNamespace(id=uuid.uuid4(), agent=AgentName.marc)

    async def fake_list(session, *, limit):
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
    first = SimpleNamespace(id=uuid.uuid4(), agent=AgentName.marc)
    second = SimpleNamespace(id=uuid.uuid4(), agent=AgentName.marc)
    calls = []

    async def fake_list(session, *, limit):
        calls.append(limit)
        return [first, second]

    async def fake_submit(payload):
        if payload.agent_instance_id == first.id:
            raise RuntimeError("dispatch failed")
        return uuid.UUID("00000000-0000-0000-0000-000000000002")

    async def fake_workspace(session, agent_instance_id):
        return SimpleNamespace(github_repo="owner/repo", project="nexus")

    runner = FakeRunner()
    runner.submit_task = AsyncMock(side_effect=fake_submit)
    monkeypatch.setattr(AgentInstanceRepository, "list_product_discovery_candidates", fake_list)
    monkeypatch.setattr(WorkspaceRepository, "get_by_agent_instance_id", fake_workspace)

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
    async def run():
        poller = ProductDiscoveryPoller(
            settings=_settings(product_discovery_poll_interval_seconds=1),
            database=FakeDatabase(),
            runner=FakeRunner(),
        )

        async def fake_run_loop():
            return None

        monkeypatch.setattr(poller, "_run_loop", fake_run_loop)
        poller.start()
        assert poller._task is not None
        await poller.stop()
        assert poller._task is None

    asyncio.run(run())


async def test_product_discovery_candidates_allow_waiting_for_review_pm_tasks(db_session):
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
