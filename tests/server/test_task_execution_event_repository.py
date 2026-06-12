import uuid

from src.server.postgres.models import AgentName, TaskCategory, TaskRecord, TaskStatus
from src.server.postgres.repositories import (
    AgentInstanceRepository,
    TaskExecutionEventRepository,
    UserRepository,
)


async def _create_task(db_session):
    user = await UserRepository.upsert_github_user(
        db_session,
        github_id=uuid.uuid4().hex,
        github_login="event-user",
        email=None,
    )
    instance = await AgentInstanceRepository.create(
        db_session,
        agent=AgentName.tela,
        client_id=uuid.uuid4().hex,
        display_name="Tela",
        user_id=user.id,
    )
    task = TaskRecord(
        agent=AgentName.tela,
        agent_instance_id=instance.id,
        category=TaskCategory.coding,
        question="Add backend event tests",
        status=TaskStatus.running,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)
    return task


async def test_task_execution_event_repository_creates_and_lists_events(db_session):
    task = await _create_task(db_session)
    first = await TaskExecutionEventRepository.create(
        db_session,
        task_id=task.id,
        event_type="model_call",
        agent=AgentName.tela,
        message="started",
        tokens=7,
        model="gpt-test",
    )
    second = await TaskExecutionEventRepository.create(
        db_session,
        task_id=task.id,
        event_type="tool_call",
        message="ran tests",
        tokens=3,
    )

    events = await TaskExecutionEventRepository.list_by_task(db_session, task.id)

    assert [event.id for event in events] == [first.id, second.id]
    assert events[0].agent == AgentName.tela
    assert events[0].model == "gpt-test"
    assert events[1].message == "ran tests"


async def test_task_execution_event_metadata_is_redacted_and_truncated(db_session):
    task = await _create_task(db_session)

    event = await TaskExecutionEventRepository.create(
        db_session,
        task_id=task.id,
        event_type="tool_result",
        safe_metadata={
            "github_token": "ghp_secret",
            "nested": {"password": "hidden", "summary": "x" * 300},
            "items": ["ok", "y" * 300],
        },
    )

    assert event.safe_metadata["github_token"] == "[REDACTED]"
    assert event.safe_metadata["nested"]["password"] == "[REDACTED]"
    assert event.safe_metadata["nested"]["summary"] == f"{'x' * 256}...[truncated]"
    assert event.safe_metadata["items"][1] == f"{'y' * 256}...[truncated]"


async def test_task_execution_event_aggregate_metrics(db_session):
    task = await _create_task(db_session)
    other_task = await _create_task(db_session)
    for event_type, tokens in [("model_call", 11), ("model_call", None), ("tool_call", 5)]:
        await TaskExecutionEventRepository.create(db_session, task_id=task.id, event_type=event_type, tokens=tokens)
    await TaskExecutionEventRepository.create(db_session, task_id=other_task.id, event_type="model_call", tokens=99)

    metrics = await TaskExecutionEventRepository.aggregate_metrics(db_session, task.id)

    assert metrics == {
        "event_count": 3,
        "total_tokens": 16,
        "event_counts_by_type": {"model_call": 2, "tool_call": 1},
    }
