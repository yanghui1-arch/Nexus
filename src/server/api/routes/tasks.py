"""Task API routes."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from src.agents import Jules, Sophie, Tela
from src.agents.base import Agent
from src.server.api.dependencies import get_current_user
from src.server.config import get_settings
from src.server.postgres.database import Database
from src.server.postgres.models import (
    AgentName,
    TaskCategory,
    TaskStatus,
    UserRecord,
)
from src.server.postgres.repositories import (
    AgentInstanceRepository,
    TaskExecutionEventRepository,
    TaskRepository,
    TaskWorkItemRepository,
    WorkspaceRepository,
)
from src.server.runner import AgentTaskRunner, TaskDispatchError, TaskSubmission
from src.server.schemas import (
    TaskConsultRequest,
    TaskConsultResponse,
    TaskCreateRequest,
    TaskExecutionEventResponse,
    TaskExecutionStatsResponse,
    TaskMessage,
    TaskResponse,
    TaskStatusUpdateRequest,
    TaskSubmitResponse,
    TaskWorkItemResponse,
)

router = APIRouter(prefix="/v1/tasks", tags=["tasks"])
available_agent_factory = {
    "tela": Tela,
    "sophie": Sophie,
    "jules": Jules,
}


def _resolved_task_repo_project(task, workspace) -> tuple[str | None, str | None]:
    # Mixed datasets still exist here:
    # - current task rows snapshot repo/project directly on TaskRecord
    # - older rows may still need a workspace fallback
    # Prefer the explicit task snapshot when present so later workspace edits do
    # not rewrite historical tasks in the API.
    """Resolve task repo and project from task and workspace data."""
    repo = task.repo or (workspace.github_repo if workspace is not None else None)
    project = task.project if task.project is not None else (workspace.project if workspace is not None else None)
    return repo, project


@router.post("", response_model=TaskSubmitResponse, status_code=202)
async def create_task(
    request: Request,
    payload: TaskCreateRequest,
    user: UserRecord = Depends(get_current_user),
) -> TaskSubmitResponse:
    """Create and dispatch a new agent task."""
    runner: AgentTaskRunner = request.app.state.runner
    database: Database = request.app.state.database
    async with database.session() as session:
        instance = await AgentInstanceRepository.get(session, payload.agent_instance_id)
    if instance is None or instance.user_id != user.id:
        raise HTTPException(status_code=404, detail="Agent instance not found")

    try:
        task_id = await runner.submit_task(
            TaskSubmission(
                agent_instance_id=payload.agent_instance_id,
                agent=AgentName(payload.agent.value),
                question=payload.question,
                external_issue_url=payload.external_issue_url,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except TaskDispatchError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

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
    user: UserRecord = Depends(get_current_user),
) -> list[TaskResponse]:
    """List tasks owned by the current user."""
    database: Database = request.app.state.database
    async with database.session() as session:
        tasks = await TaskRepository.list(
            session,
            agent_instance_id=agent_instance_id,
            status=status,
            category=category,
            repo=repo,
            project=project,
            user_id=user.id,
            limit=limit,
        )
        workspace_by_agent_instance_id = {
            workspace.agent_instance_id: workspace
            for workspace in await WorkspaceRepository.list_for_user(session, user_id=user.id)
        }
    tasks = sorted(tasks, key=lambda task: task.created_at, reverse=True)
    responses: list[TaskResponse] = []
    for task in tasks:
        # Preserve one response shape across old task rows and new workspace-backed rows.
        resolved_repo, resolved_project = _resolved_task_repo_project(
            task,
            workspace_by_agent_instance_id.get(task.agent_instance_id),
        )
        responses.append(TaskResponse.from_record(task, repo=resolved_repo, project=resolved_project))
    return responses


@router.get("/{task_id}/messages", response_model=list[TaskMessage])
async def list_task_messages(
    request: Request,
    task_id: uuid.UUID,
    limit: int = Query(default=200, ge=1, le=1000),
    user: UserRecord = Depends(get_current_user),
) -> list[TaskMessage]:
    """List execution messages for a task owned by the current user."""
    database: Database = request.app.state.database
    async with database.session() as session:
        task = await TaskRepository.get_for_user(session, task_id, user_id=user.id)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        events = await TaskExecutionEventRepository.list_by_task(session, task_id, limit=limit)
    return [
        TaskMessage(
            timestamp=event.created_at.isoformat(),
            status=event.event_type,
            description=event.message,
            data=None,
            meta=event.safe_metadata,
        )
        for event in events
    ]


@router.get("/{task_id}/stats", response_model=TaskExecutionStatsResponse)
async def get_task_stats(
    request: Request,
    task_id: uuid.UUID,
    user: UserRecord = Depends(get_current_user),
) -> TaskExecutionStatsResponse:
    """Return aggregate execution statistics for a task owned by the current user."""
    database: Database = request.app.state.database
    async with database.session() as session:
        task = await TaskRepository.get_for_user(session, task_id, user_id=user.id)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        events = await TaskExecutionEventRepository.list_by_task(session, task_id)
    return TaskExecutionStatsResponse.from_events(events, task=task)


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    request: Request,
    task_id: uuid.UUID,
    user: UserRecord = Depends(get_current_user),
) -> TaskResponse:
    """Return one task owned by the current user."""
    database: Database = request.app.state.database
    async with database.session() as session:
        task = await TaskRepository.get_for_user(session, task_id, user_id=user.id)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        workspace = await WorkspaceRepository.get_by_agent_instance_id(session, task.agent_instance_id)
    repo, project = _resolved_task_repo_project(task, workspace)
    return TaskResponse.from_record(task, repo=repo, project=project)


@router.get("/{task_id}/events", response_model=list[TaskExecutionEventResponse])
async def list_task_events(
    request: Request,
    task_id: uuid.UUID,
    limit: int = Query(default=200, ge=1, le=1000),
    user: UserRecord = Depends(get_current_user),
) -> list[TaskExecutionEventResponse]:
    """List execution events for a task owned by the current user."""
    database: Database = request.app.state.database
    async with database.session() as session:
        task = await TaskRepository.get_for_user(session, task_id, user_id=user.id)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        events = await TaskExecutionEventRepository.list_by_task(session, task_id, limit=limit)
    return [TaskExecutionEventResponse.from_record(event) for event in events]


@router.get("/{task_id}/work-items", response_model=list[TaskWorkItemResponse])
async def list_task_work_items(
    request: Request,
    task_id: uuid.UUID,
    user: UserRecord = Depends(get_current_user),
) -> list[TaskWorkItemResponse]:
    """List review work items for a task."""
    database: Database = request.app.state.database
    async with database.session() as session:
        task = await TaskRepository.get(session, task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        instance = await AgentInstanceRepository.get(session, task.agent_instance_id)
        if instance is None or instance.user_id != user.id:
            raise HTTPException(status_code=404, detail="Task not found")
        work_items = await TaskWorkItemRepository.list_by_task(session, task_id)
    return [TaskWorkItemResponse.from_record(work_item) for work_item in work_items]


@router.patch("/{task_id}/status", response_model=TaskResponse)
async def update_task_status(
    request: Request,
    task_id: uuid.UUID,
    payload: TaskStatusUpdateRequest,
    user: UserRecord = Depends(get_current_user),
) -> TaskResponse:
    """Update review status for a task."""
    database: Database = request.app.state.database

    async with database.session() as session:
        task = await TaskRepository.get(session, task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        instance = await AgentInstanceRepository.get(session, task.agent_instance_id)
        if instance is None or instance.user_id != user.id:
            raise HTTPException(status_code=404, detail="Task not found")

        if payload.status == TaskStatus.merged:
            if task.status == payload.status:
                return TaskResponse.from_record(task)
            if task.status != TaskStatus.waiting_for_review:
                raise HTTPException(
                    status_code=409,
                    detail="Only waiting_for_review tasks can be updated to merged",
                )
            updated = await TaskRepository.set_merged(session, task_id)
        elif payload.status == TaskStatus.closed:
            if task.status == payload.status:
                return TaskResponse.from_record(task)
            if task.status != TaskStatus.waiting_for_review:
                raise HTTPException(
                    status_code=409,
                    detail="Only waiting_for_review tasks can be closed",
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
    user: UserRecord = Depends(get_current_user),
) -> TaskConsultResponse:
    """Ask an agent to report progress for an existing task."""
    database: Database = request.app.state.database
    async with database.session() as session:
        task = await TaskRepository.get(session, task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        instance = await AgentInstanceRepository.get(session, task.agent_instance_id)
        workspace = await WorkspaceRepository.get_by_agent_instance_id(session, task.agent_instance_id)
    if instance is None or instance.user_id != user.id:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.agent.value not in available_agent_factory.keys():
        raise HTTPException(status_code=404, detail=f"Unsupported agent: {task.agent.value}")

    settings = get_settings()
    if not settings.api_key:
        raise HTTPException(status_code=503, detail="NEXUS_API_KEY is not configured")
    repo, _ = _resolved_task_repo_project(task, workspace)
    if not repo:
        raise HTTPException(status_code=409, detail="Task repo is required for consult")

    github_token = settings.github_tokens.get(task.agent.value)
    agent_factory: Agent = available_agent_factory.get(task.agent.value)
    agent: Agent = agent_factory.create(
        base_url=settings.base_url,
        api_key=settings.api_key,
        model=settings.model,
        max_context=settings.max_context,
        github_repo=repo,
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
