"""Task dispatcher for executor worker.
Task status is stored with a list in Redis and the last element is the latest projection.
PostgreSQL remains the source of truth, and runner recovers undispatched/orphaned tasks on startup.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError

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
from src.server.redis.client import RedisClient
from src.server.schemas import TaskCheckpoint, TaskCreateRequest


def _task_key(task_id: uuid.UUID) -> str:
    """Build a key for task."""
    return f"task:{task_id}:messages"


def _task(
    *,
    status: str,
    description: str | None = None,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "description": description,
        "meta": meta,
    }


class AgentTaskRunner:
    """Dispatches and recover persisted tasks to Celery workers."""

    def __init__(
        self,
        *,
        settings: Settings,
        database: Database,
        redis_client: RedisClient,
    ) -> None:
        self._settings = settings
        self._database = database
        self._redis_client = redis_client

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

            repo = request.repo
            if repo is None:
                raise ValueError("Task repo is required.")

            project = request.project

            task = await TaskRepository.create(
                session,
                agent=AgentName(request.agent.value),
                agent_instance_id=request.agent_instance_id,
                question=request.question,
                repo=repo,
                project=project,
                current_session_ctx=request.current_session_ctx,
                history_session_ctx=request.history_session_ctx,
            )

            workspace = await WorkspaceRepository.ensure_for_agent_instance(session, instance)
            logger.info(f"Agent `{instance.agent.name}` has workspace `{workspace.workspace_key}`")

        task_request = TaskCreateRequest(
            agent_instance_id=request.agent_instance_id,
            agent=request.agent,
            question=request.question,
            repo=task.repo,
            project=task.project,
            current_session_ctx=request.current_session_ctx,
            history_session_ctx=request.history_session_ctx,
            checkpoint=request.checkpoint,
        )

        await self._redis_client.append(
            _task_key(task.id),
            _task(
                status="QUEUED",
                description=(
                    f"{request.agent.value} task queued for Celery worker "
                    f"(agent_instance_id={request.agent_instance_id})."
                ),
                meta={"agent_instance_id": str(request.agent_instance_id)},
            ),
        )
        logger.info(f"Task `{task.id}` is queued.")

        try:
            dispatched = await self._dispatch(task.id, task_request, recovered=False)
            if not dispatched:
                raise RuntimeError(f"Task `{task.id}` is no longer dispatchable (status/lease changed).")
            logger.info(f"Task `{task.id}` has been dispatched for worker.")
        except Exception as exc:
            async with self._database.session() as session:
                await TaskRepository.set_failed(session, task.id, error=f"Dispatch failed: {exc}")
            await self._redis_client.append(
                _task_key(task.id),
                _task(
                    status="FAILED",
                    description=f"Celery dispatch failed: {exc}",
                    meta={"agent_instance_id": str(request.agent_instance_id)},
                ),
            )
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
                await self._redis_client.append(
                    _task_key(task.id),
                    _task(
                        status="SKIPPED",
                        description="Recovery skipped because assigned agent instance is missing or inactive.",
                        meta={"agent_instance_id": str(task.agent_instance_id)},
                    ),
                )
                continue
            
            # recover from checkpoint for running tasks
            checkpoint: TaskCheckpoint | None = None
            if isinstance(task.checkpoint, dict):
                try:
                    checkpoint = TaskCheckpoint.model_validate(task.checkpoint)
                except ValidationError:
                    logger.warning(
                        "Task `%s` has invalid checkpoint payload. Falling back to persisted request context.",
                        task.id,
                    )

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

            request = TaskCreateRequest(
                agent_instance_id=task.agent_instance_id,
                agent=task.agent.value,
                question=task.question,
                repo=task.repo,
                project=task.project,
                current_session_ctx=list(task.requested_current_session_ctx or []),
                history_session_ctx=list(task.requested_history_session_ctx or []),
                checkpoint=checkpoint,
            )

            try:
                dispatched = await self._dispatch(task.id, request, recovered=True)
            except Exception as exc:
                async with self._database.session() as session:
                    await TaskRepository.set_queued(
                        session,
                        task.id,
                        error=f"Recovery dispatch failed: {exc}",
                    )
                await self._redis_client.append(
                    _task_key(task.id),
                    _task(
                        status="FAILED",
                        description=f"Recovery dispatch failed: {exc}",
                        meta={"agent_instance_id": str(task.agent_instance_id)},
                    ),
                )
                logger.exception("Failed to redispatch recovered task %s", task.id)
                continue

            if not dispatched:
                # Another runner may have acquired the lease first.
                logger.warning(
                    "Failed to re-dispatch task %s for worker: another runner may have acquired the lease first.",
                    task.id
                )
                continue

            recovered_count += 1

            description = (
                "Stale running task recovered and re-dispatched to Celery worker."
                if previous_status == TaskStatus.running
                else "Queued task recovered and dispatched to Celery worker."
            )
            await self._redis_client.append(
                _task_key(task.id),
                _task(
                    status="RECOVERED",
                    description=description,
                    meta={
                        "agent_instance_id": str(task.agent_instance_id),
                        "previous_status": previous_status.value,
                        "has_checkpoint": bool(checkpoint),
                    },
                ),
            )

        if recovered_count:
            logger.info("Recovered and dispatched %s unfinished tasks.", recovered_count)
        else:
            logger.warning("No task is recovered and dispatched.")

        return recovered_count

    async def shutdown(self) -> None:
        return None

    async def _dispatch(self, task_id: uuid.UUID, request: TaskCreateRequest, *, recovered: bool) -> bool:
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
                "request_payload": request.model_dump(mode="json"),
                "recovered": recovered,
                # Worker must claim with the same token before it can flip queued -> running.
                "dispatch_token": leased_task.dispatch_token,
            },
            queue=self._settings.celery_queue,
        )
        return True
