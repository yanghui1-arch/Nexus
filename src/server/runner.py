"""Task dispatcher for executor worker.

PostgreSQL is the source of truth, and runner recovers undispatched/orphaned tasks on startup.
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


def _task_category_for_agent(agent: AgentName) -> TaskCategory:
    """Return the task category used for an agent."""
    if agent == AgentName.marc:
        return TaskCategory.pm
    return TaskCategory.coding


class AgentTaskRunner:
    """Dispatches and recover persisted tasks to Celery workers."""

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

        try:
            dispatched = await self.dispatch_existing_task(
                task.id,
                recovered=False,
                fail_task_on_dispatch_error=True,
            )
            if not dispatched:
                raise RuntimeError(f"Task `{task.id}` is no longer dispatchable (status/lease changed).")
            logger.info(f"Task `{task.id}` has been dispatched for worker.")
        except Exception:
            raise

        return task.id

    async def retry_failed_task(self, task_id: uuid.UUID) -> uuid.UUID:
        """Clone a failed task into a fresh queued task and dispatch it."""
        async with self._database.session() as session:
            source = await TaskRepository.get(session, task_id)
            if source is None:
                raise ValueError("Task not found")
            if source.status != TaskStatus.failed:
                raise ValueError("Only failed tasks can be retried")
            if not source.repo or not source.project:
                raise ValueError("Failed task repo/project context is missing")

            retry = await TaskRepository.create_pending(
                session,
                agent=source.agent,
                agent_instance_id=source.agent_instance_id,
                category=source.category,
                question=source.question,
                repo=source.repo,
                project=source.project,
                external_issue_url=source.external_issue_url,
            )
            await session.commit()
            await session.refresh(retry)

        dispatched = await self.dispatch_existing_task(
            retry.id,
            recovered=False,
            fail_task_on_dispatch_error=True,
        )
        if not dispatched:
            raise RuntimeError(f"Task `{retry.id}` is no longer dispatchable (status/lease changed).")
        logger.info("Failed task `%s` was retried as `%s`.", task_id, retry.id)
        return retry.id

    async def recover_unfinished_tasks(self) -> int:
        """Recover queued/running tasks whose dispatch lease is missing or expired.
        Recover three types task - Queued tasks but not be submitted, Running task but not finalized
        and Queued tasks submitted to worker but exceeds `celery_visibility_timeout_seconds`.

        Returns:
            count of recovering tasks successfully.
        """

        async with self._database.session() as session:
            logger.info("Recovering unfinished tasks.")
            recoverable_tasks = await TaskRepository.list_recoverable(
                session,
                limit=10000,
            )

        recovered_count = 0
        for task in recoverable_tasks:
            async with self._database.session() as session:
                instance = await AgentInstanceRepository.get(session, task.agent_instance_id)
                workspace = await WorkspaceRepository.get_by_agent_instance_id(session, task.agent_instance_id)

            if instance is None or not instance.is_active:
                logger.warning(
                    "Recovery skipped for task %s because assigned agent instance %s is missing or inactive.",
                    task.id,
                    task.agent_instance_id,
                )
                continue

            # recover from checkpoint for running tasks
            # The worker now reads checkpoint/context from PostgreSQL by task_id instead of a synthetic payload.
            previous_status = task.status
            if previous_status == TaskStatus.running:
                # Running + expired lease means the previous worker is considered orphaned.
                async with self._database.session() as session:
                    reset = await TaskRepository.set_queued(
                        session,
                        task.id,
                        error="Recovered stale running task for redispatch after restart.",
                    )
                if reset is None:
                    continue

            # Recovery must preserve the repo/project snapshot captured when the task
            # was created. Legacy rows may still need workspace fallback for one or
            # both fields, so keep that compatibility path here.
            resolved_repo = task.repo or (workspace.github_repo if workspace is not None else None)
            resolved_project = task.project if task.project is not None else (
                workspace.project if workspace is not None else None
            )
            if not resolved_repo or not resolved_project:
                async with self._database.session() as session:
                    await TaskRepository.set_failed(
                        session,
                        task.id,
                        error="Recovery failed: task repo/project context is missing.",
                    )
                logger.warning("Failed to recover task %s because repo/project context is missing.", task.id)
                continue

            try:
                dispatched = await self._dispatch(task.id, recovered=True)
            except Exception as exc:
                async with self._database.session() as session:
                    await TaskRepository.set_queued(
                        session,
                        task.id,
                        error=f"Recovery dispatch failed: {exc}",
                    )
                logger.exception("Failed to redispatch recovered task %s", task.id)
                continue

            if not dispatched:
                # Another runner may have acquired the lease first.
                logger.warning(
                    "Failed to re-dispatch task %s for worker: another runner may have acquired the lease first.",
                    task.id,
                )
                continue

            recovered_count += 1

            logger.info(
                "%s task %s recovered and re-dispatched to Celery worker.",
                "Stale running"
                if previous_status == TaskStatus.running
                else "Queued",
                task.id,
            )

        if recovered_count:
            logger.info("Recovered and dispatched %s unfinished tasks.", recovered_count)
        else:
            logger.warning("No task is recovered and dispatched.")

        return recovered_count

    async def shutdown(self) -> None:
        """Shut down runner resources."""
        return None

    async def dispatch_existing_task(
        self,
        task_id: uuid.UUID,
        *,
        recovered: bool = False,
        fail_task_on_dispatch_error: bool = False,
    ) -> bool:
        """Dispatch an already persisted task."""
        try:
            dispatched = await self._dispatch(task_id, recovered=recovered)
        except Exception as exc:
            if fail_task_on_dispatch_error:
                # New planning flows can opt in here so a dispatch failure is visible
                # on both the task row and the linked planning run instead of leaving
                # the approved proposal in an ambiguous in-between state.
                async with self._database.session() as session:
                    task = await TaskRepository.set_failed(session, task_id, error=f"Dispatch failed: {exc}")
                    if task is not None and task.category == TaskCategory.pm:
                        planning_run = await ProposalPlanningRunRepository.get_by_task_id(session, task_id)
                        if planning_run is not None:
                            await ProposalPlanningRunRepository.set_failed(
                                session,
                                planning_run.id,
                                error=f"Dispatch failed: {exc}",
                            )
                logger.error(f"Fail to dispatch task `{task_id}`: {str(exc)}")
            raise

        if not dispatched and fail_task_on_dispatch_error:
            error = f"Dispatch failed: Task `{task_id}` is no longer dispatchable (status/lease changed)."
            async with self._database.session() as session:
                task = await TaskRepository.set_failed(session, task_id, error=error)
                if task is not None and task.category == TaskCategory.pm:
                    planning_run = await ProposalPlanningRunRepository.get_by_task_id(session, task_id)
                    if planning_run is not None:
                        await ProposalPlanningRunRepository.set_failed(session, planning_run.id, error=error)
            logger.error(error)
        return dispatched

    async def dispatch_github_feedback(self, task_id: uuid.UUID) -> bool:
        """Dispatch a task created from GitHub feedback."""
        async with self._database.session() as session:
            queued = await TaskRepository.queue_github_feedback(session, task_id)
        if queued is None:
            return False

        try:
            dispatched = await self._dispatch(task_id, recovered=False)
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
        )
        logger.info(f"Agent `{instance.agent.name}` has workspace `{workspace.workspace_key}`")
        return task

    async def _dispatch(self, task_id: uuid.UUID, *, recovered: bool) -> bool:
        """Acquire a dispatch lease then emit a Celery message.

        PostgreSQL is the source of truth for lease ownership, so only one dispatcher can
        actively send a broker message for a task at a time.
        """
        async with self._database.session() as session:
            leased_task = await TaskRepository.mark_dispatched(
                session,
                task_id,
                lease_seconds=self._settings.task_dispatch_lease_seconds,
            )

        if leased_task is None or not leased_task.dispatch_token:
            logger.warning(f"Failed to dispatch task {task_id} to worker.")
            return False

        celery_app.send_task(
            "nexus.execute_agent_task",
            kwargs={
                "task_id": str(task_id),
                "recovered": recovered,
                # Worker must claim with the same token before it can flip queued -> running.
                "dispatch_token": leased_task.dispatch_token,
            },
            queue=self._settings.celery_queue,
        )
        return True
