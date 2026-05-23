from __future__ import annotations

import asyncio
import uuid
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

from src.server.product_discovery import ProductDiscoveryPoller, build_product_discovery_question
from src.server.postgres.models import AgentName, ProductProposalStatus, TaskCategory, TaskRecord, TaskStatus
from src.server.postgres.repositories import AgentInstanceRepository, ProductProposalRepository, UserRepository, WorkspaceRepository


def test_product_discovery_prompt_includes_context_and_guardrails():
    """Verify product discovery prompt keeps critical context and guardrails."""
    recent_proposals = [
        SimpleNamespace(
            title="Reduce duplicate product proposals",
            summary="Avoid repeated discovery output",
            status=ProductProposalStatus.proposed,
        ),
        SimpleNamespace(title="Improve onboarding funnel", summary="Shorten setup", status=ProductProposalStatus.approved),
    ]

    prompt = build_product_discovery_question(
        recent_proposals,
        proposal_limit=5,
        project="Nexus Growth",
        repo="yanghui1-arch/Nexus",
        pending_proposal_count=3,
    )

    assert "project=Nexus Growth" in prompt, "prompt should include project context"
    assert "repo=yanghui1-arch/Nexus" in prompt, "prompt should include repo context"
    assert "待处理 proposal 数量：3" in prompt, "prompt should include pending proposal count"
    assert "Title: Reduce duplicate product proposals" in prompt, "prompt should include recent proposal title"
    assert "Status: proposed" in prompt, "prompt should include recent proposal status"
    assert "避免重复" in prompt, "prompt should tell Marc to avoid duplicate proposals"
    assert "中文产品发现任务目标" in prompt, "prompt should preserve the Chinese discovery goal"
    assert "优化产品并提出一个proposal" in prompt, "prompt should keep the original Chinese task objective"


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
        "product_discovery_recent_proposal_limit": 5,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_poll_once_dispatches_only_dispatchable_instances(monkeypatch):
    """Verify poll once dispatches only dispatchable instances."""
    candidate = SimpleNamespace(id=uuid.uuid4(), agent=AgentName.marc)
    runner = FakeRunner()
    captured = {"proposal_calls": []}

    async def fake_list(session, *, limit):
        """Provide a fake list."""
        captured["limit"] = limit
        return [candidate]

    async def fake_workspace(session, agent_instance_id):
        """Provide a fake workspace."""
        return SimpleNamespace(github_repo="owner/repo", project="nexus")

    async def fake_proposals(session, **kwargs):
        """Provide fake proposals for prompt context."""
        captured["proposal_calls"].append(kwargs)
        if kwargs.get("status") == ProductProposalStatus.proposed:
            return [SimpleNamespace(title="Pending proposal", summary="Needs review", status=ProductProposalStatus.proposed)]
        return [SimpleNamespace(title="Existing proposal", summary="Already known", status=ProductProposalStatus.approved)]

    monkeypatch.setattr(AgentInstanceRepository, "list_product_discovery_candidates", fake_list)
    monkeypatch.setattr(WorkspaceRepository, "get_by_agent_instance_id", fake_workspace)
    monkeypatch.setattr(ProductProposalRepository, "list", fake_proposals)

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
    assert captured["proposal_calls"] == [
        {"project": "nexus", "repo": "owner/repo", "limit": 5},
        {"status": ProductProposalStatus.proposed, "project": "nexus", "repo": "owner/repo", "limit": 200},
    ]
    assert "Existing proposal" in payload.question
    assert "待处理 proposal 数量：1" in payload.question


def test_product_discovery_prompt_limits_and_sanitizes_proposals() -> None:
    """Verify product discovery prompt keeps recent proposal context bounded."""
    proposals = [
        SimpleNamespace(title="T" * 150, summary="S" * 550, answer="SECRET_ANSWER_ONE", status="proposed"),
        SimpleNamespace(title="Keep me", summary="Short summary", answer="SECRET_ANSWER_TWO", status="approved"),
        SimpleNamespace(title="Drop me", summary="Should not appear", answer="SECRET_ANSWER_THREE", status="rejected"),
    ]

    question = build_product_discovery_question(proposals, proposal_limit=2)

    assert question.count("- Title:") == 2
    assert "Drop me" not in question
    assert "SECRET_ANSWER" not in question
    assert "T" * 150 in question
    assert "S" * 550 in question
    assert len(question) == len(build_product_discovery_question(proposals[:2], proposal_limit=2))


def test_product_discovery_prompt_handles_empty_proposals() -> None:
    """Verify empty recent proposals render predictable context."""
    question = build_product_discovery_question([], proposal_limit=5)

    assert question.endswith("- None")
    assert "Answer:" not in question


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
        return SimpleNamespace(github_repo="owner/repo", project="nexus")

    async def fake_proposals(session, **kwargs):
        """Provide fake recent proposals."""
        return []

    runner = FakeRunner()
    runner.submit_task = AsyncMock(side_effect=fake_submit)
    monkeypatch.setattr(AgentInstanceRepository, "list_product_discovery_candidates", fake_list)
    monkeypatch.setattr(WorkspaceRepository, "get_by_agent_instance_id", fake_workspace)
    monkeypatch.setattr(ProductProposalRepository, "list", fake_proposals)

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
