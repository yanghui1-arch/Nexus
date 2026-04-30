"""Task API routes."""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Request

from src.agents import Sophie, Tela
from src.agents.base import Agent
from src.server.config import get_settings
from src.server.postgres.database import Database
from src.server.postgres.models import (
    TaskStatus,
    TaskWorkItemStatus,
    VirtualPullRequestStatus,
    VirtualPullRequestReviewDecision,
)
from src.server.postgres.repositories import (
    TaskRepository,
    TaskWorkItemRepository,
    VirtualPullRequestCommentRepository,
    VirtualPullRequestRepository,
    VirtualPullRequestThreadRepository,
)
from src.server.runner import AgentTaskRunner
from src.server.schemas import (
    ReviewQueueItemResponse,
    TaskConsultRequest,
    TaskConsultResponse,
    TaskCreateRequest,
    TaskReviewSummaryResponse,
    TaskResponse,
    TaskStatusUpdateRequest,
    TaskSubmitResponse,
    TaskWorkItemResponse,
    VirtualPullRequestCommentCreateRequest,
    VirtualPullRequestCommentResponse,
    VirtualPullRequestDetailResponse,
    VirtualPullRequestDiffResponse,
    VirtualPullRequestResponse,
    VirtualPullRequestReviewRequest,
    VirtualPullRequestReviewResponse,
    VirtualPullRequestThreadCreateRequest,
    VirtualPullRequestThreadResponse,
    VirtualPullRequestThreadUpdateRequest,
)

router = APIRouter(prefix="/v1/tasks", tags=["tasks"])
available_agent_factory = {
    "tela": Tela,
    "sophie": Sophie,
}


def _build_thread_responses(threads, comments):
    comments_by_thread_id: dict[uuid.UUID, list] = defaultdict(list)
    for comment in comments:
        comments_by_thread_id[comment.thread_id].append(comment)
    return [
        VirtualPullRequestThreadResponse.from_record(
            thread,
            comments_by_thread_id.get(thread.id, []),
        )
        for thread in threads
    ]


async def _sync_task_status_for_virtual_pr_review(
    session,
    task,
):
    work_items = await TaskWorkItemRepository.list_by_task(session, task.id)
    if not work_items:
        return None
    if all(work_item.status == TaskWorkItemStatus.closed for work_item in work_items):
        return await TaskRepository.set_closed(session, task.id)
    if all(
        work_item.status in {TaskWorkItemStatus.approved, TaskWorkItemStatus.closed}
        for work_item in work_items
    ):
        return await TaskRepository.set_waiting_for_merge(session, task.id, result=task.result)
    return await TaskRepository.set_waiting_for_review(session, task.id, result=task.result)


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


@router.get("/review-queue", response_model=list[ReviewQueueItemResponse])
async def list_review_queue(
    request: Request,
    limit: int = Query(default=200, ge=1, le=1000),
) -> list[ReviewQueueItemResponse]:
    database: Database = request.app.state.database
    async with database.session() as session:
        tasks = await TaskRepository.list_review_queue(session, limit=limit)
        queue_items: list[ReviewQueueItemResponse] = []
        for task in tasks:
            virtual_prs = await VirtualPullRequestRepository.list_by_task(session, task.id)
            queue_items.append(
                ReviewQueueItemResponse(
                    task=TaskResponse.from_record(task),
                    virtual_pr_count=len(virtual_prs),
                )
            )
    return queue_items


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


@router.get("/{task_id}/review-summary", response_model=TaskReviewSummaryResponse)
async def get_task_review_summary(
    request: Request,
    task_id: uuid.UUID,
) -> TaskReviewSummaryResponse:
    database: Database = request.app.state.database
    async with database.session() as session:
        task = await TaskRepository.get(session, task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        work_items = await TaskWorkItemRepository.list_by_task(session, task_id)
        virtual_prs = await VirtualPullRequestRepository.list_by_task(session, task_id)
    return TaskReviewSummaryResponse(
        task=TaskResponse.from_record(task),
        work_items=[TaskWorkItemResponse.from_record(work_item) for work_item in work_items],
        virtual_prs=[VirtualPullRequestResponse.from_record(virtual_pr) for virtual_pr in virtual_prs],
    )


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


@router.get("/{task_id}/virtual-prs/{virtual_pr_id}", response_model=VirtualPullRequestDetailResponse)
async def get_virtual_pull_request_detail(
    request: Request,
    task_id: uuid.UUID,
    virtual_pr_id: uuid.UUID,
) -> VirtualPullRequestDetailResponse:
    database: Database = request.app.state.database
    async with database.session() as session:
        task = await TaskRepository.get(session, task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        virtual_pr = await VirtualPullRequestRepository.get(session, virtual_pr_id)
        if virtual_pr is None or virtual_pr.task_id != task_id:
            raise HTTPException(status_code=404, detail="Virtual pull request not found")
        work_item = await TaskWorkItemRepository.get(session, virtual_pr.work_item_id)
        if work_item is None:
            raise HTTPException(status_code=404, detail="Work item not found")
        reviews = await VirtualPullRequestRepository.list_reviews_by_virtual_pr(session, virtual_pr_id)
        threads = await VirtualPullRequestThreadRepository.list_by_virtual_pr(session, virtual_pr_id)
        comments = await VirtualPullRequestCommentRepository.list_by_thread_ids(
            session,
            [thread.id for thread in threads],
        )
    return VirtualPullRequestDetailResponse(
        task=TaskResponse.from_record(task),
        work_item=TaskWorkItemResponse.from_record(work_item),
        virtual_pr=VirtualPullRequestResponse.from_record(virtual_pr),
        diff=virtual_pr.diff or "",
        reviews=[VirtualPullRequestReviewResponse.from_record(review) for review in reviews],
        threads=_build_thread_responses(threads, comments),
    )


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


@router.post(
    "/{task_id}/virtual-prs/{virtual_pr_id}/threads",
    response_model=VirtualPullRequestThreadResponse,
    status_code=201,
)
async def create_virtual_pull_request_thread(
    request: Request,
    task_id: uuid.UUID,
    virtual_pr_id: uuid.UUID,
    payload: VirtualPullRequestThreadCreateRequest,
) -> VirtualPullRequestThreadResponse:
    database: Database = request.app.state.database
    async with database.session() as session:
        task = await TaskRepository.get(session, task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        created = await VirtualPullRequestThreadRepository.create(
            session,
            task_id=task_id,
            virtual_pr_id=virtual_pr_id,
            kind=payload.kind,
            created_by=payload.created_by,
            body=payload.body,
            file_path=payload.file_path,
            start_line=payload.start_line,
            end_line=payload.end_line,
            line_side=payload.line_side,
            diff_hunk=payload.diff_hunk,
        )
    if created is None:
        raise HTTPException(status_code=404, detail="Virtual pull request not found")
    thread, comment = created
    return VirtualPullRequestThreadResponse.from_record(thread, [comment])


@router.post(
    "/{task_id}/virtual-prs/{virtual_pr_id}/threads/{thread_id}/comments",
    response_model=VirtualPullRequestCommentResponse,
    status_code=201,
)
async def create_virtual_pull_request_comment(
    request: Request,
    task_id: uuid.UUID,
    virtual_pr_id: uuid.UUID,
    thread_id: uuid.UUID,
    payload: VirtualPullRequestCommentCreateRequest,
) -> VirtualPullRequestCommentResponse:
    database: Database = request.app.state.database
    async with database.session() as session:
        task = await TaskRepository.get(session, task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        virtual_pr = await VirtualPullRequestRepository.get(session, virtual_pr_id)
        if virtual_pr is None or virtual_pr.task_id != task_id:
            raise HTTPException(status_code=404, detail="Virtual pull request not found")
        thread = await VirtualPullRequestThreadRepository.get(session, thread_id)
        if thread is None or thread.virtual_pr_id != virtual_pr_id:
            raise HTTPException(status_code=404, detail="Thread not found")
        comment = await VirtualPullRequestThreadRepository.add_comment(
            session,
            thread_id=thread_id,
            author=payload.author,
            parent_comment_id=payload.parent_comment_id,
            body=payload.body,
        )
    if comment is None:
        raise HTTPException(status_code=404, detail="Reply target not found")
    return VirtualPullRequestCommentResponse.from_record(comment)


@router.patch(
    "/{task_id}/virtual-prs/{virtual_pr_id}/threads/{thread_id}",
    response_model=VirtualPullRequestThreadResponse,
)
async def update_virtual_pull_request_thread(
    request: Request,
    task_id: uuid.UUID,
    virtual_pr_id: uuid.UUID,
    thread_id: uuid.UUID,
    payload: VirtualPullRequestThreadUpdateRequest,
) -> VirtualPullRequestThreadResponse:
    database: Database = request.app.state.database
    async with database.session() as session:
        task = await TaskRepository.get(session, task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        virtual_pr = await VirtualPullRequestRepository.get(session, virtual_pr_id)
        if virtual_pr is None or virtual_pr.task_id != task_id:
            raise HTTPException(status_code=404, detail="Virtual pull request not found")
        thread = await VirtualPullRequestThreadRepository.update_status(
            session,
            virtual_pr_id=virtual_pr_id,
            thread_id=thread_id,
            status=payload.status,
        )
        if thread is None:
            raise HTTPException(status_code=404, detail="Thread not found")
        comments = await VirtualPullRequestCommentRepository.list_by_thread_ids(
            session, [thread.id]
        )
    return VirtualPullRequestThreadResponse.from_record(thread, comments)


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
        if (
            payload.decision == VirtualPullRequestReviewDecision.approved
            and virtual_pr.status != VirtualPullRequestStatus.ready_for_review
        ):
            raise HTTPException(
                status_code=409,
                detail="Only open virtual pull requests can be approved",
            )
        if (
            payload.decision == VirtualPullRequestReviewDecision.closed
            and virtual_pr.status == VirtualPullRequestStatus.closed
        ):
            raise HTTPException(
                status_code=409,
                detail="Virtual pull request is already closed",
            )
        if (
            payload.decision == VirtualPullRequestReviewDecision.reopened
            and virtual_pr.status != VirtualPullRequestStatus.closed
        ):
            raise HTTPException(
                status_code=409,
                detail="Only closed virtual pull requests can be reopened",
            )

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
            await _sync_task_status_for_virtual_pr_review(session, task)
        elif payload.decision == VirtualPullRequestReviewDecision.closed:
            await TaskWorkItemRepository.mark_closed(session, virtual_pr.work_item_id)
            await _sync_task_status_for_virtual_pr_review(session, task)
        elif payload.decision == VirtualPullRequestReviewDecision.reopened:
            await TaskWorkItemRepository.reopen_for_review(session, virtual_pr.work_item_id)
            await _sync_task_status_for_virtual_pr_review(session, task)

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
