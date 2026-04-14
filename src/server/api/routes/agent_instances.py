"""Agent instance API routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query, Request

from src.server.postgres.database import Database
from src.server.postgres.models import AgentName
from src.server.postgres.repositories import (
    AgentInstanceRepository,
    WorkspaceRepository,
)
from src.server.schemas import (
    AgentInstanceCreateRequest,
    AgentInstanceResponse,
    AgentInstanceStatusUpdateRequest,
    AgentKind,
)

router = APIRouter(prefix="/v1/agent-instances", tags=["agent-instances"])


@router.post("", response_model=AgentInstanceResponse, status_code=201)
async def create_agent_instance(
    request: Request,
    payload: AgentInstanceCreateRequest,
) -> AgentInstanceResponse:
    database: Database = request.app.state.database

    async with database.session() as session:
        instance = await AgentInstanceRepository.create(
            session,
            agent=AgentName(payload.agent.value),
            client_id=payload.client_id,
            github_repo=payload.github_repo,
            project=payload.project,
            display_name=payload.display_name,
            is_active=payload.is_active,
        )
        workspace = await WorkspaceRepository.ensure_for_agent_instance(session, instance)

    return AgentInstanceResponse.from_record(instance, workspace=workspace)


@router.get("", response_model=list[AgentInstanceResponse])
async def list_agent_instances(
    request: Request,
    agent: AgentKind | None = Query(default=None),
    client_id: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
) -> list[AgentInstanceResponse]:
    database: Database = request.app.state.database
    async with database.session() as session:
        instances = await AgentInstanceRepository.list(
            session,
            agent=AgentName(agent.value) if agent else None,
            client_id=client_id,
            is_active=is_active,
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
) -> AgentInstanceResponse:
    database: Database = request.app.state.database
    async with database.session() as session:
        instance = await AgentInstanceRepository.get(session, agent_instance_id)
        if instance is None:
            raise HTTPException(status_code=404, detail="Agent instance not found")
        workspace = await WorkspaceRepository.get_by_agent_instance_id(session, instance.id)
    return AgentInstanceResponse.from_record(instance, workspace=workspace)


@router.patch("/{agent_instance_id}/status", response_model=AgentInstanceResponse)
async def set_agent_instance_status(
    request: Request,
    agent_instance_id: uuid.UUID,
    payload: AgentInstanceStatusUpdateRequest,
) -> AgentInstanceResponse:
    database: Database = request.app.state.database
    async with database.session() as session:
        instance = await AgentInstanceRepository.set_active(
            session,
            agent_instance_id,
            is_active=payload.is_active,
        )
        if instance is None:
            raise HTTPException(status_code=404, detail="Agent instance not found")
        workspace = await WorkspaceRepository.get_by_agent_instance_id(session, instance.id)

    return AgentInstanceResponse.from_record(instance, workspace=workspace)
