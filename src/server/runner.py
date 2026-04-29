"""Task dispatcher for executor worker.

PostgreSQL is the source of truth, and runner recovers undispatched/orphaned tasks on startup.
"""

from __future__ import annotations

import uuid
from typing import Any

from src.logger import logger
from src.server.celery.app import celery_app
from src.server.config import Settings
from src.server.postgres.database import Database
from src.server.postgres.models import AgentName, TaskStatus
from src.server.postgres.repositories import (
    AgentInstanceRepository,
    TaskRepository,
    WorkspaceRepository,
)
from src.server.schemas import TaskCreateRequest


class AgentTaskRunner:
    """Dispatches and recover persisted tasks to Celery workers."""

    def __init__(
        self,
        *,
        settings: Settings,
        database: Database,
    ) -> None:
        self._settings = settings
        self._database = database

    async def submit_task(self, request: TaskCreateRequest) -> uuid.UUID:
        async with self._database.session() as session:
            instance = await AgentInstanceRepository.get(session, request.agent_instance_id)
            if instance is None:
                raise ValueError(f"agent_instance_id={request.agent_instance_id} does not exist")
            if not instance.is_active:
                raise ValueError(f"agent_instance_id={request.agent_instance_id} is inactive")
            if instance.agent.value != request.agent.value:
                raise ValueError(
                    f"agent type mismatch: task asks for {request.agent.value} but instance is {instance.agent.value}"
                )

            current_session_ctx, history_session_ctx = self._load_server_owned_context(request)
            task = await TaskRepository.create(
                session,
                agent=AgentName(request.agent.value),
                agent_instance_id=request.agent_instance_id,
                question=request.question,
                repo=request.repo,
                project=request.project,
                current_session_ctx=current_session_ctx,
                history_session_ctx=history_session_ctx,
            )

            workspace = await WorkspaceRepository.ensure_for_agent_instance(session, instance)
            logger.info(f"Agent `{instance.agent.name}` has workspace `{workspace.workspace_key}`")
        logger.info(f"Task `{task.id}` is queued.")

        try:
            dispatched = await self._dispatch(task.id, recovered=False)
            if not dispatched:
                raise RuntimeError(f"Task `{task.id}` is no longer dispatchable (status/lease changed).")
            logger.info(f"Task `{task.id}` has been dispatched for worker.")
        except Exception as exc:
            async with self._database.session() as session:
                await TaskRepository.set_failed(session, task.id, error=f"Dispatch failed: {exc}")
            logger.error(f"Fail to dispatch task `{task.id}`: {str(exc)}")
            raise

        return task.id

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

            if not task.repo:
                async with self._database.session() as session:
                    await TaskRepository.set_failed(
                        session,
                        task.id,
                        error="Recovery failed: task repo is missing.",
                    )
                logger.warning("Failed to recover task %s because repo is missing.", task.id)
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
        return None

    async def dispatch_existing_task(self, task_id: uuid.UUID, *, recovered: bool = False) -> bool:
        return await self._dispatch(task_id, recovered=recovered)

    def _load_server_owned_context(
        self,
        request: TaskCreateRequest,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Resolve server-owned execution context for a new task submission.

        The public API does not accept session/history context from clients.
        Until a dedicated server-side context source is wired in, new tasks start
        with empty persisted context.
        """
        _ = request
        return [], []

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
