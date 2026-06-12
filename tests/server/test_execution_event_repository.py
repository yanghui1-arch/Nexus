import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from src.server.postgres.repositories import ExecutionEventRepository, ExecutionEventWriteError


@pytest.mark.asyncio
async def test_execution_event_repository_creates_and_lists_by_task(db_session):
    task_id = uuid.uuid4()
    other_task_id = uuid.uuid4()
    first = await ExecutionEventRepository.create(
        db_session,
        task_id=task_id,
        event_type="agent_started",
        message="started",
        payload={"step": 1},
    )
    await ExecutionEventRepository.create(db_session, task_id=other_task_id, event_type="ignored")
    second = await ExecutionEventRepository.create(
        db_session,
        task_id=task_id,
        event_type="tool_call",
        payload={"tool": "RunCommand"},
    )

    events = await ExecutionEventRepository.list_by_task(db_session, task_id, limit=1, offset=1)

    assert first.id != second.id
    assert [event.id for event in events] == [second.id]
    assert events[0].payload == {"tool": "RunCommand"}


@pytest.mark.asyncio
async def test_execution_event_repository_returns_task_aggregate_data(db_session):
    task_id = uuid.uuid4()
    await ExecutionEventRepository.create(db_session, task_id=task_id, event_type="tool_call")
    latest = await ExecutionEventRepository.create(db_session, task_id=task_id, event_type="tool_call")
    await ExecutionEventRepository.create(db_session, task_id=task_id, event_type="agent_message")
    await ExecutionEventRepository.create(db_session, task_id=uuid.uuid4(), event_type="tool_call")

    aggregate = await ExecutionEventRepository.get_task_aggregate_data(db_session, task_id)

    assert aggregate["task_id"] == task_id
    assert aggregate["total_count"] == 3
    assert aggregate["counts_by_type"] == {"agent_message": 1, "tool_call": 2}
    assert aggregate["latest_event"].task_id == task_id
    assert aggregate["latest_event"].id != latest.id


@pytest.mark.asyncio
async def test_execution_event_repository_wraps_write_failure():
    session = SimpleNamespace(
        add=Mock(),
        commit=AsyncMock(side_effect=RuntimeError("boom")),
        rollback=AsyncMock(),
    )

    with pytest.raises(ExecutionEventWriteError):
        await ExecutionEventRepository.create(
            session, task_id=uuid.uuid4(), event_type="agent_started"
        )
    session.rollback.assert_awaited_once()
