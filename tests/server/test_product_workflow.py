from __future__ import annotations

import asyncio
import uuid
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

from src.server.postgres.models import AgentName
from src.server.postgres.repositories import AgentInstanceRepository, FeatureItemRepository
from src.server.product_workflow import ProductWorkflowPoller


class FakeDatabase:
    @asynccontextmanager
    async def session(self):
        """Return a fake database session."""
        yield object()


class FakeRunner:
    def __init__(self):
        """Initialize the test helper."""
        self.submit_task = AsyncMock(return_value="coding-task-id")


def _settings(**overrides):
    """Create test settings."""
    values = {
        "product_discovery_poll_interval_seconds": 60,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_poll_once_publishes_one_feature_item_to_tela(monkeypatch):
    """Verify poll once publishes one feature item to tela."""
    item = SimpleNamespace(id="feature-item-id", title="Knowledge base", description="Add search.")
    feature = SimpleNamespace(project="nexus")
    proposal = SimpleNamespace(repo="owner/repo", project="nexus")
    tela_instance_id = uuid.uuid4()
    tela = SimpleNamespace(id=tela_instance_id)
    runner = FakeRunner()
    captured = {}
    calls = {"item": 0}

    async def fake_next_item(session):
        """Provide a fake next item."""
        calls["item"] += 1
        return item if calls["item"] == 1 else None

    async def fake_list_agents(session, *, agent, github_repo, project, limit):
        """Provide a fake list agents."""
        captured["agent"] = agent
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

    async def fake_assign(session, item_id, *, task_id):
        """Provide a fake assign."""
        captured["assign"] = (item_id, task_id)
        return item

    monkeypatch.setattr(FeatureItemRepository, "get_next_unassigned", fake_next_item)
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
    assert captured["github_repo"] == "owner/repo"
    assert captured["project"] == "nexus"
    assert captured["limit"] == 1
    assert captured["feature_item_id"] == "feature-item-id"
    assert captured["proposal_item_id"] == "feature-item-id"
    payload = runner.submit_task.await_args.args[0]
    assert payload.agent_instance_id == tela_instance_id
    assert payload.agent.value == "tela"
    assert "Knowledge base" in payload.question
    assert captured["assign"] == ("feature-item-id", "coding-task-id")


def test_poll_once_skips_when_no_feature_item(monkeypatch):
    """Verify poll once skips when no feature item."""
    async def fake_next_item(session):
        """Provide a fake next item."""
        return None

    runner = FakeRunner()
    monkeypatch.setattr(FeatureItemRepository, "get_next_unassigned", fake_next_item)

    poller = ProductWorkflowPoller(
        settings=_settings(),
        database=FakeDatabase(),
        runner=runner,
    )

    result = asyncio.run(poller.poll_once())

    assert result == 0
    runner.submit_task.assert_not_awaited()
