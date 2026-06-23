"""Task dispatcher for executor worker.

PostgreSQL stores business state; Celery owns worker delivery and redelivery.
"""

from __future__ import annotations

from dataclasses import dataclass
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from src.logger import logger
from src.server.celery.app import celery_app
from src.server.config import Settings
from src.server.postgres.database import Database
from src.server.postgres.models import AgentName, FeatureItemStatus, TaskCategory, TaskRecord, TaskStatus
from src.server.postgres.repositories import (
    AgentInstanceRepository,
    FeatureItemRepository,
    ProposalPlanningRunRepository,
    TaskRepository,
    WorkspaceRepository,
)


class TaskDispatchError(RuntimeError):
    """Raised when a task cannot be published to the Celery broker."""


@dataclass(frozen=True, slots=True)
class TaskSubmission:
    """Internal command for creating an agent task.

    Args:
        agent_instance_id: Agent instance that should execute the task.
        agent: Internal agent enum expected for the selected instance.
        question: Prompt sent to the agent.
        external_issue_url: Optional external issue URL attached to the task.
    """

    agent_instance_id: uuid.UUID
    agent: AgentName
    question: str
    external_issue_url: str | None = None
    external_pull_request_url: str | None = None

    def __post_init__(self) -> None:
        """Normalize user-facing text while preserving a small validation guard."""
        question = self.question.strip()
        if not question:
            raise ValueError("question cannot be empty")
        object.__setattr__(self, "question", question)

        if self.external_issue_url is not None:
            external_issue_url = self.external_issue_url.strip() or None
            object.__setattr__(self, "external_issue_url", external_issue_url)

        if self.external_pull_request_url is not None:
            external_pull_request_url = self.external_pull_request_url.strip() or None
            object.__setattr__(self, "external_pull_request_url", external_pull_request_url)


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
        submission: TaskSubmission,
        *,
        session: AsyncSession | None = None,
    ) -> TaskRecord:
        # Some callers, such as proposal approval, need the task row to exist inside
        # a larger transaction before dispatch happens so they can attach extra state
        # like proposal-planning tracking rows atomically.
        """Create a task record without dispatching it."""
        if session is not None:
            return await self._create_task_record(session, submission)

        async with self._database.session() as own_session:
            task = await self._create_task_record(own_session, submission)
            await own_session.commit()
            await own_session.refresh(task)
            return task

    async def submit_task(self, submission: TaskSubmission) -> uuid.UUID:
        """Persist and dispatch a new task."""
        async with self._database.session() as session:
            task = await self._create_task_record(session, submission)
            await session.commit()
            await session.refresh(task)
        logger.info(f"Task `{task.id}` is queued.")

        await self._dispatch_or_fail(task.id)
        logger.info(f"Task `{task.id}` has been dispatched for worker.")

        return task.id

    async def shutdown(self) -> None:
        """Shut down runner resources."""
        return None

    async def dispatch_task(
        self,
        task_id: uuid.UUID,
    ) -> bool:
        """Dispatch a task created in a caller-owned transaction."""
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
        """Mark dispatch failure on the task and linked product workflow state."""
        async with self._database.session() as session:
            task = await TaskRepository.set_failed(session, task_id, error=error)
            if task is None:
                return

            if task.category == TaskCategory.coding:
                await FeatureItemRepository.set_status_by_task_id(
                    session,
                    task_id,
                    status=FeatureItemStatus.failed,
                    updated_at=task.finished_at,
                )
                return

            if task.category != TaskCategory.pm:
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
        submission: TaskSubmission,
    ) -> TaskRecord:
        """Persist a task record and related initial state."""
        instance = await AgentInstanceRepository.get(session, submission.agent_instance_id)
        if instance is None:
            raise ValueError(f"agent_instance_id={submission.agent_instance_id} does not exist")
        if not instance.is_active:
            raise ValueError(f"agent_instance_id={submission.agent_instance_id} is inactive")
        if instance.agent != submission.agent:
            raise ValueError(
                f"agent type mismatch: task asks for {submission.agent.value} but instance is {instance.agent.value}"
            )

        category = _task_category_for_agent(submission.agent)
        workspace = await WorkspaceRepository.ensure_for_agent_instance(session, instance)
        if not workspace.github_repo or not workspace.project:
            raise ValueError("workspace repo and project are required for task submission")

        # Snapshot the workspace repo/project onto the task so later workspace edits do
        # not rewrite the historical execution context for already-submitted work.
        task = await TaskRepository.create_pending(
            session,
            agent=submission.agent,
            agent_instance_id=submission.agent_instance_id,
            category=category,
            question=submission.question,
            repo=workspace.github_repo,
            project=workspace.project,
            external_issue_url=submission.external_issue_url,
            external_pull_request_url=submission.external_pull_request_url,
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
