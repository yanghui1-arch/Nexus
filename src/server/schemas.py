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
    WorkspaceRecord,
)


class AgentKind(str, Enum):
    tela = "tela"
    sophie = "sophie"


class TaskCheckpoint(BaseModel):
    version: int = Field(default=1, ge=1)
    turn_context: list[dict[str, Any]] = Field(default_factory=list)

    @field_validator("turn_context")
    @classmethod
    def validate_turn_context(cls, value: list[dict[str, Any]]) -> list[dict[str, Any]]:
        for message in value:
            if not isinstance(message, dict):
                raise ValueError("Checkpoint turn_context must contain object messages")
            role = message.get("role")
            if not isinstance(role, str) or not role.strip():
                raise ValueError("Checkpoint messages must include non-empty `role`")

        return value


class TaskCreateRequest(BaseModel):
    agent_instance_id: uuid.UUID
    agent: AgentKind
    question: str = Field(min_length=1)
    repo: str | None = None
    project: str | None = None
    current_session_ctx: list[dict[str, Any]] = Field(default_factory=list)
    history_session_ctx: list[dict[str, Any]] = Field(default_factory=list)
    checkpoint: TaskCheckpoint | None = None

    @field_validator("question")
    @classmethod
    def validate_question(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("question cannot be empty")
        return stripped


class TaskSubmitResponse(BaseModel):
    task_id: uuid.UUID
    agent_instance_id: uuid.UUID
    status: TaskStatus


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


class AgentInstanceCreateRequest(BaseModel):
    agent: AgentKind
    client_id: str = Field(min_length=1)
    github_repo: str | None = None
    project: str | None = None
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
    github_repo: str | None
    project: str | None
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
            github_repo=instance.github_repo,
            project=instance.project,
            display_name=instance.display_name,
            is_active=instance.is_active,
            created_at=instance.created_at,
            updated_at=instance.updated_at,
            workspace=WorkspaceResponse.from_record(workspace) if workspace else None,
        )



