from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from openai.types.chat.chat_completion_message_param import ChatCompletionMessageParam
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now() -> datetime:
    """Return the current UTC timestamp."""
    return datetime.now(timezone.utc)


class TaskStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    waiting_for_review = "waiting_for_review"
    merged = "merged"
    closed = "closed"
    failed = "failed"


class TaskCategory(str, enum.Enum):
    coding = "coding"
    pm = "product discovery"


TASK_STATUS_VARCHAR_LENGTH = 32
TASK_CATEGORY_VARCHAR_LENGTH = 32


class AgentName(str, enum.Enum):
    tela = "tela"
    sophie = "sophie"
    jules = "jules"
    marc = "marc"


class WorkspaceStatus(str, enum.Enum):
    idle = "idle"
    running = "running"
    inactive = "inactive"


class TaskWorkItemStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    ready_for_review = "ready_for_review"
    approved = "approved"
    closed = "closed"


class ProductProposalStatus(str, enum.Enum):
    """Business-level proposal lifecycle.

    proposed:
        Proposal exists and is waiting for human review.
    approved:
        Human approved the proposal, but planning may still be queued/running/failed.
    rejected:
        Human rejected the proposal.
    planned:
        Planning finished and produced a valid implementation plan with feature items.
    completed:
        All linked features are completed or closed.
    """

    proposed = "proposed"
    approved = "approved"
    rejected = "rejected"
    planned = "planned"
    completed = "completed"


class ProposalPlanningRunStatus(str, enum.Enum):
    """Execution state of a single planning attempt for an approved proposal.

    queued:
        Planning task row exists and is waiting to be dispatched/claimed.
    running:
        The worker has claimed the planning task and is generating features/items.
    failed:
        Dispatch, execution, or post-run validation failed.
    completed:
        The planning task succeeded and produced a valid plan.
    """

    queued = "queued"
    running = "running"
    failed = "failed"
    completed = "completed"


class FeatureStatus(str, enum.Enum):
    planned = "planned"
    in_progress = "in_progress"
    completed = "completed"
    closed = "closed"


class FeatureItemStatus(str, enum.Enum):
    pending = "pending"
    in_progress = "in_progress"
    completed = "completed"
    closed = "closed"


class GithubPullRequestFeedbackKind(str, enum.Enum):
    pr_comment = "pr_comment"
    pr_review = "pr_review"
    pr_review_comment = "pr_review_comment"
    pr_merge_conflict = "pr_merge_conflict"


class GithubPullRequestFeedbackStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    processed = "processed"
    ignored = "ignored"


class Base(DeclarativeBase):
    pass


class UserRecord(Base):
    __tablename__ = "user_account"
    __table_args__ = (UniqueConstraint("github_id", name="uq_user_github_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    github_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    github_login: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"), server_default="0.00")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now, server_default=func.now())


class AuthSessionRecord(Base):
    __tablename__ = "auth_session"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_account.id", ondelete="CASCADE"), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, server_default=func.now())


class AgentPurchaseRecord(Base):
    __tablename__ = "agent_purchase"
    __table_args__ = (Index("ix_agent_purchase_user_agent", "user_id", "agent"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_account.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_instance_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("agent_instance.id", ondelete="SET NULL"), nullable=True, index=True)
    agent: Mapped[AgentName] = mapped_column(Enum(AgentName, native_enum=False), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    purchased_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, server_default=func.now())


class AgentInstanceRecord(Base):
    __tablename__ = "agent_instance"
    __table_args__ = (
        Index("ix_agent_instance_agent_client", "agent", "client_id"),
        Index("ix_agent_instance_user_agent", "user_id", "agent"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user_account.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    agent: Mapped[AgentName] = mapped_column(
        Enum(AgentName, native_enum=False),
        nullable=False,
        index=True,
    )
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    client_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
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
    # Workspace is the durable per-agent-instance context chosen by the frontend.
    # It owns the repo/project binding; workers may transition status, but they
    # must not rewrite github_repo/project during task execution.
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
    project: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
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
        Index("ix_task_category_status", "category", "status"),
        Index(
            "uq_task_one_running_per_agent_instance",
            "agent_instance_id",
            unique=True,
            postgresql_where=text("status = 'running'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
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
    category: Mapped[TaskCategory] = mapped_column(
        Enum(
            TaskCategory,
            native_enum=False,
            length=TASK_CATEGORY_VARCHAR_LENGTH,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        index=True,
        default=TaskCategory.coding,
        server_default=TaskCategory.coding.value,
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    # Snapshot the repo/project chosen at task submission time so later workspace
    # edits do not rewrite historical task execution context. Legacy rows may still
    # leave these fields empty and rely on workspace fallback paths.
    repo: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    project: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    external_issue_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    # Unlike repo/project, the external PR URL remains task-scoped because GitHub
    # feedback resumes the same task/PR conversation instead of a workspace-wide thread.
    external_pull_request_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    checkpoint: Mapped[list[ChatCompletionMessageParam] | None] = mapped_column(JSON, nullable=True)
    dispatch_token: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    resume_status: Mapped[TaskStatus | None] = mapped_column(
        Enum(TaskStatus, native_enum=False, length=TASK_STATUS_VARCHAR_LENGTH),
        nullable=True,
        index=True,
    )
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


class ExecutionEventRecord(Base):
    __tablename__ = "execution_event"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ("
            "'agent_started', 'agent_finished', 'agent_failed', "
            "'agent_message', 'tool_call', 'tool_result'"
            ")",
            name="ck_execution_event_event_type",
        ),
        Index("ix_execution_event_task_created", "task_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("task.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )


class ProductProposalRecord(Base):
    __tablename__ = "product_proposal"
    __table_args__ = (
        Index("ix_product_proposal_status_created_at", "status", "created_at"),
        Index("ix_product_proposal_project_created_at", "project", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    plan_type: Mapped[str] = mapped_column(String(32), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user_account.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    repo: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    status: Mapped[ProductProposalStatus] = mapped_column(
        Enum(ProductProposalStatus, native_enum=False, length=32),
        nullable=False,
        index=True,
        default=ProductProposalStatus.proposed,
    )
    source_task_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("task.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
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


class ProposalPlanningRunRecord(Base):
    __tablename__ = "proposal_planning_run"
    __table_args__ = (
        UniqueConstraint("proposal_id", "attempt", name="uq_proposal_planning_run_attempt"),
        UniqueConstraint("task_id", name="uq_proposal_planning_run_task_id"),
        Index("ix_proposal_planning_run_proposal_created_at", "proposal_id", "created_at"),
        Index("ix_proposal_planning_run_status_created_at", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    proposal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("product_proposal.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("task.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    attempt: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[ProposalPlanningRunStatus] = mapped_column(
        Enum(ProposalPlanningRunStatus, native_enum=False, length=32),
        nullable=False,
        index=True,
        default=ProposalPlanningRunStatus.queued,
        server_default=ProposalPlanningRunStatus.queued.value,
    )
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


class FeatureRecord(Base):
    __tablename__ = "feature"
    __table_args__ = (
        Index("ix_feature_status_created_at", "status", "created_at"),
        Index("ix_feature_project_created_at", "project", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    proposal_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("product_proposal.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    project: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    status: Mapped[FeatureStatus] = mapped_column(
        Enum(FeatureStatus, native_enum=False, length=32),
        nullable=False,
        index=True,
        default=FeatureStatus.planned,
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


class FeatureItemRecord(Base):
    __tablename__ = "feature_item"
    __table_args__ = (
        UniqueConstraint("feature_id", "order_index", name="uq_feature_item_feature_order"),
        Index("ix_feature_item_feature_status", "feature_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    feature_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("feature.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[FeatureItemStatus] = mapped_column(
        Enum(FeatureItemStatus, native_enum=False, length=32),
        nullable=False,
        index=True,
        default=FeatureItemStatus.pending,
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("task.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
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
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TaskExecutionEventRecord(Base):
    __tablename__ = "task_execution_event"
    __table_args__ = (
        Index("ix_task_execution_event_task_created_at", "task_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("task.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    agent: Mapped[AgentName | None] = mapped_column(
        Enum(AgentName, native_enum=False),
        nullable=True,
        index=True,
    )
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Store only scrubbed, allow-listed context here. Do not persist raw prompts,
    # tool arguments, credentials, environment variables, or other sensitive inputs.
    safe_metadata: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )


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


class GithubPullRequestFeedbackRecord(Base):
    __tablename__ = "github_pull_request_feedback"
    __table_args__ = (
        UniqueConstraint(
            "task_id",
            "kind",
            "external_id",
            name="uq_github_pull_request_feedback_task_source",
        ),
        Index("ix_github_pull_request_feedback_task_status", "task_id", "status", "created_at"),
        Index("ix_github_pull_request_feedback_pull_request", "pull_request_number", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("task.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    pull_request_number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    kind: Mapped[GithubPullRequestFeedbackKind] = mapped_column(
        Enum(GithubPullRequestFeedbackKind, native_enum=False, length=32),
        nullable=False,
        index=True,
    )
    status: Mapped[GithubPullRequestFeedbackStatus] = mapped_column(
        Enum(GithubPullRequestFeedbackStatus, native_enum=False, length=32),
        nullable=False,
        index=True,
        default=GithubPullRequestFeedbackStatus.pending,
    )
    # External GitHub ids are mostly numeric, but merge-conflict feedback uses a
    # synthetic hash key so we persist all source ids as text.
    external_id: Mapped[str] = mapped_column(String(128), nullable=False)
    author: Mapped[str | None] = mapped_column(String(255), nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_state: Mapped[str | None] = mapped_column(String(64), nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    line: Mapped[int | None] = mapped_column(Integer, nullable=True)
    original_line: Mapped[int | None] = mapped_column(Integer, nullable=True)
    commit_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    html_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    external_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    external_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ignored_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
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
