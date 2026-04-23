from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from typing import Any

from openai.types.chat import ChatCompletionMessage

from src.agents import Sophie, Tela
from src.agents.base.agent import Agent, BaseAgentResponse, WorkTempStatus
from src.logger import logger
from src.server.config import Settings, get_settings
from src.server.postgres.database import Database
from src.server.postgres.models import AgentName, TaskRecord
from src.server.postgres.repositories import (
    AgentInstanceRepository,
    TaskRepository,
    WorkspaceRepository,
)


__all__ = ["execute_agent_task"]

_agents: dict[str, Any] = {
    "tela": Tela,
    "sophie": Sophie,
}


@dataclass(frozen=True)
class _ExecutionBinding:
    github_repo: str | None
    workspace_key: str


async def execute_agent_task(
    *,
    task_id: uuid.UUID,
    settings: Settings | None = None,
    recovered: bool = False,
    dispatch_token: str | None = None,
) -> None:
    cfg = settings or get_settings()
    database = Database(cfg.database_url)
    await database.connect()

    pending_checkpoint_tasks: set[asyncio.Task[Any]] = set()
    stop_lease_heartbeat = asyncio.Event()
    lease_heartbeat_task: asyncio.Task[Any] | None = None
    binding: _ExecutionBinding | None = None
    task: TaskRecord | None = None

    def on_progress(status: WorkTempStatus) -> None:
        if status["process"] != "SAVE_CHECKPOINT":
            return

        async def _persist_checkpoint() -> None:
            if task is None:
                raise RuntimeError(f"task_id={task_id} does not exist")

            # SAVE_CHECKPOINT marks a safe replay boundary for persistence.
            current_turn_ctx = status.get("context", [])
            if len(current_turn_ctx) == 0:
                logger.warning(
                    "Agent %s save checkpoints size: 0 for task %s",
                    task.agent.value,
                    task_id,
                )
            current_turn_ctx_json = []
            for message in current_turn_ctx:
                if isinstance(message, ChatCompletionMessage):
                    current_turn_ctx_json.append(message.model_dump_json(exclude_none=True))
                else:
                    current_turn_ctx_json.append(message)

            async with database.session() as session:
                await TaskRepository.update_checkpoint(
                    session,
                    task_id,
                    checkpoint=current_turn_ctx_json,
                )
            logger.info(
                "Agent %s saves checkpoints when executing task %s.",
                task.agent.value,
                task_id,
            )

        async_task = asyncio.create_task(_persist_checkpoint())
        pending_checkpoint_tasks.add(async_task)

        def _cleanup(done_task: asyncio.Task[Any]) -> None:
            pending_checkpoint_tasks.discard(done_task)
            try:
                # Surface background persistence exceptions into logs; the return value itself is irrelevant.
                done_task.result()
            except Exception:
                logger.exception("Checkpoint persistence failed for task %s", task_id)

        async_task.add_done_callback(_cleanup)

    try:
        task = await _load_task(database, task_id)

        if not dispatch_token:
            logger.warning("Worker message missing dispatch token; skip execution and wait for redispatch.")
            return

        binding = await _load_binding(database, task)
        await _set_workspace_running(database, task.agent_instance_id, binding.github_repo)

        # Worker can start only if it proves it owns the latest dispatch lease token.
        started = await _claim_running(
            database,
            task_id,
            dispatch_token=dispatch_token,
            lease_seconds=cfg.task_dispatch_lease_seconds,
            expected_agent_instance_id=task.agent_instance_id,
        )
        if not started:
            logger.warning(
                "Task %s lease claim failed; stale or duplicate broker delivery will be skipped.",
                task_id,
            )
            return

        # Heartbeat keeps lease fresh so recovery only picks truly orphaned running tasks.
        lease_heartbeat_task = asyncio.create_task(
            _lease_heartbeat(
                database=database,
                task_id=task_id,
                dispatch_token=dispatch_token,
                lease_seconds=cfg.task_dispatch_lease_seconds,
                stop_event=stop_lease_heartbeat,
            )
        )

        logger.info(
            "%s task %s accepted for execution in workspace %s.",
            "Recovered"
            if recovered
            else "Fresh",
            task_id,
            binding.workspace_key,
        )

        result = await _run_agent(
            task=task,
            on_progress=on_progress,
            settings=cfg,
            workspace_key=binding.workspace_key,
            github_repo=binding.github_repo,
        )

        await _mark_waiting_for_merge(database, task_id, result.response)
        logger.info(
            "Task %s moved to waiting_for_merge. has_sop=%s",
            task_id,
            bool(result.sop),
        )

    except Exception as exc:
        logger.exception("Task %s failed in worker", task_id)
        await _mark_failed(database, task_id, str(exc))
        raise
    finally:
        stop_lease_heartbeat.set()

        awaitables: list[asyncio.Task[Any]] = []
        if pending_checkpoint_tasks:
            awaitables.extend(pending_checkpoint_tasks)
        if lease_heartbeat_task is not None:
            awaitables.append(lease_heartbeat_task)

        if awaitables:
            await asyncio.gather(*awaitables, return_exceptions=True)

        if binding is not None and task is not None:
            await _release_workspace(database, task.agent_instance_id)

        await database.disconnect()


async def _run_agent(
    *,
    task: TaskRecord,
    on_progress,
    settings: Settings,
    workspace_key: str,
    github_repo: str | None,
) -> BaseAgentResponse:
    agent = _build_agent(
        task=task,
        settings=settings,
        workspace_key=workspace_key,
        github_repo=github_repo,
    )

    try:
        async with agent:
            return await agent.work(
                question=task.question,
                current_session_ctx=list(task.requested_current_session_ctx or []),
                history_session_ctx=list(task.requested_history_session_ctx or []),
                update_process_callback=on_progress,
            )
    finally:
        # `run_agent_task` uses `asyncio.run(...)` per task; close agent-owned async resources
        # before loop teardown.
        await agent.close()


def _build_agent(
    *,
    task: TaskRecord,
    settings: Settings,
    workspace_key: str,
    github_repo: str | None,
) -> Agent:
    api_key = settings.api_key
    if not api_key:
        raise RuntimeError("NEXUS_API_KEY is required.")

    resolved_repo = task.repo or github_repo
    if not resolved_repo:
        raise RuntimeError("Missing task repo.")

    shared = {
        "base_url": settings.base_url,
        "api_key": api_key,
        "model": settings.model,
        "max_context": settings.max_context,
        "max_attempts": settings.max_attempts,
        "github_repo": resolved_repo,
        "sandbox_workspace_key": workspace_key,
    }

    agent_name = task.agent.value
    agent_builder: Agent = _agents.get(agent_name)
    github_token = settings.github_tokens.get(agent_name)
    if not agent_builder:
        raise RuntimeError(
            f"Task {task.id} failed to create agent `{agent_name}` due to invalid agent name."
            f" Detailed task repo({task.repo})"
        )
    if not github_token:
        raise RuntimeError(
            f"Task {task.id} failed to create agent `{agent_name}` without github token."
            " Currently Nexus only supports coding agent. Every coding agent should have a github token now."
        )

    return agent_builder.create(**shared, github_token=github_token)


async def _load_task(database: Database, task_id: uuid.UUID) -> TaskRecord:
    async with database.session() as session:
        task = await TaskRepository.get(session, task_id)
    if task is None:
        raise RuntimeError(f"task_id={task_id} does not exist")
    return task


async def _load_binding(database: Database, task: TaskRecord) -> _ExecutionBinding:
    """Ensure the agent instance workspace exists and resolve the task binding."""

    async with database.session() as session:
        instance = await AgentInstanceRepository.get(session, task.agent_instance_id)
        if instance is None:
            raise RuntimeError(f"agent_instance_id={task.agent_instance_id} does not exist")
        if not instance.is_active:
            raise RuntimeError(f"agent_instance_id={task.agent_instance_id} is inactive")
        if instance.agent.value != task.agent.value:
            raise RuntimeError(
                f"task agent {task.agent.value} does not match instance agent {instance.agent.value}"
            )

        github_repo = task.repo
        if github_repo is None:
            raise RuntimeError("Missing task repo.")

        workspace = await WorkspaceRepository.ensure_for_agent_instance(
            session,
            instance,
        )

    return _ExecutionBinding(
        github_repo=github_repo,
        workspace_key=workspace.workspace_key,
    )


async def _claim_running(
    database: Database,
    task_id: uuid.UUID,
    *,
    dispatch_token: str,
    lease_seconds: int,
    expected_agent_instance_id: uuid.UUID,
) -> bool:
    async with database.session() as session:
        task = await TaskRepository.claim_dispatched_running(
            session,
            task_id,
            dispatch_token=dispatch_token,
            lease_seconds=lease_seconds,
            expected_agent_instance_id=expected_agent_instance_id,
        )
        return task is not None


async def _lease_heartbeat(
    *,
    database: Database,
    task_id: uuid.UUID,
    dispatch_token: str,
    lease_seconds: int,
    stop_event: asyncio.Event,
) -> None:
    interval_seconds = max(1, lease_seconds // 3)

    while not stop_event.is_set():
        extended = await _extend_lease(
            database,
            task_id,
            dispatch_token=dispatch_token,
            lease_seconds=lease_seconds,
        )
        if not extended:
            logger.warning(
                "Stop lease heartbeat for task %s because lease extension failed.",
                task_id,
            )
            return

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
        except asyncio.TimeoutError:
            continue


async def _extend_lease(
    database: Database,
    task_id: uuid.UUID,
    *,
    dispatch_token: str,
    lease_seconds: int,
) -> bool:
    async with database.session() as session:
        return await TaskRepository.extend_lease(
            session,
            task_id,
            dispatch_token=dispatch_token,
            lease_seconds=lease_seconds,
            require_running=True,
        )


async def _set_workspace_running(
    database: Database,
    agent_instance_id: uuid.UUID,
    github_repo: str | None,
) -> None:
    if github_repo is None:
        raise RuntimeError("Missing task repo.")

    async with database.session() as session:
        await WorkspaceRepository.set_running(
            session,
            agent_instance_id=agent_instance_id,
            github_repo=github_repo,
        )


async def _release_workspace(database: Database, agent_instance_id: uuid.UUID) -> None:
    """Release workspace not delete.
    Set workspace status as idle and reset repo as None if agent instance is active. Else set workspace as inactive and clear repo.
    """

    async with database.session() as session:
        instance = await AgentInstanceRepository.get(session, agent_instance_id)
        if instance is None:
            return

        if instance.is_active:
            await WorkspaceRepository.set_idle(
                session,
                agent_instance_id=agent_instance_id,
            )
        else:
            await WorkspaceRepository.set_inactive(
                session,
                agent_instance_id=agent_instance_id,
            )


async def _mark_waiting_for_merge(database: Database, task_id: uuid.UUID, result: str | None) -> None:
    async with database.session() as session:
        await TaskRepository.set_waiting_for_merge(session, task_id, result=result)


async def _mark_failed(database: Database, task_id: uuid.UUID, error: str) -> None:
    async with database.session() as session:
        await TaskRepository.set_failed(session, task_id, error=error)
