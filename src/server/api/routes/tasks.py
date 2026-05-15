"""Task API routes."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Request

from src.agents import Sophie, Tela
from src.agents.base import Agent
from src.server.config import get_settings
from src.server.postgres.database import Database
from src.server.postgres.models import (
    TaskCategory,
    TaskStatus,
    TaskWorkItemStatus,
)
from src.server.postgres.repositories import (
    TaskRepository,
    TaskWorkItemRepository,
)
from src.server.runner import AgentTaskRunner
from src.server.schemas import (
    TaskConsultRequest,
    TaskConsultResponse,
    TaskCreateRequest,
    TaskResponse,
    TaskStatusUpdateRequest,
    TaskSubmitResponse,
    TaskWorkItemResponse,
)

router = APIRouter(prefix="/v1/tasks", tags=["tasks"])
available_agent_factory = {
    "tela": Tela,
    "sophie": Sophie,
}


@router.post("", response_model=TaskSubmitResponse, status_code=202)
async def create_task(
    request: Request,
    payload: TaskCreateRequest,
) -> TaskSubmitResponse:
    runner: AgentTaskRunner = request.app.state.runner
    database: Database = request.app.state.database
    try:
        task_id = await runner.submit_task(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    async with database.session() as session:
        task = await TaskRepository.get(session, task_id)
    if task is None:
        raise HTTPException(status_code=500, detail="Created task could not be loaded")

    return TaskSubmitResponse(
        task_id=task_id,
        agent_instance_id=payload.agent_instance_id,
        category=task.category,
        status=TaskStatus.queued,
    )


@router.get("", response_model=list[TaskResponse])
async def list_tasks(
    request: Request,
    agent_instance_id: uuid.UUID | None = Query(default=None),
    status: TaskStatus | None = Query(default=None),
    category: TaskCategory | None = Query(default=None),
    repo: str | None = Query(default=None),
    project: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
) -> list[TaskResponse]:
    database: Database = request.app.state.database
    async with database.session() as session:
        tasks = await TaskRepository.list(
            session,
            agent_instance_id=agent_instance_id,
            status=status,
            category=category,
            repo=repo,
            project=project,
            limit=limit,
        )
    tasks = sorted(tasks, key=lambda task: task.created_at, reverse=True)
    return [TaskResponse.from_record(task) for task in tasks]


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


@router.get("/{task_id}/work-items", response_model=list[TaskWorkItemResponse])
async def list_task_work_items(
    request: Request,
    task_id: uuid.UUID,
) -> list[TaskWorkItemResponse]:
    database: Database = request.app.state.database
    async with database.session() as session:
        task = await TaskRepository.get(session, task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        work_items = await TaskWorkItemRepository.list_by_task(session, task_id)
    return [TaskWorkItemResponse.from_record(work_item) for work_item in work_items]


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

        if payload.status == TaskStatus.merged:
            if task.status == payload.status:
                return TaskResponse.from_record(task)
            if task.status != TaskStatus.waiting_for_merge:
                raise HTTPException(
                    status_code=409,
                    detail="Only waiting_for_merge tasks can be updated to merged",
                )
            updated = await TaskRepository.set_merged(session, task_id)
        elif payload.status == TaskStatus.closed:
            if task.status == payload.status:
                return TaskResponse.from_record(task)
            if task.status not in {TaskStatus.waiting_for_review, TaskStatus.waiting_for_merge}:
                raise HTTPException(
                    status_code=409,
                    detail="Only waiting_for_review or waiting_for_merge tasks can be closed",
                )
            updated = await TaskRepository.set_closed(session, task_id)
        else:
            if task.status == TaskStatus.waiting_for_review:
                return TaskResponse.from_record(task)
            if task.status != TaskStatus.closed:
                raise HTTPException(
                    status_code=409,
                    detail="Only closed tasks can be reopened",
                )
            work_items = await TaskWorkItemRepository.list_by_task(session, task_id)
            if work_items and all(
                work_item.status == TaskWorkItemStatus.approved for work_item in work_items
            ):
                updated = await TaskRepository.set_waiting_for_merge(
                    session,
                    task_id,
                    result=task.result,
                )
            else:
                updated = await TaskRepository.set_waiting_for_review(
                    session,
                    task_id,
                    result=task.result,
                )

    if updated is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskResponse.from_record(updated)


@router.post("/{task_id}/consult", response_model=TaskConsultResponse)
async def consult_task(
    request: Request,
    task_id: uuid.UUID,
    payload: TaskConsultRequest,
) -> TaskConsultResponse:
    database: Database = request.app.state.database
    async with database.session() as session:
        task = await TaskRepository.get(session, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.agent.value not in available_agent_factory.keys():
        raise HTTPException(status_code=404, detail=f"Unsupported agent: {task.agent.value}")

    settings = get_settings()
    if not settings.api_key:
        raise HTTPException(status_code=503, detail="NEXUS_API_KEY is not configured")
    if not task.repo:
        raise HTTPException(status_code=409, detail="Task repo is required for consult")

    github_token = settings.github_tokens.get(task.agent.value)
    agent_factory: Agent = available_agent_factory.get(task.agent.value)
    agent: Agent = agent_factory.create(
        base_url=settings.base_url,
        api_key=settings.api_key,
        model=settings.model,
        max_context=settings.max_context,
        github_repo=task.repo,
        max_attempts=settings.max_attempts,
        github_token=github_token,
    )

    try:
        reply = await agent.report_current_process(
            checkpoint=task.checkpoint,
            user_message=payload.message,
        )
    finally:
        await agent.close()

    return TaskConsultResponse(
        task_id=task.id,
        status=task.status,
        reply=reply,
        timestamp=datetime.now(timezone.utc),
    )
