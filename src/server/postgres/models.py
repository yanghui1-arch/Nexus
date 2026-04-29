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
    Integer,
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
    waiting = "waiting"
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


class TaskWorkItemStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    ready_for_review = "ready_for_review"
    approved = "approved"
    changes_requested = "changes_requested"


class VirtualPullRequestStatus(str, enum.Enum):
    ready_for_review = "ready_for_review"
    approved = "approved"
    changes_requested = "changes_requested"


class VirtualPullRequestReviewDecision(str, enum.Enum):
    approved = "approved"
    changes_requested = "changes_requested"


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
    # Persisted replay checkpoint messages for task recovery.
    checkpoint: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)
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


class TaskWorkItemRecord(Base):
    __tablename__ = "task_work_item"
    __table_args__ = (
        UniqueConstraint("task_id", "order_index", name="uq_task_work_item_task_order"),
        Index("ix_task_work_item_task_status", "task_id", "status"),
        Index(
            "uq_task_work_item_one_running_per_task",
            "task_id",
            unique=True,
            postgresql_where=text("status = 'running'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("task.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[TaskWorkItemStatus] = mapped_column(
        Enum(TaskWorkItemStatus, native_enum=False, length=32),
        nullable=False,
        index=True,
        default=TaskWorkItemStatus.pending,
    )
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    base_commit: Mapped[str | None] = mapped_column(String(64), nullable=True)
    head_commit: Mapped[str | None] = mapped_column(String(64), nullable=True)
    local_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
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


class VirtualPullRequestRecord(Base):
    __tablename__ = "virtual_pull_request"
    __table_args__ = (
        UniqueConstraint("work_item_id", name="uq_virtual_pull_request_work_item"),
        Index("ix_virtual_pull_request_task_status", "task_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("task.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    work_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("task_work_item.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[VirtualPullRequestStatus] = mapped_column(
        Enum(VirtualPullRequestStatus, native_enum=False, length=32),
        nullable=False,
        index=True,
        default=VirtualPullRequestStatus.ready_for_review,
    )
    base_commit: Mapped[str] = mapped_column(String(64), nullable=False)
    head_commit: Mapped[str] = mapped_column(String(64), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    changed_files: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
        server_default=text("'[]'::json"),
    )
    additions: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    deletions: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    diff: Mapped[str | None] = mapped_column(Text, nullable=True)
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


class VirtualPullRequestReviewRecord(Base):
    __tablename__ = "virtual_pull_request_review"
    __table_args__ = (
        Index("ix_virtual_pull_request_review_task", "task_id", "created_at"),
        Index("ix_virtual_pull_request_review_virtual_pr", "virtual_pr_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("task.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    virtual_pr_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("virtual_pull_request.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    decision: Mapped[VirtualPullRequestReviewDecision] = mapped_column(
        Enum(VirtualPullRequestReviewDecision, native_enum=False, length=32),
        nullable=False,
        index=True,
    )
    reviewer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )
