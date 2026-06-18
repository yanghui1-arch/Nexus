from __future__ import annotations

import asyncio
import uuid
from typing import Any

from src.agents.base.agent import WorkTempStatus
from src.logger import logger
from src.server.config import Settings, get_settings
from src.server.postgres.database import Database
from src.server.postgres.models import TaskCategory, TaskRecord, TaskStatus
from src.server.postgres.repositories import TaskRepository

from .state import ExecutionBinding
from . import state, workflows


async def execute_agent_task(
    *,
    task_id: uuid.UUID,
    settings: Settings | None = None,
    allow_running: bool = False,
) -> None:
    """Execute one queued agent task.

    Args:
        task_id: ID of the task to load and execute.
        settings: Optional settings override, mainly used by tests.
        allow_running: Whether an already-running task may be accepted. This is
            used by explicit recovery paths, not normal broker redelivery.

    Raises:
        RuntimeError: If the task, agent instance, or repo/project binding
            cannot be resolved.
        Exception: Re-raises workflow failures after recording the task failure
            in the database.
    """
    cfg = settings or get_settings()
    database = Database(cfg.database_url)
    await database.connect()

    pending_checkpoint_tasks: set[asyncio.Task[Any]] = set()
    pending_event_tasks: set[asyncio.Task[Any]] = set()
    binding: ExecutionBinding | None = None
    task: TaskRecord | None = None
    # Only release a workspace that this delivery actually claimed. A failed
    # task claim must not make an unrelated/stale running task look idle.
    workspace_marked_running = False

    def _schedule_lifecycle_event(status: WorkTempStatus) -> None:
        """Persist agent lifecycle progress without affecting execution flow."""
        if task is None:
            logger.warning("Skipping lifecycle event for missing task %s", task_id)
            return

        safe_metadata = {"process": status["process"]}
        current_tools = status.get("current_use_tool")
        if current_tools is not None:
            safe_metadata["current_use_tool"] = list(current_tools)
        if status.get("current_use_tool_args") is not None:
            safe_metadata["has_tool_args"] = True
        if "context" in status:
            safe_metadata["checkpoint_message_count"] = len(status["context"])

        async def _persist_lifecycle_event() -> None:
            """Persist one structured lifecycle event."""
            async with database.session() as session:
                await TaskRepository.create_execution_event(
                    session,
                    task_id=task_id,
                    event_type=status["process"],
                    agent=task.agent,
                    message=status.get("agent_content"),
                    safe_metadata=safe_metadata,
                )

        async_task = asyncio.create_task(_persist_lifecycle_event())
        pending_event_tasks.add(async_task)

        def _cleanup(done_task: asyncio.Task[Any]) -> None:
            pending_event_tasks.discard(done_task)
            try:
                done_task.result()
            except Exception:
                logger.exception("Lifecycle event persistence failed for task %s", task_id)

        async_task.add_done_callback(_cleanup)

    def on_progress(status: WorkTempStatus) -> None:
        """Persist checkpoint progress emitted by the running agent.

        Args:
            status: Progress payload emitted by ``Agent.work``.

        Raises:
            RuntimeError: If a checkpoint event arrives before the task has
                been loaded.
        """
        if status["process"] != "SAVE_CHECKPOINT":
            _schedule_lifecycle_event(status)

        if status["process"] != "SAVE_CHECKPOINT":
            return

        if task is None:
            raise RuntimeError(f"task_id={task_id} does not exist")

        current_turn_ctx = status["context"]
        checkpoint_payload = list(current_turn_ctx)
        task.checkpoint = checkpoint_payload

        async def _persist_checkpoint() -> None:
            """Persist a safe replay checkpoint."""
            async with database.session() as session:
                await TaskRepository.update_checkpoint(
                    session,
                    task_id,
                    checkpoint=checkpoint_payload,
                )
            logger.info(
                "Agent %s saves checkpoints when executing task %s.",
                task.agent.value,
                task_id,
            )

        async_task = asyncio.create_task(_persist_checkpoint())
        pending_checkpoint_tasks.add(async_task)

        def _cleanup(done_task: asyncio.Task[Any]) -> None:
            """Clean up workflow resources."""
            pending_checkpoint_tasks.discard(done_task)
            try:
                # Surface background persistence exceptions into logs; the return value itself is irrelevant.
                done_task.result()
            except Exception:
                logger.exception("Checkpoint persistence failed for task %s", task_id)

        async_task.add_done_callback(_cleanup)

    try:
        task = await state.load_task(database, task_id)

        if task.status == TaskStatus.running and not allow_running:
            logger.info(
                "Task %s delivery is a duplicate because task is already running; skipping.",
                task_id,
            )
            return

        if task.status not in {TaskStatus.queued, TaskStatus.running}:
            logger.info(
                "Task %s delivery is stale because task is already %s; skipping.",
                task_id,
                task.status.value,
            )
            return

        binding = await state.load_binding(database, task)
        # Populate the in-memory task object so downstream helpers keep reading the
        # resolved repo/project, including legacy rows that still used workspace fallback.
        task.repo = binding.github_repo
        task.project = binding.project

        # Claim the DB task before touching workspace state. The task table is
        # the concurrency gate; marking workspace first can hide a blocked claim.
        running_task = await state.mark_task_running(
            database,
            task_id,
            expected_agent_instance_id=task.agent_instance_id,
            allow_running=allow_running,
        )
        if running_task is None:
            try:
                # Diagnostics are best-effort and read-only. They make the skip
                # actionable without turning a logging failure into task failure.
                claim_snapshot = await state.load_task_claim_failure_snapshot(
                    database,
                    task_id,
                    expected_agent_instance_id=task.agent_instance_id,
                )
            except Exception:
                logger.exception("Failed to load task claim failure snapshot for task %s.", task_id)
                logger.warning(
                    "Task %s could not enter running state; stale delivery will be skipped.",
                    task_id,
                )
            else:
                logger.warning(
                    "Task %s could not enter running state; stale delivery will be skipped. "
                    "current_status=%s current_agent_instance_id=%s expected_agent_instance_id=%s "
                    "allow_running=%s conflicting_running_task_id=%s conflicting_running_task_started_at=%s "
                    "conflicting_running_task_updated_at=%s workspace_status=%s workspace_updated_at=%s",
                    task_id,
                    claim_snapshot.task_status,
                    claim_snapshot.task_agent_instance_id,
                    task.agent_instance_id,
                    allow_running,
                    claim_snapshot.conflicting_running_task_id,
                    claim_snapshot.conflicting_running_task_started_at,
                    claim_snapshot.conflicting_running_task_updated_at,
                    claim_snapshot.workspace_status,
                    claim_snapshot.workspace_updated_at,
                )
            return
        task = running_task

        # From this point on, this delivery owns the workspace lifecycle for the
        # duration of workflow execution and may release it in the finally block.
        await state.mark_workspace_running(database, task.agent_instance_id)
        workspace_marked_running = True

        logger.info(
            "Task %s accepted for execution in workspace %s.",
            task_id,
            binding.workspace_key,
        )

        await workflows.run_agent_workflow(
            database=database,
            task=task,
            on_progress=on_progress,
            settings=cfg,
            user_id=binding.user_id,
            workspace_key=binding.workspace_key,
            github_repo=binding.github_repo,
        )

        if task.category == TaskCategory.coding:
            await state.mark_post_execution_wait_state(database, task_id, None)
            logger.info("Task %s returned to its waiting state.", task_id)

    except Exception as exc:
        logger.exception("Task %s failed in worker", task_id)
        await state.mark_failed(database, task_id, str(exc))
        raise
    finally:
        pending_tasks = [*pending_checkpoint_tasks, *pending_event_tasks]
        if pending_tasks:
            await asyncio.gather(*pending_tasks, return_exceptions=True)

        if binding is not None and task is not None and workspace_marked_running:
            await state.release_workspace(database, task.agent_instance_id)

        await database.disconnect()
