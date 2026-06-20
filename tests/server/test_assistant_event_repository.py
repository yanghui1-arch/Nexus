from __future__ import annotations

import uuid
from datetime import datetime, timezone

from src.server.postgres.models import AgentInstanceRecord, AgentName
from src.server.postgres.repositories import AssistantEventRepository


async def test_assistant_event_repository_lists_recent_events_desc(db_session) -> None:
    agent_instance_id = uuid.uuid4()
    other_agent_instance_id = uuid.uuid4()
    db_session.add_all(
        [
            AgentInstanceRecord(
                id=agent_instance_id,
                user_id=uuid.uuid4(),
                agent=AgentName.assistant,
                client_id="assistant-1",
            ),
            AgentInstanceRecord(
                id=other_agent_instance_id,
                user_id=uuid.uuid4(),
                agent=AgentName.assistant,
                client_id="assistant-2",
            ),
        ]
    )
    await db_session.commit()

    older = await AssistantEventRepository.create(
        db_session,
        agent_instance_id=agent_instance_id,
        task_id=None,
        repo="owner/repo",
        project="nexus",
        external_pull_request_url="https://github.com/owner/repo/pull/12",
        external_issue_url=None,
        summary="older",
    )
    newer = await AssistantEventRepository.create(
        db_session,
        agent_instance_id=agent_instance_id,
        task_id=None,
        repo="owner/repo",
        project="nexus",
        external_pull_request_url="https://github.com/owner/repo/pull/12",
        external_issue_url=None,
        summary="newer",
    )
    other = await AssistantEventRepository.create(
        db_session,
        agent_instance_id=other_agent_instance_id,
        task_id=None,
        repo="owner/repo",
        project="nexus",
        external_pull_request_url="https://github.com/owner/repo/pull/12",
        external_issue_url=None,
        summary="other agent",
    )

    older.created_at = datetime(2026, 6, 20, 4, 0, 0, tzinfo=timezone.utc)
    newer.created_at = datetime(2026, 6, 20, 4, 10, 0, tzinfo=timezone.utc)
    other.created_at = datetime(2026, 6, 20, 4, 20, 0, tzinfo=timezone.utc)
    await db_session.commit()

    events = await AssistantEventRepository.list_recent(
        db_session,
        agent_instance_id=agent_instance_id,
        limit=10,
        external_pull_request_url="https://github.com/owner/repo/pull/12",
        start_time=datetime(2026, 6, 20, 3, 59, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 6, 20, 4, 11, 0, tzinfo=timezone.utc),
    )

    assert [event.summary for event in events] == ["newer", "older"]
