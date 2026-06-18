from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

from src.server.postgres.models import (
    AgentInstanceRecord,
    ProductProposalRecord,
    ProductProposalStatus,
    ProposalPlanningRunRecord,
    ProposalPlanningRunStatus,
    FeatureItemRecord,
    FeatureItemStatus,
    FeatureRecord,
    FeatureStatus,
    TaskCategory,
    TaskExecutionEventRecord,
    TaskRecord,
    TaskStatus,
    TaskWorkItemRecord,
    TaskWorkItemStatus,
    WorkspaceRecord,
)


class AgentKind(str, Enum):
    tela = "tela"
    sophie = "sophie"
    jules = "jules"
    marc = "marc"


class ProductProposalCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    plan_type: str = Field(min_length=1, max_length=32)
    summary: str = Field(min_length=1)
    answer: str = Field(min_length=1)
    project: str | None = None
    repo: str | None = None
    source_task_id: uuid.UUID | None = None

    @field_validator("title", "plan_type", "summary", "answer")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("value cannot be empty")
        return stripped

    @field_validator("project", "repo")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class ProductProposalStatusUpdateRequest(BaseModel):
    status: ProductProposalStatus

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: ProductProposalStatus) -> ProductProposalStatus:
        if value not in {
            ProductProposalStatus.approved,
            ProductProposalStatus.rejected,
            ProductProposalStatus.planned,
        }:
            raise ValueError("status must be approved, rejected, or planned")
        return value


class ProposalPlanningRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    proposal_id: uuid.UUID
    task_id: uuid.UUID
    attempt: int
    status: ProposalPlanningRunStatus
    error: str | None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    @classmethod
    def from_record(cls, run: ProposalPlanningRunRecord) -> "ProposalPlanningRunResponse":
        return cls(
            id=run.id,
            proposal_id=run.proposal_id,
            task_id=run.task_id,
            attempt=run.attempt,
            status=run.status,
            error=run.error,
            created_at=run.created_at,
            updated_at=run.updated_at,
            started_at=run.started_at,
            finished_at=run.finished_at,
        )


class ProductProposalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    plan_type: str
    summary: str
    answer: str
    project: str | None
    repo: str | None
    status: ProductProposalStatus
    source_task_id: uuid.UUID | None
    latest_planning_run: ProposalPlanningRunResponse | None = None
    latest_planning_task_exists: bool | None = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_record(
        cls,
        proposal: ProductProposalRecord,
        *,
        latest_planning_run: ProposalPlanningRunRecord | None = None,
        latest_planning_task_exists: bool | None = None,
    ) -> "ProductProposalResponse":
        return cls(
            id=proposal.id,
            title=proposal.title,
            plan_type=proposal.plan_type,
            summary=proposal.summary,
            answer=proposal.answer,
            project=proposal.project,
            repo=proposal.repo,
            status=proposal.status,
            source_task_id=proposal.source_task_id,
            latest_planning_run=ProposalPlanningRunResponse.from_record(latest_planning_run)
            if latest_planning_run is not None
            else None,
            latest_planning_task_exists=latest_planning_task_exists,
            created_at=proposal.created_at,
            updated_at=proposal.updated_at,
        )


class FeatureItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    feature_id: uuid.UUID
    order_index: int
    title: str
    description: str
    status: FeatureItemStatus
    task_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    @classmethod
    def from_record(cls, item: FeatureItemRecord) -> "FeatureItemResponse":
        return cls(
            id=item.id,
            feature_id=item.feature_id,
            order_index=item.order_index,
            title=item.title,
            description=item.description,
            status=item.status,
            task_id=item.task_id,
            created_at=item.created_at,
            updated_at=item.updated_at,
            started_at=item.started_at,
            finished_at=item.finished_at,
        )


class FeatureResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    proposal_id: uuid.UUID | None
    title: str
    description: str
    project: str | None
    status: FeatureStatus
    created_at: datetime
    updated_at: datetime
    items: list[FeatureItemResponse] | None = None

    @classmethod
    def from_record(
        cls,
        feature: FeatureRecord,
        items: list[FeatureItemRecord] | None = None,
    ) -> "FeatureResponse":
        return cls(
            id=feature.id,
            proposal_id=feature.proposal_id,
            title=feature.title,
            description=feature.description,
            project=feature.project,
            status=feature.status,
            created_at=feature.created_at,
            updated_at=feature.updated_at,
            items=[FeatureItemResponse.from_record(item) for item in items] if items is not None else None,
        )


class TaskCreateRequest(BaseModel):
    agent_instance_id: uuid.UUID
    agent: AgentKind
    question: str = Field(min_length=1)
    external_issue_url: str | None = Field(default=None, max_length=1024)

    @field_validator("question")
    @classmethod
    def validate_question(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("question cannot be empty")
        return stripped

    @field_validator("external_issue_url")
    @classmethod
    def validate_external_issue_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class WorkspaceUpdateRequest(BaseModel):
    github_repo: str | None = None
    project: str | None = None

    @field_validator("github_repo")
    @classmethod
    def validate_github_repo(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("project")
    @classmethod
    def validate_project(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class TaskConsultRequest(BaseModel):
    message: str = Field(min_length=1)

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("message cannot be empty")
        return stripped


class TaskSubmitResponse(BaseModel):
    task_id: uuid.UUID
    agent_instance_id: uuid.UUID
    category: TaskCategory
    status: TaskStatus


class FeatureItemRetryTaskResponse(BaseModel):
    feature_item: FeatureItemResponse
    task: TaskSubmitResponse


class TaskConsultResponse(BaseModel):
    task_id: uuid.UUID
    status: TaskStatus
    reply: str
    timestamp: datetime


class TaskStatusUpdateRequest(BaseModel):
    status: TaskStatus

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: TaskStatus) -> TaskStatus:
        if value not in {TaskStatus.waiting_for_review, TaskStatus.merged, TaskStatus.closed}:
            raise ValueError("status must be waiting_for_review, merged, or closed")
        return value


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    agent: str
    agent_instance_id: uuid.UUID
    category: TaskCategory
    question: str
    repo: str | None
    project: str | None
    external_issue_url: str | None
    external_pull_request_url: str | None
    status: TaskStatus
    result: str | None
    error: str | None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    @classmethod
    def from_record(
        cls,
        task: TaskRecord,
        *,
        repo: str | None | object = ...,
        project: str | None | object = ...,
    ) -> "TaskResponse":
        # Routes may override repo/project so one API payload can represent both:
        # - current tasks that snapshot repo/project on the task row
        # - legacy tasks that still need workspace fallback at read time
        resolved_repo = task.repo if repo is ... else repo
        resolved_project = task.project if project is ... else project
        return cls(
            id=task.id,
            agent=task.agent.value,
            agent_instance_id=task.agent_instance_id,
            category=task.category,
            question=task.question,
            repo=resolved_repo,
            project=resolved_project,
            external_issue_url=getattr(task, "external_issue_url", None),
            external_pull_request_url=getattr(task, "external_pull_request_url", None),
            status=task.status,
            result=task.result,
            error=task.error,
            created_at=task.created_at,
            updated_at=task.updated_at,
            started_at=task.started_at,
            finished_at=task.finished_at,
        )


class TaskExecutionEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    task_id: uuid.UUID
    event_type: str
    agent: str | None
    message: str | None
    safe_metadata: dict[str, Any] | None
    tokens: int | None
    model: str | None
    created_at: datetime

    @classmethod
    def from_record(cls, event: TaskExecutionEventRecord) -> "TaskExecutionEventResponse":
        return cls(
            id=event.id,
            task_id=event.task_id,
            event_type=event.event_type,
            agent=event.agent.value if event.agent is not None else None,
            message=event.message,
            safe_metadata=event.safe_metadata,
            tokens=event.tokens,
            model=event.model,
            created_at=event.created_at,
        )


class TaskMessage(BaseModel):
    timestamp: str
    status: str = Field(validation_alias=AliasChoices("status", "event"))
    description: str | None = Field(default=None, validation_alias=AliasChoices("description", "content"))
    data: dict[str, Any] | None = None
    meta: dict[str, Any] | None = None


class TaskExecutionStatsResponse(BaseModel):
    event_count: int = 0
    total_tokens: int = 0
    first_event_at: datetime | None = None
    last_event_at: datetime | None = None
    duration_seconds: float | None = None
    model: str = "unknown"

    @classmethod
    def from_events(cls, events: list[Any]) -> "TaskExecutionStatsResponse":
        """Build task execution statistics, preserving an explicit empty state."""
        if not events:
            return cls()
        first_event_at = min(event.created_at for event in events)
        last_event_at = max(event.created_at for event in events)
        models = {event.model for event in events if event.model}
        return cls(
            event_count=len(events),
            total_tokens=sum(event.tokens or 0 for event in events),
            first_event_at=first_event_at,
            last_event_at=last_event_at,
            duration_seconds=(last_event_at - first_event_at).total_seconds(),
            model=models.pop() if len(models) == 1 else "unknown",
        )


class TaskWorkItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    task_id: uuid.UUID
    order_index: int
    title: str
    description: str
    status: TaskWorkItemStatus
    summary: str | None
    base_commit: str | None
    head_commit: str | None
    local_path: str | None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    @classmethod
    def from_record(cls, work_item: TaskWorkItemRecord) -> "TaskWorkItemResponse":
        return cls(
            id=work_item.id,
            task_id=work_item.task_id,
            order_index=work_item.order_index,
            title=work_item.title,
            description=work_item.description,
            status=work_item.status,
            summary=work_item.summary,
            base_commit=work_item.base_commit,
            head_commit=work_item.head_commit,
            local_path=work_item.local_path,
            created_at=work_item.created_at,
            updated_at=work_item.updated_at,
            started_at=work_item.started_at,
            finished_at=work_item.finished_at,
        )


class AgentInstanceCreateRequest(BaseModel):
    agent: AgentKind
    client_id: str = Field(min_length=1)
    display_name: str | None = None
    is_active: bool = True


class AgentInstanceDisplayNameUpdateRequest(BaseModel):
    display_name: str | None = None

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class AgentInstanceStatusUpdateRequest(BaseModel):
    is_active: bool


class WorkspaceResponse(BaseModel):
    id: uuid.UUID
    agent_instance_id: uuid.UUID
    workspace_key: str
    github_repo: str | None
    project: str | None
    docker_container_id: str | None
    docker_volume_name: str | None
    status: str
    last_used_at: datetime
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_record(cls, workspace: WorkspaceRecord) -> "WorkspaceResponse":
        return cls(
            id=workspace.id,
            agent_instance_id=workspace.agent_instance_id,
            workspace_key=workspace.workspace_key,
            github_repo=workspace.github_repo,
            project=workspace.project,
            docker_container_id=workspace.docker_container_id,
            docker_volume_name=workspace.docker_volume_name,
            status=workspace.status.value,
            last_used_at=workspace.last_used_at,
            created_at=workspace.created_at,
            updated_at=workspace.updated_at,
        )


class AgentInstanceResponse(BaseModel):
    id: uuid.UUID
    agent: str
    client_id: str
    display_name: str | None
    expires_at: datetime | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    workspace: WorkspaceResponse | None = None

    @classmethod
    def from_record(
        cls,
        instance: AgentInstanceRecord,
        workspace: WorkspaceRecord | None = None,
    ) -> "AgentInstanceResponse":
        return cls(
            id=instance.id,
            agent=instance.agent.value,
            client_id=instance.client_id,
            display_name=instance.display_name,
            expires_at=instance.expires_at,
            is_active=instance.is_active,
            created_at=instance.created_at,
            updated_at=instance.updated_at,
            workspace=WorkspaceResponse.from_record(workspace) if workspace else None,
        )


class UserResponse(BaseModel):
    id: uuid.UUID
    github_login: str
    email: str | None
    balance: Decimal


class RechargeRequest(BaseModel):
    amount: Decimal = Field(gt=Decimal("0"), le=Decimal("1000000"), decimal_places=2)


class PurchaseAgentRequest(BaseModel):
    agent: AgentKind


class PurchaseAgentResponse(BaseModel):
    id: uuid.UUID
    agent_instance_id: uuid.UUID
    agent: str
    price: Decimal
    balance: Decimal
    purchased_at: datetime
    expires_at: datetime
