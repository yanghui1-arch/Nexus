from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    JSON,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TaskStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    waiting_for_merge = "waiting_for_merge"
    merged = "merged"
    closed = "closed"
    failed = "failed"


TASK_STATUS_VARCHAR_LENGTH = 32


class AgentName(str, enum.Enum):
    tela = "tela"
    sophie = "sophie"


class WorkspaceStatus(str, enum.Enum):
    idle = "idle"
    running = "running"
    inactive = "inactive"


class Base(DeclarativeBase):
    pass


class AgentInstanceRecord(Base):
    __tablename__ = "agent_instance"
    __table_args__ = (
        Index("ix_agent_instance_agent_client", "agent", "client_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    agent: Mapped[AgentName] = mapped_column(
        Enum(AgentName, native_enum=False),
        nullable=False,
        index=True,
    )
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    client_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
        server_default=func.now(),
    )


class WorkspaceRecord(Base):
    __tablename__ = "workspace"
    __table_args__ = (
        UniqueConstraint("agent_instance_id", name="uq_workspace_agent_instance_id"),
        UniqueConstraint("workspace_key", name="uq_workspace_workspace_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    agent_instance_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agent_instance.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workspace_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    github_repo: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    docker_container_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    docker_volume_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[WorkspaceStatus] = mapped_column(
        Enum(WorkspaceStatus, native_enum=False),
        nullable=False,
        default=WorkspaceStatus.idle,
    )
    last_used_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
        server_default=func.now(),
    )


class TaskRecord(Base):
    __tablename__ = "task"
    __table_args__ = (
        Index("ix_task_agent_instance_status", "agent_instance_id", "status"),
        Index(
            "uq_task_one_running_per_agent_instance",
            "agent_instance_id",
            unique=True,
            postgresql_where=text("status = 'running'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # agent name
    agent: Mapped[AgentName] = mapped_column(
        Enum(AgentName, native_enum=False),
        nullable=False,
        index=True,
    )
    agent_instance_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agent_instance.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    repo: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    project: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    requested_current_session_ctx: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
        server_default=text("'[]'::json"),
    )
    requested_history_session_ctx: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
        server_default=text("'[]'::json"),
    )
    # Compatible with TaskCheckpoint
    checkpoint: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    # Lease token is regenerated on every dispatch attempt and must match when worker claims the task.
    dispatch_token: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    # Lease expiry marks when a dispatched/running task is considered orphaned and recoverable.
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus, native_enum=False, length=TASK_STATUS_VARCHAR_LENGTH),
        nullable=False,
        index=True,
        default=TaskStatus.queued,
    )
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
        server_default=func.now(),
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TaskActivityRecord(Base):
    __tablename__ = "task_activity"
    __table_args__ = (
        Index("ix_task_activity_task_created_at", "task_id", "created_at"),
        Index("ix_task_activity_agent_created_at", "agent", "created_at"),
        Index("ix_task_activity_agent_instance_created_at", "agent_instance_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("task.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    agent: Mapped[AgentName] = mapped_column(
        Enum(AgentName, native_enum=False),
        nullable=False,
        index=True,
    )
    agent_instance_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agent_instance.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    tools: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    tool_args: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )
