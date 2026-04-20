"""Task API routes."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from src.logger import logger
from src.server.postgres.database import Database
from src.server.postgres.models import TaskStatus
from src.server.postgres.repositories import (
    TaskActivityRepository,
    TaskRepository,
)
from src.server.redis.client import RedisClient
from src.server.runner import AgentTaskRunner
from src.server.schemas import (
    TaskCreateRequest,
    TaskMessage,
    TaskResponse,
    TaskStatusUpdateRequest,
    TaskSubmitResponse,
)

router = APIRouter(prefix="/v1/tasks", tags=["tasks"])


@router.post("", response_model=TaskSubmitResponse, status_code=202)
async def create_task(
    request: Request,
    payload: TaskCreateRequest,
) -> TaskSubmitResponse:
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


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    request: Request,
    task_id: uuid.UUID,
) -> TaskResponse:
    database: Database = request.app.state.database
    async with database.session() as session:
        task = await TaskRepository.get(session, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskResponse.from_record(task)

@router.patch("/{task_id}/status", response_model=TaskResponse)
async def update_task_status(
    request: Request,
    task_id: uuid.UUID,
    payload: TaskStatusUpdateRequest,
) -> TaskResponse:
    database: Database = request.app.state.database

    async with database.session() as session:
        task = await TaskRepository.get(session, task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")

        if task.status == payload.status:
            return TaskResponse.from_record(task)
        if task.status != TaskStatus.waiting_for_merge:
            raise HTTPException(
                status_code=409,
                detail="Only waiting_for_merge tasks can be updated to merged or closed",
            )

        if payload.status == TaskStatus.merged:
            updated = await TaskRepository.set_merged(session, task_id)
        else:
            updated = await TaskRepository.set_closed(session, task_id)

    if updated is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskResponse.from_record(updated)


@router.get("/{task_id}/messages", response_model=list[TaskMessage])
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


async def _load_task_messages(
    redis_client: RedisClient,
    task_id: uuid.UUID,
    *,
    limit: int,
) -> list[dict[str, Any]]:
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
