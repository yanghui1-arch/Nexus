"""Task dispatcher for executor worker.

PostgreSQL stores business state; Celery owns worker delivery and redelivery.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from src.logger import logger
from src.server.celery.app import celery_app
from src.server.config import Settings
from src.server.postgres.database import Database
from src.server.postgres.models import AgentName, TaskCategory, TaskStatus
from src.server.postgres.repositories import (
    AgentInstanceRepository,
    ProposalPlanningRunRepository,
    TaskRepository,
    WorkspaceRepository,
)
from src.server.schemas import TaskCreateRequest


class TaskDispatchError(RuntimeError):
    """Raised when a task cannot be published to the Celery broker."""


def _task_category_for_agent(agent: AgentName) -> TaskCategory:
    """Return the task category used for an agent."""
    if agent == AgentName.assistant:
        return TaskCategory.review
    if agent == AgentName.marc:
        return TaskCategory.pm
    return TaskCategory.coding


class AgentTaskRunner:
    """Dispatch persisted tasks to Celery workers."""

    def __init__(
        self,
        *,
        settings: Settings,
        database: Database,
    ) -> None:
        """Initialize the service component."""
        self._settings = settings
        self._database = database

    async def create_task_record(
        self,
        request: TaskCreateRequest,
        *,
        session: AsyncSession | None = None,
    ):
        # Some callers, such as proposal approval, need the task row to exist inside
        # a larger transaction before dispatch happens so they can attach extra state
        # like proposal-planning tracking rows atomically.
        """Create a task record without dispatching it."""
        if session is not None:
            return await self._create_task_record(session, request)

        async with self._database.session() as own_session:
            task = await self._create_task_record(own_session, request)
            await own_session.commit()
            await own_session.refresh(task)
            return task

    async def submit_task(self, request: TaskCreateRequest) -> uuid.UUID:
        """Persist and dispatch a new task."""
        async with self._database.session() as session:
            task = await self._create_task_record(session, request)
            await session.commit()
            await session.refresh(task)
        logger.info(f"Task `{task.id}` is queued.")

        await self._dispatch_or_fail(task.id)
        logger.info(f"Task `{task.id}` has been dispatched for worker.")

        return task.id

    async def shutdown(self) -> None:
        """Shut down runner resources."""
        return None

    async def dispatch_planning_task(
        self,
        task_id: uuid.UUID,
    ) -> bool:
        """Dispatch a planning task created in a caller-owned transaction."""
        return await self._dispatch_or_fail(task_id)

    async def _dispatch_or_fail(
        self,
        task_id: uuid.UUID,
    ) -> bool:
        """Dispatch a task and mark dispatch failure in PostgreSQL."""
        try:
            dispatched = await self._dispatch(task_id)
        except Exception as exc:
            error = f"Dispatch failed: {exc}"
            await self._mark_dispatch_failed(task_id, error=error)
            logger.error(f"Fail to dispatch task `{task_id}`: {str(exc)}")
            raise TaskDispatchError(error) from exc

        if not dispatched:
            error = f"Dispatch failed: Task `{task_id}` is no longer queued for dispatch."
            await self._mark_dispatch_failed(task_id, error=error)
            logger.error(error)
            raise TaskDispatchError(error)
        return True

    async def _mark_dispatch_failed(self, task_id: uuid.UUID, *, error: str) -> None:
        """Mark dispatch failure on the task and any linked planning run."""
        async with self._database.session() as session:
            task = await TaskRepository.set_failed(session, task_id, error=error)
            if task is None or task.category != TaskCategory.pm:
                return

            planning_run = await ProposalPlanningRunRepository.get_by_task_id(session, task_id)
            if planning_run is not None:
                await ProposalPlanningRunRepository.set_failed(session, planning_run.id, error=error)

    async def dispatch_github_feedback(self, task_id: uuid.UUID) -> bool:
        """Dispatch a task created from GitHub feedback."""
        async with self._database.session() as session:
            queued = await TaskRepository.queue_github_feedback(session, task_id)
        if queued is None:
            return False

        try:
            dispatched = await self._dispatch(task_id)
        except Exception as exc:
            async with self._database.session() as session:
                await TaskRepository.restore_github_feedback_dispatch(
                    session,
                    task_id,
                    error=f"GitHub feedback dispatch failed: {exc}",
                )
            raise

        if not dispatched:
            async with self._database.session() as session:
                await TaskRepository.restore_github_feedback_dispatch(
                    session,
                    task_id,
                    error="GitHub feedback dispatch skipped because the task is no longer dispatchable.",
                )
        return dispatched

    async def _create_task_record(
        self,
        session: AsyncSession,
        request: TaskCreateRequest,
    ):
        """Persist a task record and related initial state."""
        instance = await AgentInstanceRepository.get(session, request.agent_instance_id)
        if instance is None:
            raise ValueError(f"agent_instance_id={request.agent_instance_id} does not exist")
        if not instance.is_active:
            raise ValueError(f"agent_instance_id={request.agent_instance_id} is inactive")
        if instance.agent.value != request.agent.value:
            raise ValueError(
                f"agent type mismatch: task asks for {request.agent.value} but instance is {instance.agent.value}"
            )

        category = _task_category_for_agent(AgentName(request.agent.value))
        workspace = await WorkspaceRepository.ensure_for_agent_instance(session, instance)
        if not workspace.github_repo or not workspace.project:
            raise ValueError("workspace repo and project are required for task submission")

        # Snapshot the workspace repo/project onto the task so later workspace edits do
        # not rewrite the historical execution context for already-submitted work.
        task = await TaskRepository.create_pending(
            session,
            agent=AgentName(request.agent.value),
            agent_instance_id=request.agent_instance_id,
            category=category,
            question=request.question,
            repo=workspace.github_repo,
            project=workspace.project,
            external_issue_url=request.external_issue_url,
            external_pull_request_url=getattr(request, "external_pull_request_url", None),
        )
        logger.info(f"Agent `{instance.agent.name}` has workspace `{workspace.workspace_key}`")
        return task

    async def _dispatch(self, task_id: uuid.UUID) -> bool:
        """Emit a Celery message for a queued task."""
        async with self._database.session() as session:
            task = await TaskRepository.get(session, task_id)

        if task is None or task.status != TaskStatus.queued:
            logger.warning(f"Failed to dispatch task {task_id} to worker.")
            return False

        celery_app.send_task(
            "nexus.execute_agent_task",
            kwargs={
                "task_id": str(task_id),
            },
            queue=self._settings.celery_queue,
            task_id=str(task_id),
        )
        return True
