from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from src.server.postgres.models import Base, TASK_CATEGORY_VARCHAR_LENGTH, TASK_STATUS_VARCHAR_LENGTH


_REQUIRED_SCHEMA: dict[str, set[str]] = {
    "user_account": {"id", "github_id", "github_login", "balance"},
    "auth_session": {"token_hash", "user_id", "expires_at"},
    "agent_purchase": {"id", "user_id", "agent", "price", "agent_instance_id"},
    "agent_instance": {"id", "user_id", "agent", "client_id", "is_active", "expires_at"},
    "workspace": {
        "id",
        "agent_instance_id",
        "workspace_key",
        "github_repo",
        "project",
        "status",
    },
    "task": {
        "id",
        "agent",
        "agent_instance_id",
        "category",
        "question",
        "external_issue_url",
        "external_pull_request_url",
        "status",
        "resume_status",
        "checkpoint",
        "dispatch_token",
        "lease_expires_at",
    },
    "product_proposal": {
        "id",
        "title",
        "plan_type",
        "summary",
        "answer",
        "user_id",
        "project",
        "repo",
        "status",
        "source_task_id",
    },
    "proposal_planning_run": {
        "id",
        "proposal_id",
        "task_id",
        "attempt",
        "status",
        "error",
    },
    "feature": {
        "id",
        "proposal_id",
        "title",
        "description",
        "project",
        "status",
    },
    "feature_item": {
        "id",
        "feature_id",
        "order_index",
        "title",
        "description",
        "status",
        "task_id",
    },
    "task_work_item": {
        "id",
        "task_id",
        "order_index",
        "title",
        "description",
        "status",
        "summary",
        "base_commit",
        "head_commit",
        "local_path",
    },
    "github_pull_request_feedback": {
        "id",
        "task_id",
        "pull_request_number",
        "kind",
        "status",
        "external_id",
        "author",
        "body",
        "review_state",
        "file_path",
        "line",
        "original_line",
        "commit_id",
        "html_url",
        "external_created_at",
        "external_updated_at",
        "ignored_reason",
        "processed_at",
        "payload",
    },
}


class Database:
    def __init__(self, database_url: str) -> None:
        """Initialize the repository object."""
        self._database_url = database_url
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None

    async def connect(self) -> None:
        """Open database connections and initialize the engine."""
        if self._engine is not None:
            return
        self._engine = create_async_engine(
            self._database_url,
            pool_pre_ping=True,
        )
        self._session_factory = async_sessionmaker(self._engine, expire_on_commit=False)

    async def create_schema(self) -> None:
        """Create database schema objects when needed."""
        if self._engine is None:
            raise RuntimeError("Database engine is not initialized. Call connect() first.")

        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            if conn.dialect.name == "postgresql":
                # Older deployments stored GitHub feedback source ids as BIGINT.
                # Merge-conflict feedback now uses hashed episode ids, so migrate
                # the column to text before the poller starts reading or writing it.
                await conn.execute(
                    text(
                        "ALTER TABLE github_pull_request_feedback "
                        "ALTER COLUMN external_id TYPE VARCHAR(128) "
                        "USING external_id::text"
                    )
                )
            await conn.execute(text("ALTER TABLE workspace ADD COLUMN IF NOT EXISTS github_repo VARCHAR(255)"))
            await conn.execute(text("ALTER TABLE workspace ADD COLUMN IF NOT EXISTS project VARCHAR(255)"))
            await conn.execute(
                text(
                    "ALTER TABLE product_proposal "
                    "ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES user_account(id) ON DELETE CASCADE"
                )
            )
            await conn.execute(
                text(
                    "UPDATE product_proposal "
                    "SET user_id = ("
                    "SELECT ai.user_id "
                    "FROM task t "
                    "JOIN agent_instance ai ON ai.id = t.agent_instance_id "
                    "WHERE t.id = product_proposal.source_task_id"
                    ") "
                    "WHERE user_id IS NULL AND source_task_id IS NOT NULL"
                )
            )
            await conn.execute(
                text("CREATE INDEX IF NOT EXISTS ix_product_proposal_user_id ON product_proposal (user_id)")
            )
            unresolved_proposal_owner_count = int(
                (
                    await conn.execute(
                        text("SELECT COUNT(*) FROM product_proposal WHERE user_id IS NULL")
                    )
                ).scalar_one()
            )
            if unresolved_proposal_owner_count > 0:
                raise RuntimeError(
                    "product_proposal contains rows without a resolvable user_id. "
                    "Backfill those rows before continuing."
                )
            if conn.dialect.name == "postgresql":
                await conn.execute(text("ALTER TABLE product_proposal ALTER COLUMN user_id SET NOT NULL"))
            await conn.execute(
                text(
                    "ALTER TABLE task ADD COLUMN IF NOT EXISTS "
                    f"category VARCHAR({TASK_CATEGORY_VARCHAR_LENGTH}) DEFAULT 'coding' NOT NULL"
                )
            )
            await conn.execute(text("UPDATE task SET category = 'coding' WHERE category IS NULL"))
            await conn.execute(text("ALTER TABLE task ADD COLUMN IF NOT EXISTS checkpoint JSON"))
            await conn.execute(text("ALTER TABLE task ADD COLUMN IF NOT EXISTS dispatch_token VARCHAR(64)"))
            await conn.execute(text("ALTER TABLE task ADD COLUMN IF NOT EXISTS lease_expires_at TIMESTAMPTZ"))
            await conn.execute(text("ALTER TABLE task ADD COLUMN IF NOT EXISTS resume_status VARCHAR(32)"))
            await conn.execute(
                text("ALTER TABLE task ADD COLUMN IF NOT EXISTS external_issue_url VARCHAR(1024)")
            )
            await conn.execute(
                text(
                    "ALTER TABLE task ADD COLUMN IF NOT EXISTS external_pull_request_url VARCHAR(1024)"
                )
            )
            await conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_task_one_running_per_agent_instance "
                    "ON task (agent_instance_id) WHERE status = 'running'"
                )
            )
            await conn.execute(text("ALTER TABLE agent_instance DROP COLUMN IF EXISTS github_repo"))
            await conn.execute(text("ALTER TABLE agent_instance DROP COLUMN IF EXISTS project"))
            await conn.execute(text("ALTER TABLE task ALTER COLUMN status DROP DEFAULT"))
            await conn.execute(
                text(
                    f"ALTER TABLE task ALTER COLUMN status TYPE VARCHAR({TASK_STATUS_VARCHAR_LENGTH}) "
                    "USING status::text"
                )
            )
            await conn.execute(text("ALTER TABLE task ALTER COLUMN status SET DEFAULT 'queued'"))
            await conn.execute(
                text("UPDATE task SET status = 'waiting_for_review' WHERE status = 'completed'")
            )
            await conn.execute(
                text("UPDATE task SET status = 'waiting_for_review' WHERE status = 'waiting'")
            )
            await conn.execute(
                text("UPDATE task SET status = 'waiting_for_review' WHERE status = 'waiting_for_merge'")
            )
            await conn.execute(
                text(
                    "UPDATE task SET resume_status = 'waiting_for_review' "
                    "WHERE resume_status = 'waiting_for_merge'"
                )
            )
            await conn.execute(
                text(
                    "UPDATE task_work_item SET status = 'ready_for_review' "
                    "WHERE status = 'changes_requested'"
                )
            )
            await conn.execute(
                text(
                    "UPDATE product_proposal p "
                    "SET status = CASE "
                    "WHEN EXISTS ("
                    "SELECT 1 FROM feature_item fi "
                    "JOIN feature f ON fi.feature_id = f.id "
                    "WHERE f.proposal_id = p.id"
                    ") "
                    "AND NOT EXISTS ("
                    "SELECT 1 FROM feature f "
                    "WHERE f.proposal_id = p.id AND f.status NOT IN ('completed', 'closed')"
                    ") THEN 'completed' "
                    "WHEN EXISTS ("
                    "SELECT 1 FROM feature_item fi "
                    "JOIN feature f ON fi.feature_id = f.id "
                    "WHERE f.proposal_id = p.id"
                    ") THEN 'planned' "
                    "ELSE p.status "
                    "END "
                    "WHERE p.status <> 'rejected'"
                )
            )
            await conn.execute(text("ALTER TABLE user_account ADD COLUMN IF NOT EXISTS balance NUMERIC(12, 2) DEFAULT 0.00 NOT NULL"))
            await conn.execute(
                text(
                    "DO $$ BEGIN "
                    "IF EXISTS ("
                    "SELECT 1 FROM information_schema.columns "
                    "WHERE table_name = 'user_account' AND column_name = 'balance_cents'"
                    ") THEN "
                    "UPDATE user_account SET balance = balance_cents / 100.0 "
                    "WHERE balance_cents IS NOT NULL; "
                    "END IF; "
                    "END $$;"
                )
            )
            await conn.execute(text("ALTER TABLE agent_purchase ADD COLUMN IF NOT EXISTS price NUMERIC(12, 2)"))
            await conn.execute(
                text(
                    "DO $$ BEGIN "
                    "IF EXISTS ("
                    "SELECT 1 FROM information_schema.columns "
                    "WHERE table_name = 'agent_purchase' AND column_name = 'price_cents'"
                    ") THEN "
                    "UPDATE agent_purchase SET price = price_cents / 100.0 "
                    "WHERE price_cents IS NOT NULL AND price IS NULL; "
                    "END IF; "
                    "END $$;"
                )
            )
            await conn.execute(text("ALTER TABLE agent_purchase ALTER COLUMN price SET NOT NULL"))
            await conn.execute(text("ALTER TABLE agent_instance ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ"))
            await conn.execute(text("ALTER TABLE agent_instance ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES user_account(id) ON DELETE CASCADE"))
            await conn.execute(text("ALTER TABLE agent_purchase ADD COLUMN IF NOT EXISTS agent_instance_id UUID REFERENCES agent_instance(id) ON DELETE SET NULL"))
            await conn.execute(
                text(
                    "UPDATE agent_instance ai SET user_id = ap.user_id "
                    "FROM agent_purchase ap "
                    "WHERE ap.agent_instance_id = ai.id AND ai.user_id IS NULL"
                )
            )
            await conn.execute(text("ALTER TABLE agent_instance ALTER COLUMN user_id SET NOT NULL"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_agent_instance_user_id ON agent_instance (user_id)"))
            await conn.execute(text("ALTER TABLE agent_purchase DROP COLUMN IF EXISTS expires_at"))
            await conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_task_work_item_one_running_per_task "
                    "ON task_work_item (task_id) WHERE status = 'running'"
                )
            )
            await conn.run_sync(self._assert_schema_compatible)

    @staticmethod
    def _assert_schema_compatible(sync_conn) -> None:
        """Validate that the existing database schema is compatible."""
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
        """Yield a transactional database session."""
        if self._session_factory is None:
            raise RuntimeError("Session factory is not initialized. Call connect() first.")
        async with self._session_factory() as session:
            yield session

    async def ping(self) -> bool:
        """Check whether the database connection is healthy."""
        if self._engine is None:
            return False
        try:
            async with self._engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except SQLAlchemyError:
            return False

    async def disconnect(self) -> None:
        """Close database connections and release resources."""
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None
