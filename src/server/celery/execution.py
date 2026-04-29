from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from typing import Any, Literal

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
    TaskWorkItemRepository,
    VirtualPullRequestRepository,
    WorkspaceRepository,
)
from src.tools.nexus import NexusTaskContext


__all__ = ["execute_agent_task"]

_agents: dict[str, Any] = {
    "tela": Tela,
    "sophie": Sophie,
}


@dataclass(frozen=True)
class _ExecutionBinding:
    github_repo: str | None
    workspace_key: str


@dataclass(frozen=True)
class _ExecutionOutcome:
    status: Literal["waiting", "waiting_for_merge"]
    response: str | None


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
                    current_turn_ctx_json.append(message.model_dump(exclude_none=True))
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

        outcome = await _run_agent_workflow(
            database=database,
            task=task,
            on_progress=on_progress,
            settings=cfg,
            workspace_key=binding.workspace_key,
            github_repo=binding.github_repo,
            recovered=recovered,
        )

        if outcome.status == "waiting":
            await _mark_waiting(database, task_id, outcome.response)
            logger.info("Task %s moved to waiting for Nexus virtual PR review.", task_id)
        else:
            await _mark_waiting_for_merge(database, task_id, outcome.response)
            logger.info("Task %s moved to waiting_for_merge after final PR run.", task_id)

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


async def _run_agent_workflow(
    *,
    database: Database,
    task: TaskRecord,
    on_progress,
    settings: Settings,
    workspace_key: str,
    github_repo: str | None,
    recovered: bool,
) -> _ExecutionOutcome:
    planning_recovered = recovered

    while True:
        async with database.session() as session:
            work_items = await TaskWorkItemRepository.list_by_task(session, task.id)
            all_approved = await TaskWorkItemRepository.all_approved(session, task.id)
            running_work_item = await TaskWorkItemRepository.get_running(session, task.id)
            next_work_item = await TaskWorkItemRepository.get_next_for_execution(session, task.id)

        if not work_items:
            logger.info("Task %s has no Nexus work items; starting planning/small-task run.", task.id)
            result = await _run_agent(
                task=task,
                on_progress=on_progress,
                settings=settings,
                workspace_key=workspace_key,
                github_repo=github_repo,
                recovered=planning_recovered,
                nexus_context=NexusTaskContext(
                    task_id=task.id,
                    database=database,
                    repo=task.repo or github_repo or "",
                ),
                question_override=_build_planning_prompt(task.question),
            )
            planning_recovered = False

            async with database.session() as session:
                work_items = await TaskWorkItemRepository.list_by_task(session, task.id)
            if not work_items:
                logger.info(
                    "Task %s completed without Nexus work items; treating as small-task external PR run.",
                    task.id,
                )
                return _ExecutionOutcome(status="waiting_for_merge", response=result.response)

            logger.info(
                "Task %s was split into %s Nexus work items.",
                task.id,
                len(work_items),
            )
            continue

        if all_approved:
            logger.info("Task %s has all Nexus work items approved; starting final PR run.", task.id)
            result = await _run_agent(
                task=task,
                on_progress=on_progress,
                settings=settings,
                workspace_key=workspace_key,
                github_repo=github_repo,
                recovered=False,
                nexus_context=NexusTaskContext(
                    task_id=task.id,
                    database=database,
                    repo=task.repo or github_repo or "",
                ),
                question_override=_build_final_pr_prompt(task.question, work_items),
            )
            return _ExecutionOutcome(status="waiting_for_merge", response=result.response)

        work_item = running_work_item
        if work_item is None and next_work_item is not None:
            async with database.session() as session:
                work_item = await TaskWorkItemRepository.set_running(session, next_work_item.id)
            if work_item is None:
                raise RuntimeError(f"Failed to start Nexus work item {next_work_item.id}.")

        if work_item is None:
            logger.info("Task %s has no executable work item; waiting for Nexus review.", task.id)
            return _ExecutionOutcome(status="waiting", response="Waiting for Nexus virtual PR review.")

        logger.info(
            "Task %s starting Nexus work item %s: %s",
            task.id,
            work_item.order_index,
            work_item.title,
        )
        result = await _run_agent(
            task=task,
            on_progress=on_progress,
            settings=settings,
            workspace_key=workspace_key,
            github_repo=github_repo,
            recovered=False,
            nexus_context=NexusTaskContext(
                task_id=task.id,
                database=database,
                repo=task.repo or github_repo or "",
                current_work_item_id=work_item.id,
            ),
            question_override=_build_work_item_prompt(task.question, work_item),
        )

        async with database.session() as session:
            refreshed = await TaskWorkItemRepository.get(session, work_item.id)
            virtual_pr = await VirtualPullRequestRepository.get_by_work_item(session, work_item.id)

        if refreshed is None:
            raise RuntimeError(f"Nexus work item {work_item.id} disappeared during execution.")
        if virtual_pr is None or refreshed.status.value != "ready_for_review":
            raise RuntimeError(
                "Agent finished a Nexus work item without calling finish_current_task_work_item."
            )

        logger.info(
            "Task %s work item %s is ready for Nexus review.",
            task.id,
            refreshed.order_index,
        )
        return _ExecutionOutcome(status="waiting", response=result.response)


async def _run_agent(
    *,
    task: TaskRecord,
    on_progress,
    settings: Settings,
    workspace_key: str,
    github_repo: str | None,
    recovered: bool,
    nexus_context: NexusTaskContext | None = None,
    question_override: str | None = None,
) -> BaseAgentResponse:
    agent = _build_agent(
        task=task,
        settings=settings,
        workspace_key=workspace_key,
        github_repo=github_repo,
        nexus_context=nexus_context,
    )

    try:
        async with agent:
            work_kwargs = {
                "question": question_override or task.question,
                "current_session_ctx": task.requested_current_session_ctx or [],
                "history_session_ctx": task.requested_history_session_ctx or [],
                "update_process_callback": on_progress,
            }
            checkpoint = task.checkpoint if recovered else None
            if checkpoint:
                work_kwargs["from_checkpoint"] = True
                work_kwargs["checkpoint"] = checkpoint
            return await agent.work(**work_kwargs)
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
    nexus_context: NexusTaskContext | None = None,
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
        "nexus_task_context": nexus_context,
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


def _build_planning_prompt(question: str) -> str:
    return (
        "Original task:\n"
        f"{question}\n\n"
        "Decide whether this task is small or needs Nexus internal review work items. "
        "If the expected added, edited, or removed lines exceed about 200 lines, call "
        "create_task_work_items with ordered review-sized work items and then stop. "
        "Do not create GitHub issues or sub-issues. If the task is small, implement it normally "
        "and create one real external pull request."
    )


def _build_work_item_prompt(question: str, work_item: Any) -> str:
    return (
        "Original task:\n"
        f"{question}\n\n"
        "Nexus assigned this internal review work item:\n"
        f"Order: {work_item.order_index}\n"
        f"Title: {work_item.title}\n"
        f"Description: {work_item.description}\n\n"
        "Implement only this work item. Fetch the repository before editing so Nexus can capture "
        "the base commit. Commit this work item's scoped changes before finishing; the Nexus "
        "virtual PR is built from base_commit..head_commit. Do not create GitHub issues, "
        "sub-issues, or external pull requests for this work item. When the scoped implementation "
        "is complete, call "
        "finish_current_task_work_item with a concise reviewer-facing summary."
    )


def _build_final_pr_prompt(question: str, work_items: list[Any]) -> str:
    item_summaries = "\n".join(
        f"- {item.order_index}. {item.title}: {item.summary or item.description}"
        for item in work_items
    )
    return (
        "All Nexus virtual PR work items for this task are approved.\n\n"
        "Original task:\n"
        f"{question}\n\n"
        "Approved work items:\n"
        f"{item_summaries}\n\n"
        "Create one real external GitHub pull request for the accumulated approved changes. "
        "Do not create more Nexus work items, GitHub issues, sub-issues, or multiple external PRs."
    )


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


async def _mark_waiting(database: Database, task_id: uuid.UUID, result: str | None) -> None:
    async with database.session() as session:
        await TaskRepository.set_waiting(session, task_id, result=result)


async def _mark_failed(database: Database, task_id: uuid.UUID, error: str) -> None:
    async with database.session() as session:
        await TaskRepository.set_failed(session, task_id, error=error)
