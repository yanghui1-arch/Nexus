from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from src.server.postgres.models import Base


_REQUIRED_SCHEMA: dict[str, set[str]] = {
    "agent_instance": {"id", "agent", "client_id", "is_active"},
    "workspace": {"id", "agent_instance_id", "workspace_key", "status"},
    "task": {
        "id",
        "agent",
        "agent_instance_id",
        "question",
        "status",
        "requested_current_session_ctx",
        "requested_history_session_ctx",
        "checkpoint",
        "dispatch_token",
        "lease_expires_at",
    },
}

class Database:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None

    async def connect(self) -> None:
        if self._engine is not None:
            return
        self._engine = create_async_engine(
            self._database_url,
            pool_pre_ping=True,
        )
        self._session_factory = async_sessionmaker(self._engine, expire_on_commit=False)

    async def create_schema(self) -> None:
        if self._engine is None:
            raise RuntimeError("Database engine is not initialized. Call connect() first.")

        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await conn.execute(
                text(
                    "ALTER TABLE task ADD COLUMN IF NOT EXISTS requested_current_session_ctx JSON "
                    "NOT NULL DEFAULT '[]'::json"
                )
            )
            await conn.execute(
                text(
                    "ALTER TABLE task ADD COLUMN IF NOT EXISTS requested_history_session_ctx JSON "
                    "NOT NULL DEFAULT '[]'::json"
                )
            )
            await conn.execute(
                text(
                    "ALTER TABLE task ADD COLUMN IF NOT EXISTS checkpoint JSON"
                )
            )
            await conn.execute(
                text(
                    "ALTER TABLE task ADD COLUMN IF NOT EXISTS dispatch_token VARCHAR(64)"
                )
            )
            await conn.execute(
                text(
                    "ALTER TABLE task ADD COLUMN IF NOT EXISTS lease_expires_at TIMESTAMPTZ"
                )
            )
            await conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_task_one_running_per_agent_instance "
                    "ON task (agent_instance_id) WHERE status = 'running'"
                )
            )
            await conn.run_sync(self._assert_schema_compatible)

    @staticmethod
    def _assert_schema_compatible(sync_conn) -> None:
        inspector = inspect(sync_conn)

        for table_name, required_columns in _REQUIRED_SCHEMA.items():
            if not inspector.has_table(table_name):
                raise RuntimeError(
                    f"Required table `{table_name}` is missing. Run migrations or recreate database schema."
                )

            existing_columns = {col["name"] for col in inspector.get_columns(table_name)}
            missing_columns = required_columns - existing_columns
            if missing_columns:
                missing = ", ".join(sorted(missing_columns))
                raise RuntimeError(
                    f"Table `{table_name}` is missing required columns: {missing}. "
                    "Run migrations or recreate database schema."
                )

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        if self._session_factory is None:
            raise RuntimeError("Session factory is not initialized. Call connect() first.")
        async with self._session_factory() as session:
            yield session

    async def ping(self) -> bool:
        if self._engine is None:
            return False
        try:
            async with self._engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except SQLAlchemyError:
            return False

    async def disconnect(self) -> None:
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None


