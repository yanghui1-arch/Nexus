from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

from src.server.postgres.models import (
    AgentInstanceRecord,
    TaskRecord,
    TaskStatus,
    TaskWorkItemRecord,
    TaskWorkItemStatus,
    VirtualPullRequestRecord,
    VirtualPullRequestReviewDecision,
    VirtualPullRequestReviewRecord,
    VirtualPullRequestStatus,
    WorkspaceRecord,
)


class AgentKind(str, Enum):
    tela = "tela"
    sophie = "sophie"


class TaskCreateRequest(BaseModel):
    agent_instance_id: uuid.UUID
    agent: AgentKind
    question: str = Field(min_length=1)
    repo: str = Field(min_length=1)
    project: str | None = None

    @field_validator("question")
    @classmethod
    def validate_question(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("question cannot be empty")
        return stripped

    @field_validator("repo")
    @classmethod
    def validate_repo(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("repo cannot be empty")
        return stripped


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
    status: TaskStatus


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
        if value not in {TaskStatus.merged, TaskStatus.closed}:
            raise ValueError("status must be merged or closed")
        return value


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    agent: str
    agent_instance_id: uuid.UUID
    question: str
    repo: str | None
    project: str | None
    status: TaskStatus
    result: str | None
    error: str | None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    @classmethod
    def from_record(cls, task: TaskRecord) -> "TaskResponse":
        return cls(
            id=task.id,
            agent=task.agent.value,
            agent_instance_id=task.agent_instance_id,
            question=task.question,
            repo=task.repo,
            project=task.project,
            status=task.status,
            result=task.result,
            error=task.error,
            created_at=task.created_at,
            updated_at=task.updated_at,
            started_at=task.started_at,
            finished_at=task.finished_at,
        )


class TaskMessage(BaseModel):
    timestamp: str
    status: str = Field(validation_alias=AliasChoices("status", "event"))
    description: str | None = Field(default=None, validation_alias=AliasChoices("description", "content"))
    data: dict[str, Any] | None = None
    meta: dict[str, Any] | None = None


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


class VirtualPullRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    task_id: uuid.UUID
    work_item_id: uuid.UUID
    status: VirtualPullRequestStatus
    base_commit: str
    head_commit: str
    summary: str
    changed_files: list[str]
    additions: int
    deletions: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_record(cls, virtual_pr: VirtualPullRequestRecord) -> "VirtualPullRequestResponse":
        return cls(
            id=virtual_pr.id,
            task_id=virtual_pr.task_id,
            work_item_id=virtual_pr.work_item_id,
            status=virtual_pr.status,
            base_commit=virtual_pr.base_commit,
            head_commit=virtual_pr.head_commit,
            summary=virtual_pr.summary,
            changed_files=virtual_pr.changed_files,
            additions=virtual_pr.additions,
            deletions=virtual_pr.deletions,
            created_at=virtual_pr.created_at,
            updated_at=virtual_pr.updated_at,
        )


class VirtualPullRequestDiffResponse(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    work_item_id: uuid.UUID
    base_commit: str
    head_commit: str
    diff: str


class VirtualPullRequestReviewRequest(BaseModel):
    decision: VirtualPullRequestReviewDecision
    reviewer: str | None = Field(default=None, max_length=255)
    comment: str | None = None


class VirtualPullRequestReviewResponse(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    virtual_pr_id: uuid.UUID
    decision: VirtualPullRequestReviewDecision
    reviewer: str | None
    comment: str | None
    created_at: datetime

    @classmethod
    def from_record(
        cls,
        review: VirtualPullRequestReviewRecord,
    ) -> "VirtualPullRequestReviewResponse":
        return cls(
            id=review.id,
            task_id=review.task_id,
            virtual_pr_id=review.virtual_pr_id,
            decision=review.decision,
            reviewer=review.reviewer,
            comment=review.comment,
            created_at=review.created_at,
        )


class AgentInstanceCreateRequest(BaseModel):
    agent: AgentKind
    client_id: str = Field(min_length=1)
    display_name: str | None = None
    is_active: bool = True


class AgentInstanceStatusUpdateRequest(BaseModel):
    is_active: bool


class WorkspaceResponse(BaseModel):
    id: uuid.UUID
    agent_instance_id: uuid.UUID
    workspace_key: str
    github_repo: str | None
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
            is_active=instance.is_active,
            created_at=instance.created_at,
            updated_at=instance.updated_at,
            workspace=WorkspaceResponse.from_record(workspace) if workspace else None,
        )
