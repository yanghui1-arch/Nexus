from __future__ import annotations

import asyncio
import uuid
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

from src.server.postgres.models import AgentName
from src.server.postgres.repositories import AgentInstanceRepository, FeatureItemRepository
from src.server.product_workflow import ProductWorkflowPoller
from src.server.services.product_workflow_dispatch import FeatureItemDispatchGroup


class FakeDatabase:
    @asynccontextmanager
    async def session(self):
        """Return a fake database session."""
        yield object()


class FakeRunner:
    def __init__(self):
        """Initialize the test helper."""
        self.create_task_record = AsyncMock(return_value=SimpleNamespace(id="coding-task-id"))
        self.dispatch_task = AsyncMock(return_value=True)


def _settings(**overrides):
    """Create test settings."""
    values = {
        "product_workflow_poll_interval_seconds": 60,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_poll_once_publishes_one_feature_item_to_tela(monkeypatch):
    """Verify poll once publishes one feature item to tela."""
    item = SimpleNamespace(id="feature-item-id", title="Knowledge base", description="Add search.")
    feature = SimpleNamespace(project="nexus")
    proposal = SimpleNamespace(repo="owner/repo", project="nexus", user_id=uuid.uuid4())
    dispatch_group = FeatureItemDispatchGroup(
        user_id=proposal.user_id,
        repo=proposal.repo,
        project=proposal.project,
    )
    tela_instance_id = uuid.uuid4()
    tela = SimpleNamespace(id=tela_instance_id)
    runner = FakeRunner()
    captured = {}
    calls = {"groups": 0, "item": 0}

    async def fake_groups(session):
        """Provide a fake dispatch-group list."""
        calls["groups"] += 1
        return [dispatch_group] if calls["groups"] == 1 else []

    async def fake_next_item(session, *, dispatch_group):
        """Provide a fake next item for one group."""
        captured["dispatch_group"] = (dispatch_group.user_id, dispatch_group.repo, dispatch_group.project)
        calls["item"] += 1
        return item if calls["item"] == 1 else None

    async def fake_list_agents(session, *, agent, user_id, github_repo, project, limit):
        """Provide a fake list agents."""
        captured["agent"] = agent
        captured["user_id"] = user_id
        captured["github_repo"] = github_repo
        captured["project"] = project
        captured["limit"] = limit
        return [tela]

    async def fake_get_feature(session, item_id):
        """Provide a fake get feature."""
        captured["feature_item_id"] = item_id
        return feature

    async def fake_get_proposal(session, item_id):
        """Provide a fake get proposal."""
        captured["proposal_item_id"] = item_id
        return proposal

    async def fake_assign(session, item_id, *, task_id, require_unassigned=True):
        """Provide a fake assign."""
        captured["assign"] = (item_id, task_id)
        return item

    monkeypatch.setattr("src.server.services.product_workflow_dispatch.list_pending_dispatch_groups", fake_groups)
    monkeypatch.setattr(
        "src.server.services.product_workflow_dispatch.get_next_unassigned_for_dispatch_group",
        fake_next_item,
    )
    monkeypatch.setattr(AgentInstanceRepository, "list_by_active_task_load", fake_list_agents)
    monkeypatch.setattr(FeatureItemRepository, "get_feature", fake_get_feature)
    monkeypatch.setattr(FeatureItemRepository, "get_proposal", fake_get_proposal)
    monkeypatch.setattr(FeatureItemRepository, "assign_task", fake_assign)

    poller = ProductWorkflowPoller(
        settings=_settings(),
        database=FakeDatabase(),
        runner=runner,
    )

    result = asyncio.run(poller.poll_once())

    assert result == 1
    assert captured["agent"] == AgentName.tela
    assert captured["user_id"] == proposal.user_id
    assert captured["github_repo"] == "owner/repo"
    assert captured["project"] == "nexus"
    assert captured["limit"] == 1
    assert captured["dispatch_group"] == (proposal.user_id, "owner/repo", "nexus")
    assert captured["feature_item_id"] == "feature-item-id"
    assert captured["proposal_item_id"] == "feature-item-id"
    payload = runner.create_task_record.await_args.args[0]
    assert payload.agent_instance_id == tela_instance_id
    assert payload.agent == AgentName.tela
    assert "Knowledge base" in payload.question
    assert captured["assign"] == ("feature-item-id", "coding-task-id")
    runner.dispatch_task.assert_awaited_once_with("coding-task-id")


def test_poll_once_skips_when_no_feature_item(monkeypatch):
    """Verify poll once skips when no feature item."""
    async def fake_groups(session):
        """Provide no dispatch groups."""
        return []

    runner = FakeRunner()
    monkeypatch.setattr("src.server.services.product_workflow_dispatch.list_pending_dispatch_groups", fake_groups)

    poller = ProductWorkflowPoller(
        settings=_settings(),
        database=FakeDatabase(),
        runner=runner,
    )

    result = asyncio.run(poller.poll_once())

    assert result == 0
    runner.create_task_record.assert_not_awaited()
    runner.dispatch_task.assert_not_awaited()


def test_poll_once_skips_blocked_group_and_continues_with_other_workspaces(monkeypatch):
    """Verify one user's unavailable Tela does not block other workflow groups."""
    blocked_user = uuid.uuid4()
    ready_user = uuid.uuid4()
    blocked_group = FeatureItemDispatchGroup(user_id=blocked_user, repo="blocked/repo", project="blocked")
    ready_group = FeatureItemDispatchGroup(user_id=ready_user, repo="ready/repo", project="ready")
    blocked_item = SimpleNamespace(id="blocked-item", title="Blocked", description="Blocked item.")
    ready_item = SimpleNamespace(id="ready-item", title="Ready", description="Ready item.")
    ready_tela = SimpleNamespace(id=uuid.uuid4())
    ready_proposal = SimpleNamespace(repo="ready/repo", project="ready", user_id=ready_user)
    runner = FakeRunner()
    calls = {"groups": 0}
    captured = {"agent_calls": []}

    async def fake_groups(session):
        """Return one blocked group and one dispatchable group."""
        calls["groups"] += 1
        return [blocked_group, ready_group] if calls["groups"] == 1 else []

    async def fake_next_item(session, *, dispatch_group):
        """Return the next item for the requested group."""
        if (dispatch_group.user_id, dispatch_group.repo, dispatch_group.project) == (
            blocked_user,
            "blocked/repo",
            "blocked",
        ):
            return blocked_item
        if (dispatch_group.user_id, dispatch_group.repo, dispatch_group.project) == (
            ready_user,
            "ready/repo",
            "ready",
        ):
            return ready_item
        return None

    async def fake_list_agents(session, *, agent, user_id, github_repo, project, limit):
        """Return no Tela for the blocked group and one Tela for the ready group."""
        captured["agent_calls"].append((agent, user_id, github_repo, project, limit))
        if user_id == blocked_user:
            return []
        return [ready_tela]

    async def fake_get_feature(session, item_id):
        """Treat both feature items as valid."""
        return SimpleNamespace(project="ready" if item_id == "ready-item" else "blocked")

    async def fake_get_proposal(session, item_id):
        """Return the proposal owner for each item."""
        if item_id == "blocked-item":
            return SimpleNamespace(repo="blocked/repo", project="blocked", user_id=blocked_user)
        if item_id == "ready-item":
            return ready_proposal
        return None

    async def fake_assign(session, item_id, *, task_id, require_unassigned=True):
        """Assign only the dispatchable item."""
        captured["assign"] = (item_id, task_id)
        return ready_item

    monkeypatch.setattr("src.server.services.product_workflow_dispatch.list_pending_dispatch_groups", fake_groups)
    monkeypatch.setattr(
        "src.server.services.product_workflow_dispatch.get_next_unassigned_for_dispatch_group",
        fake_next_item,
    )
    monkeypatch.setattr(AgentInstanceRepository, "list_by_active_task_load", fake_list_agents)
    monkeypatch.setattr(FeatureItemRepository, "get_feature", fake_get_feature)
    monkeypatch.setattr(FeatureItemRepository, "get_proposal", fake_get_proposal)
    monkeypatch.setattr(FeatureItemRepository, "assign_task", fake_assign)

    poller = ProductWorkflowPoller(
        settings=_settings(),
        database=FakeDatabase(),
        runner=runner,
    )

    result = asyncio.run(poller.poll_once())

    assert result == 1
    assert captured["assign"] == ("ready-item", "coding-task-id")
    assert captured["agent_calls"] == [
        (AgentName.tela, blocked_user, "blocked/repo", "blocked", 1),
        (AgentName.tela, ready_user, "ready/repo", "ready", 1),
    ]
    payload = runner.create_task_record.await_args.args[0]
    assert payload.agent_instance_id == ready_tela.id
    assert "Ready" in payload.question
    runner.dispatch_task.assert_awaited_once_with("coding-task-id")


def test_product_workflow_poller_start_and_stop(monkeypatch):
    """Verify product workflow poller start and stop."""
    async def run():
        """Run the async test body."""
        poller = ProductWorkflowPoller(
            settings=_settings(product_workflow_poll_interval_seconds=1),
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
