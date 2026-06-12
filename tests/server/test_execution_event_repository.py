import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.exc import IntegrityError

from src.server.postgres.models import AgentName
from src.server.postgres.repositories import (
    ExecutionEventRepository,
    ExecutionEventWriteError,
    TaskExecutionEventRepository,
)


@pytest.mark.asyncio
async def test_task_execution_event_repository_persists_status_metadata():
    task_id = uuid.uuid4()
    refreshed = []
    session = SimpleNamespace(
        added=[],
        add=lambda record: session.added.append(record),
        commit=AsyncMock(),
        refresh=AsyncMock(side_effect=lambda record: refreshed.append(record)),
    )

    record = await TaskExecutionEventRepository.create_from_status(
        session,
        task_id=task_id,
        agent=AgentName.tela,
        status={
            "process": "PROCESS",
            "agent_content": "Using tools",
            "current_use_tool": ["RunCommand"],
        },
    )

    assert session.added == [record]
    assert record.task_id == task_id
    assert record.agent == AgentName.tela
    assert record.event_type == "PROCESS"
    assert record.message == "Using tools"
    assert record.safe_metadata == {
        "summary": "Using tools",
        "tool_names": ["RunCommand"],
        "tool_summary": "RunCommand",
    }
    session.commit.assert_awaited_once()
    session.refresh.assert_awaited_once_with(record)
    assert refreshed == [record]


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
    await ExecutionEventRepository.create(db_session, task_id=other_task_id, event_type="agent_failed")
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


@pytest.mark.asyncio
async def test_execution_event_repository_rejects_unknown_event_type(db_session):
    with pytest.raises(ExecutionEventWriteError) as exc_info:
        await ExecutionEventRepository.create(
            db_session,
            task_id=uuid.uuid4(),
            event_type="checkpoint_saved",  # type: ignore[arg-type]
        )

    assert isinstance(exc_info.value.__cause__, IntegrityError)
