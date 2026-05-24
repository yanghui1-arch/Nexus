"""Agent instance API routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from src.server.api.dependencies import get_current_user
from src.server.postgres.database import Database
from src.server.postgres.models import AgentName, UserRecord, WorkspaceStatus
from src.server.postgres.repositories import (
    AgentInstanceRepository,
    WorkspaceRepository,
)
from src.server.schemas import (
    AgentInstanceCreateRequest,
    AgentInstanceDisplayNameUpdateRequest,
    AgentInstanceResponse,
    AgentInstanceStatusUpdateRequest,
    AgentKind,
    WorkspaceUpdateRequest,
)

router = APIRouter(prefix="/v1/agent-instances", tags=["agent-instances"])


@router.post("", response_model=AgentInstanceResponse, status_code=201)
async def create_agent_instance(
    request: Request,
    payload: AgentInstanceCreateRequest,
    user: UserRecord = Depends(get_current_user),
) -> AgentInstanceResponse:
    """Create an active agent instance and create a workspace for the agent instance."""
    database: Database = request.app.state.database

    async with database.session() as session:
        instance = await AgentInstanceRepository.create(
            session,
            agent=AgentName(payload.agent.value),
            client_id=payload.client_id,
            display_name=payload.display_name,
            is_active=True,
            user_id=user.id,
        )
        workspace = await WorkspaceRepository.ensure_for_agent_instance(session, instance)

    return AgentInstanceResponse.from_record(instance, workspace=workspace)


@router.get("", response_model=list[AgentInstanceResponse])
async def list_agent_instances(
    request: Request,
    agent: AgentKind | None = Query(default=None),
    client_id: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    user: UserRecord = Depends(get_current_user),
) -> list[AgentInstanceResponse]:
    """List agent instances visible to the current user."""
    database: Database = request.app.state.database
    async with database.session() as session:
        instances = await AgentInstanceRepository.list(
            session,
            agent=AgentName(agent.value) if agent else None,
            client_id=client_id,
            is_active=is_active,
            user_id=user.id,
        )

        responses: list[AgentInstanceResponse] = []
        for instance in instances:
            workspace = await WorkspaceRepository.get_by_agent_instance_id(session, instance.id)
            responses.append(AgentInstanceResponse.from_record(instance, workspace=workspace))
        return responses


@router.get("/{agent_instance_id}", response_model=AgentInstanceResponse)
async def get_agent_instance(
    request: Request,
    agent_instance_id: uuid.UUID,
    user: UserRecord = Depends(get_current_user),
) -> AgentInstanceResponse:
    """Return one agent instance owned by the current user."""
    database: Database = request.app.state.database
    async with database.session() as session:
        instance = await AgentInstanceRepository.get(session, agent_instance_id)
        if instance is None or instance.user_id != user.id:
            raise HTTPException(status_code=404, detail="Agent instance not found")
        workspace = await WorkspaceRepository.get_by_agent_instance_id(session, instance.id)
    return AgentInstanceResponse.from_record(instance, workspace=workspace)


@router.patch("/{agent_instance_id}", response_model=AgentInstanceResponse)
async def update_agent_instance(
    request: Request,
    agent_instance_id: uuid.UUID,
    payload: AgentInstanceDisplayNameUpdateRequest,
    user: UserRecord = Depends(get_current_user),
) -> AgentInstanceResponse:
    """Update editable metadata for an agent instance."""
    database: Database = request.app.state.database
    async with database.session() as session:
        instance = await AgentInstanceRepository.get(session, agent_instance_id)
        if instance is None or instance.user_id != user.id:
            raise HTTPException(status_code=404, detail="Agent instance not found")
        instance = await AgentInstanceRepository.set_display_name(
            session,
            agent_instance_id,
            display_name=payload.display_name,
        )
        if instance is None:
            raise HTTPException(status_code=404, detail="Agent instance not found")
        workspace = await WorkspaceRepository.get_by_agent_instance_id(session, instance.id)
    return AgentInstanceResponse.from_record(instance, workspace=workspace)


@router.patch("/{agent_instance_id}/status", response_model=AgentInstanceResponse)
async def set_agent_instance_status(
    request: Request,
    agent_instance_id: uuid.UUID,
    payload: AgentInstanceStatusUpdateRequest,
    user: UserRecord = Depends(get_current_user),
) -> AgentInstanceResponse:
    """Activate or deactivate an agent instance."""
    database: Database = request.app.state.database
    async with database.session() as session:
        instance = await AgentInstanceRepository.get(session, agent_instance_id)
        if instance is None or instance.user_id != user.id:
            raise HTTPException(status_code=404, detail="Agent instance not found")
        instance = await AgentInstanceRepository.set_active(
            session,
            agent_instance_id,
            is_active=payload.is_active,
        )
        if instance is None:
            raise HTTPException(status_code=404, detail="Agent instance not found")

        workspace = await WorkspaceRepository.get_by_agent_instance_id(session, instance.id)
        if workspace is not None and workspace.status != WorkspaceStatus.running:
            if payload.is_active:
                workspace = await WorkspaceRepository.set_idle(
                    session,
                    agent_instance_id=instance.id,
                )
            else:
                workspace = await WorkspaceRepository.set_inactive(
                    session,
                    agent_instance_id=instance.id,
                )

    return AgentInstanceResponse.from_record(instance, workspace=workspace)


@router.patch("/{agent_instance_id}/workspace", response_model=AgentInstanceResponse)
async def update_agent_instance_workspace(
    request: Request,
    agent_instance_id: uuid.UUID,
    payload: WorkspaceUpdateRequest,
    user: UserRecord = Depends(get_current_user),
) -> AgentInstanceResponse:
    """Update workspace context for an agent instance."""
    database: Database = request.app.state.database
    async with database.session() as session:
        instance = await AgentInstanceRepository.get(session, agent_instance_id)
        if instance is None or instance.user_id != user.id:
            raise HTTPException(status_code=404, detail="Agent instance not found")
        await WorkspaceRepository.ensure_for_agent_instance(session, instance)
        workspace = await WorkspaceRepository.set_context(
            session,
            agent_instance_id=instance.id,
            github_repo=payload.github_repo,
            project=payload.project,
        )

    return AgentInstanceResponse.from_record(instance, workspace=workspace)
