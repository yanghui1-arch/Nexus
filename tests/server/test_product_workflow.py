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
        yield object()


class FakeRunner:
    def __init__(self):
        self.submit_task = AsyncMock(return_value="coding-task-id")


def _settings(**overrides):
    values = {
        "product_discovery_poll_interval_seconds": 60,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_poll_once_publishes_one_feature_item_to_tela(monkeypatch):
    item = SimpleNamespace(id="feature-item-id", title="Knowledge base", description="Add search.")
    feature = SimpleNamespace(project="nexus")
    tela_instance_id = uuid.uuid4()
    tela = SimpleNamespace(id=tela_instance_id)
    runner = FakeRunner()
    captured = {}
    calls = {"item": 0}

    async def fake_next_item(session):
        calls["item"] += 1
        return item if calls["item"] == 1 else None

    async def fake_list_agents(session, *, agent, limit):
        captured["agent"] = agent
        captured["limit"] = limit
        return [tela]

    async def fake_get_feature(session, item_id):
        captured["feature_item_id"] = item_id
        return feature

    async def fake_get_repo(session, item_id):
        captured["repo_item_id"] = item_id
        return "owner/repo"

    async def fake_assign(session, item_id, *, task_id):
        captured["assign"] = (item_id, task_id)
        return item

    monkeypatch.setattr(FeatureItemRepository, "get_next_unassigned", fake_next_item)
    monkeypatch.setattr(AgentInstanceRepository, "list_by_active_task_load", fake_list_agents)
    monkeypatch.setattr(FeatureItemRepository, "get_feature", fake_get_feature)
    monkeypatch.setattr(FeatureItemRepository, "get_repo", fake_get_repo)
    monkeypatch.setattr(FeatureItemRepository, "assign_task", fake_assign)

    poller = ProductWorkflowPoller(
        settings=_settings(),
        database=FakeDatabase(),
        runner=runner,
    )

    result = asyncio.run(poller.poll_once())

    assert result == 1
    assert captured["agent"] == AgentName.tela
    assert captured["limit"] == 1
    assert captured["feature_item_id"] == "feature-item-id"
    assert captured["repo_item_id"] == "feature-item-id"
    payload = runner.submit_task.await_args.args[0]
    assert payload.agent_instance_id == tela_instance_id
    assert payload.agent.value == "tela"
    assert payload.repo == "owner/repo"
    assert payload.project == "nexus"
    assert "Knowledge base" in payload.question
    assert captured["assign"] == ("feature-item-id", "coding-task-id")


def test_poll_once_skips_when_no_feature_item(monkeypatch):
    async def fake_next_item(session):
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
