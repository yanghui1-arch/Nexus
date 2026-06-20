from __future__ import annotations

import asyncio
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

from src.server.postgres.repositories import AssistantEventRepository
from src.tools.nexus import NEXUS_ASSISTANT_EVENT_TOOL_DEFINITIONS
from src.tools.nexus.client import NexusAssistantEventContext, NexusAssistantEventTools


class FakeDatabase:
    @asynccontextmanager
    async def session(self):
        yield object()


def test_assistant_event_tools_use_hidden_agent_context(monkeypatch) -> None:
    agent_instance_id = uuid.uuid4()
    task_id = uuid.uuid4()
    created_at = datetime(2026, 6, 20, 4, 7, 38, tzinfo=timezone.utc)
    context = NexusAssistantEventContext(
        agent_instance_id=agent_instance_id,
        database=FakeDatabase(),
        repo="owner/repo",
        project="nexus",
        current_task_id=task_id,
    )
    captured: dict[str, Any] = {}

    async def fake_create(session, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            id=uuid.uuid4(),
            agent_instance_id=kwargs["agent_instance_id"],
            task_id=kwargs["task_id"],
            repo=kwargs["repo"],
            project=kwargs["project"],
            external_pull_request_url=kwargs["external_pull_request_url"],
            external_issue_url=kwargs["external_issue_url"],
            summary=kwargs["summary"],
            created_at=created_at,
        )

    monkeypatch.setattr(AssistantEventRepository, "create", fake_create)

    result = asyncio.run(
        NexusAssistantEventTools(context).record_assistant_event(
            summary="Reviewed PR #12 and requested changes.",
            pull_request_url="https://github.com/owner/repo/pull/12",
        )
    )

    assert result["success"] is True
    assert captured == {
        "agent_instance_id": agent_instance_id,
        "task_id": task_id,
        "repo": "owner/repo",
        "project": "nexus",
        "external_pull_request_url": "https://github.com/owner/repo/pull/12",
        "external_issue_url": None,
        "summary": "Reviewed PR #12 and requested changes.",
    }
    assert result["event"]["created_at"] == created_at.isoformat()
    assert "id" not in result["event"]
    assert "agent_instance_id" not in result["event"]
    assert "external_issue_url" not in result["event"]
    assert any(
        tool["function"]["name"] == "record_assistant_event"
        for tool in NEXUS_ASSISTANT_EVENT_TOOL_DEFINITIONS
    )


def test_list_recent_assistant_events_filters_time_and_returns_desc_marker(monkeypatch) -> None:
    agent_instance_id = uuid.uuid4()
    context = NexusAssistantEventContext(
        agent_instance_id=agent_instance_id,
        database=FakeDatabase(),
        repo="owner/repo",
        project="nexus",
    )
    captured: dict[str, Any] = {}
    newer_time = datetime(2026, 6, 20, 4, 8, 0, tzinfo=timezone.utc)
    older_time = datetime(2026, 6, 20, 4, 7, 0, tzinfo=timezone.utc)

    async def fake_list_recent(session, **kwargs):
        captured.update(kwargs)
        return [
            SimpleNamespace(
                id=uuid.uuid4(),
                agent_instance_id=agent_instance_id,
                task_id=None,
                repo="owner/repo",
                project="nexus",
                external_pull_request_url="https://github.com/owner/repo/pull/12",
                external_issue_url=None,
                summary="newer",
                created_at=newer_time,
            ),
            SimpleNamespace(
                id=uuid.uuid4(),
                agent_instance_id=agent_instance_id,
                task_id=None,
                repo="owner/repo",
                project="nexus",
                external_pull_request_url="https://github.com/owner/repo/pull/12",
                external_issue_url=None,
                summary="older",
                created_at=older_time,
            ),
        ]

    monkeypatch.setattr(AssistantEventRepository, "list_recent", fake_list_recent)

    result = asyncio.run(
        NexusAssistantEventTools(context).list_recent_assistant_events(
            limit=20,
            pull_request_url="https://github.com/owner/repo/pull/12",
            start_time="2026-06-20T04:00:00Z",
            end_time="2026-06-20T05:00:00Z",
        )
    )

    assert captured["agent_instance_id"] == agent_instance_id
    assert captured["limit"] == 20
    assert captured["external_pull_request_url"] == "https://github.com/owner/repo/pull/12"
    assert captured["start_time"] == datetime(2026, 6, 20, 4, 0, 0, tzinfo=timezone.utc)
    assert captured["end_time"] == datetime(2026, 6, 20, 5, 0, 0, tzinfo=timezone.utc)
    assert result["order"] == "created_at_desc"
    assert [event["summary"] for event in result["events"]] == ["newer", "older"]
    assert "id" not in result["events"][0]
    assert "agent_instance_id" not in result["events"][0]
    assert "task_id" not in result["events"][0]
    assert "external_issue_url" not in result["events"][0]
