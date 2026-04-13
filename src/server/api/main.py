from __future__ import annotations

import json
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request, status

from src.logger import logger
from src.server.config import get_settings
from src.server.postgres.database import Database
from src.server.postgres.models import AgentName, TaskStatus
from src.server.postgres.repositories import (
    AgentInstanceRepository,
    TaskActivityRepository,
    TaskRepository,
    WorkspaceRepository,
)
from src.server.redis.client import RedisClient
from src.server.runner import AgentTaskRunner
from src.server.schemas import (
    AgentInstanceCreateRequest,
    AgentInstanceResponse,
    AgentInstanceStatusUpdateRequest,
    AgentKind,
    TaskCreateRequest,
    TaskMessage,
    TaskResponse,
    TaskSubmitResponse,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    database = Database(settings.database_url)
    await database.connect()
    await database.create_schema()

    redis_client = RedisClient(
        settings.redis_url,
        ttl_seconds=settings.redis_message_ttl_seconds,
    )
    await redis_client.connect()

    runner = AgentTaskRunner(
        settings=settings,
        database=database,
        redis_client=redis_client,
    )

    app.state.database = database
    app.state.redis_client = redis_client
    app.state.runner = runner

    recovered_count = await runner.recover_unfinished_tasks()
    if recovered_count:
        logger.warning("Startup recovery scheduled %s unfinished tasks.", recovered_count)

    try:
        yield
    finally:
        await runner.shutdown()
        await redis_client.close()
        await database.disconnect()

        try:
            from src.sandbox import get_sandbox_pool_manager
        except ModuleNotFoundError:
            return

        await get_sandbox_pool_manager().shutdown()


app = FastAPI(
    title="Nexus Service",
    version="0.1.0-beta",
    lifespan=lifespan,
)


@app.get("/health")
async def health(request: Request) -> dict[str, Any]:
    db_ok = await request.app.state.database.ping()
    redis_ok = await request.app.state.redis_client.ping()
    return {
        "status": "ok" if db_ok and redis_ok else "degraded",
        "database": "ok" if db_ok else "down",
        "redis": "ok" if redis_ok else "down",
    }


@app.post("/v1/agent-instances", response_model=AgentInstanceResponse, status_code=status.HTTP_201_CREATED)
async def create_agent_instance(request: Request, payload: AgentInstanceCreateRequest) -> AgentInstanceResponse:
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


@app.get("/v1/agent-instances", response_model=list[AgentInstanceResponse])
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


@app.get("/v1/agent-instances/{agent_instance_id}", response_model=AgentInstanceResponse)
async def get_agent_instance(request: Request, agent_instance_id: uuid.UUID) -> AgentInstanceResponse:
    database: Database = request.app.state.database
    async with database.session() as session:
        instance = await AgentInstanceRepository.get(session, agent_instance_id)
        if instance is None:
            raise HTTPException(status_code=404, detail="Agent instance not found")
        workspace = await WorkspaceRepository.get_by_agent_instance_id(session, instance.id)
    return AgentInstanceResponse.from_record(instance, workspace=workspace)


@app.patch("/v1/agent-instances/{agent_instance_id}/status", response_model=AgentInstanceResponse)
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


@app.post("/v1/tasks", response_model=TaskSubmitResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_task(request: Request, payload: TaskCreateRequest) -> TaskSubmitResponse:
    runner: AgentTaskRunner = request.app.state.runner
    try:
        task_id = await runner.submit_task(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return TaskSubmitResponse(
        task_id=task_id,
        agent_instance_id=payload.agent_instance_id,
        status=TaskStatus.queued,
    )


@app.get("/v1/tasks/{task_id}", response_model=TaskResponse)
async def get_task(request: Request, task_id: uuid.UUID) -> TaskResponse:
    database: Database = request.app.state.database
    async with database.session() as session:
        task = await TaskRepository.get(session, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskResponse.from_record(task)


@app.get("/v1/tasks/{task_id}/messages", response_model=list[TaskMessage])
async def get_task_messages(
    request: Request,
    task_id: uuid.UUID,
    limit: int = Query(default=200, ge=1, le=1000),
) -> list[TaskMessage]:
    database: Database = request.app.state.database
    async with database.session() as session:
        task = await TaskRepository.get(session, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    rows: list[dict[str, Any]] = []
    try:
        rows = await _load_task_messages(request.app.state.redis_client, task_id, limit=limit)
    except Exception:
        logger.exception("Redis message projection read failed for task_id=%s; falling back to PostgreSQL.", task_id)

    if not rows:
        rows = await _load_task_messages_from_pg(database, task_id, limit=limit)
    return [TaskMessage.model_validate(row) for row in rows]




async def _load_task_messages(redis_client: RedisClient, task_id: uuid.UUID, *, limit: int) -> list[dict[str, Any]]:
    rows = await redis_client._require_client().lrange(f"task:{task_id}:messages", -limit, -1)

    parsed: list[dict[str, Any]] = []
    for row in rows:
        try:
            payload = json.loads(row)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            parsed.append(_normalize_task_message(payload))
    return parsed



async def _load_task_messages_from_pg(
    database: Database,
    task_id: uuid.UUID,
    *,
    limit: int,
) -> list[dict[str, Any]]:
    async with database.session() as session:
        activities = await TaskActivityRepository.list_by_task(
            session,
            task_id=task_id,
            limit=limit,
        )

    rows: list[dict[str, Any]] = []
    for activity in activities:
        rows.append(
            _normalize_task_message(
                {
                    "timestamp": activity.created_at.isoformat(),
                    "event": activity.event,
                    "content": activity.content,
                    "tools": activity.tools,
                    "tool_args": activity.tool_args,
                }
            )
        )
    return rows

def _normalize_task_message(payload: dict[str, Any]) -> dict[str, Any]:
    status = payload.get("status") or payload.get("event") or "PROCESS"
    description = payload.get("description")
    if description is None and "content" in payload:
        description = payload.get("content")

    data = payload.get("data")
    if data is None:
        tools = payload.get("tools")
        tool_args = payload.get("tool_args")
        if tools is not None or tool_args is not None:
            data = {
                "tools": tools,
                "tool_args": tool_args,
            }

    return {
        "timestamp": payload.get("timestamp", datetime.now(timezone.utc).isoformat()),
        "status": status,
        "description": description,
        "data": data,
        "meta": payload.get("meta"),
    }




