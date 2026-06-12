from sqlalchemy import JSON, DateTime, Integer, String, Text

from src.server.postgres.models import AgentName, TaskExecutionEventRecord


def test_task_execution_event_schema_captures_safe_execution_summary():
    table = TaskExecutionEventRecord.__table__

    assert table.name == "task_execution_event"
    assert set(table.columns.keys()) == {
        "id",
        "task_id",
        "event_type",
        "agent",
        "message",
        "safe_metadata",
        "tokens",
        "model",
        "created_at",
    }
    assert next(iter(table.c.task_id.foreign_keys)).column.table.name == "task"
    assert isinstance(table.c.event_type.type, String)
    assert table.c.event_type.type.length == 64
    assert table.c.agent.type.enum_class is AgentName
    assert isinstance(table.c.message.type, Text)
    assert isinstance(table.c.safe_metadata.type, JSON)
    assert isinstance(table.c.tokens.type, Integer)
    assert isinstance(table.c.model.type, String)
    assert table.c.model.type.length == 128
    assert isinstance(table.c.created_at.type, DateTime)
    assert table.c.created_at.type.timezone is True


def test_task_execution_event_indexes_task_timeline_without_raw_inputs():
    table = TaskExecutionEventRecord.__table__

    index_columns = {
        index.name: [column.name for column in index.columns]
        for index in table.indexes
    }

    assert index_columns["ix_task_execution_event_task_created_at"] == [
        "task_id",
        "created_at",
    ]
    assert "raw_arguments" not in table.c
    assert "raw_prompt" not in table.c
    assert "parameters" not in table.c
