"""Task API routes."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Request

from src.agents import Sophie, Tela
from src.agents.base import Agent
from src.server.config import get_settings
from src.server.postgres.database import Database
from src.server.postgres.models import TaskStatus, VirtualPullRequestReviewDecision
from src.server.postgres.repositories import (
    TaskRepository,
    TaskWorkItemRepository,
    VirtualPullRequestRepository,
)
from src.server.runner import AgentTaskRunner
from src.server.schemas import (
    TaskConsultRequest,
    TaskConsultResponse,
    TaskCreateRequest,
    TaskWorkItemResponse,
    VirtualPullRequestDiffResponse,
    VirtualPullRequestResponse,
    VirtualPullRequestReviewRequest,
    VirtualPullRequestReviewResponse,
    TaskResponse,
    TaskStatusUpdateRequest,
    TaskSubmitResponse,
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
    try:
        task_id = await runner.submit_task(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return TaskSubmitResponse(
        task_id=task_id,
        agent_instance_id=payload.agent_instance_id,
        status=TaskStatus.queued,
    )


@router.get("", response_model=list[TaskResponse])
async def list_tasks(
    request: Request,
    agent_instance_id: uuid.UUID | None = Query(default=None),
    status: TaskStatus | None = Query(default=None),
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


@router.get("/{task_id}/virtual-prs", response_model=list[VirtualPullRequestResponse])
async def list_virtual_pull_requests(
    request: Request,
    task_id: uuid.UUID,
) -> list[VirtualPullRequestResponse]:
    database: Database = request.app.state.database
    async with database.session() as session:
        task = await TaskRepository.get(session, task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        virtual_prs = await VirtualPullRequestRepository.list_by_task(session, task_id)
    return [VirtualPullRequestResponse.from_record(virtual_pr) for virtual_pr in virtual_prs]


@router.get("/{task_id}/virtual-prs/{virtual_pr_id}/diff", response_model=VirtualPullRequestDiffResponse)
async def get_virtual_pull_request_diff(
    request: Request,
    task_id: uuid.UUID,
    virtual_pr_id: uuid.UUID,
) -> VirtualPullRequestDiffResponse:
    database: Database = request.app.state.database
    async with database.session() as session:
        task = await TaskRepository.get(session, task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        virtual_pr = await VirtualPullRequestRepository.get(session, virtual_pr_id)
    if virtual_pr is None or virtual_pr.task_id != task_id:
        raise HTTPException(status_code=404, detail="Virtual pull request not found")
    return VirtualPullRequestDiffResponse(
        id=virtual_pr.id,
        task_id=virtual_pr.task_id,
        work_item_id=virtual_pr.work_item_id,
        base_commit=virtual_pr.base_commit,
        head_commit=virtual_pr.head_commit,
        diff=virtual_pr.diff or "",
    )


@router.patch(
    "/{task_id}/virtual-prs/{virtual_pr_id}/review",
    response_model=VirtualPullRequestReviewResponse,
)
async def review_virtual_pull_request(
    request: Request,
    task_id: uuid.UUID,
    virtual_pr_id: uuid.UUID,
    payload: VirtualPullRequestReviewRequest,
) -> VirtualPullRequestReviewResponse:
    database: Database = request.app.state.database

    async with database.session() as session:
        task = await TaskRepository.get(session, task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        virtual_pr = await VirtualPullRequestRepository.get(session, virtual_pr_id)
        if virtual_pr is None or virtual_pr.task_id != task_id:
            raise HTTPException(status_code=404, detail="Virtual pull request not found")

        review = await VirtualPullRequestRepository.add_review(
            session,
            virtual_pr_id=virtual_pr_id,
            decision=payload.decision,
            reviewer=payload.reviewer,
            comment=payload.comment,
        )
        if review is None:
            raise HTTPException(status_code=404, detail="Virtual pull request not found")

        if payload.decision == VirtualPullRequestReviewDecision.approved:
            await TaskWorkItemRepository.mark_approved(session, virtual_pr.work_item_id)
        else:
            await TaskWorkItemRepository.mark_changes_requested(session, virtual_pr.work_item_id)

        await TaskRepository.set_queued(session, task_id)

    runner: AgentTaskRunner = request.app.state.runner
    dispatched = await runner.dispatch_existing_task(task_id, recovered=False)
    if not dispatched:
        raise HTTPException(status_code=409, detail="Task could not be dispatched for follow-up work")

    return VirtualPullRequestReviewResponse.from_record(review)


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

@router.post("/{task_id}/consult", response_model=TaskConsultResponse)
async def consult_task(
    request: Request,
    task_id: uuid.UUID,
    payload: TaskConsultRequest,
) -> TaskConsultResponse:
    # Currently only support once question about current progress. 

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
