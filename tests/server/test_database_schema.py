import pytest
from sqlalchemy import create_engine, inspect

from src.server.postgres.database import Database
from src.server.postgres.models import Base, ExecutionEventRecord, TaskRecord


def test_ensure_execution_event_table_backfills_existing_schema():
    engine = create_engine("sqlite:///:memory:")
    try:
        TaskRecord.metadata.create_all(engine)
        ExecutionEventRecord.__table__.drop(engine)

        with engine.begin() as conn:
            assert not inspect(conn).has_table("execution_event")
            Database._ensure_execution_event_table(conn)

            inspector = inspect(conn)
            assert inspector.has_table("execution_event")
            assert {
                "id",
                "task_id",
                "event_type",
                "message",
                "payload",
                "created_at",
            }.issubset({column["name"] for column in inspector.get_columns("execution_event")})
    finally:
        engine.dispose()


def test_schema_validation_still_requires_task_table():
    engine = create_engine("sqlite:///:memory:")
    try:
        with engine.begin() as conn:
            for table in Base.metadata.sorted_tables:
                if table.name not in {"task", "execution_event"}:
                    table.create(conn)
            ExecutionEventRecord.__table__.create(conn)
            with pytest.raises(RuntimeError, match="Required table `task` is missing"):
                Database._assert_schema_compatible(conn)
    finally:
        engine.dispose()
