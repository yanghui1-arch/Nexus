from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from typing import Any, cast

from openai.types.chat import ChatCompletionMessage
from openai.types.chat.chat_completion_message_param import ChatCompletionMessageParam

from src.agents import Marc, Sophie, Tela
from src.agents.base.agent import Agent, BaseAgentResponse, WorkTempStatus
from src.logger import logger
from src.server.config import Settings, get_settings
from src.server.postgres.database import Database
from src.server.postgres.models import (
    GithubPullRequestFeedbackKind,
    GithubPullRequestFeedbackRecord,
    TaskCategory,
    TaskRecord,
    TaskStatus,
    TaskWorkItemRecord,
    TaskWorkItemStatus,
)
from src.server.postgres.repositories import (
    AgentInstanceRepository,
    GithubPullRequestFeedbackRepository,
    TaskRepository,
    TaskWorkItemRepository,
    WorkspaceRepository,
)
from src.tools.nexus import NexusTaskContext


__all__ = ["execute_agent_task"]

_agents: dict[str, Any] = {
    "tela": Tela,
    "sophie": Sophie,
    "marc": Marc,
}
_CODING_AGENTS = {"tela", "sophie"}
_WORK_ITEM_REVIEW_READY_STATUSES = {
    TaskWorkItemStatus.ready_for_review,
    TaskWorkItemStatus.approved,
    TaskWorkItemStatus.closed,
}


@dataclass(frozen=True)
class _ExecutionBinding:
    github_repo: str | None
    project: str | None
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

        if task is None:
            raise RuntimeError(f"task_id={task_id} does not exist")

        current_turn_ctx = status.get("context", [])
        if len(current_turn_ctx) == 0:
            logger.warning(
                "Agent %s save checkpoints size: 0 for task %s",
                task.agent.value,
                task_id,
            )

        checkpoint_payload: list[ChatCompletionMessageParam] = [
            cast(ChatCompletionMessageParam, message.model_dump(exclude_none=True))
            if isinstance(message, ChatCompletionMessage)
            else message
            for message in current_turn_ctx
        ]
        task.checkpoint = checkpoint_payload

        async def _persist_checkpoint() -> None:
            # SAVE_CHECKPOINT marks a safe replay boundary for persistence.
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
        task.repo = binding.github_repo
        task.project = binding.project
        await _set_workspace_running(
            database,
            task.agent_instance_id,
            binding.github_repo,
            binding.project,
        )

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

        await _run_agent_workflow(
            database=database,
            task=task,
            on_progress=on_progress,
            settings=cfg,
            workspace_key=binding.workspace_key,
            github_repo=binding.github_repo,
            recovered=recovered,
        )

        if task is not None and task.category == TaskCategory.coding:
            await _mark_post_execution_wait_state(database, task_id, None)
            logger.info("Task %s returned to its waiting state.", task_id)

    except BaseException as exc:
        if _is_worker_shutdown_exception(exc):
            logger.warning("Task %s was interrupted by worker shutdown; queueing it for redispatch.", task_id)
            await _mark_queued_for_redispatch(database, task_id)
            return
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
):
    if task.category == TaskCategory.coding:
        await _run_code_agent_workflow(
            database=database,
            task=task,
            on_progress=on_progress,
            settings=settings,
            workspace_key=workspace_key,
            github_repo=github_repo,
            recovered=recovered,
        )
        return
    if task.category == TaskCategory.pm:
        await _run_pm_agent_workflow(
            database=database,
            task=task,
            on_progress=on_progress,
            settings=settings,
            workspace_key=workspace_key,
            github_repo=github_repo,
        )
        return
    raise RuntimeError(f"Unsupported task category: {task.category}")


async def _run_code_agent_workflow(
    *,
    database: Database,
    task: TaskRecord,
    on_progress,
    settings: Settings,
    workspace_key: str,
    github_repo: str | None,
    recovered: bool,
):
    nexus_context = NexusTaskContext(
        task_id=task.id,
        database=database,
        repo=task.repo or github_repo or "",
    )
    agent = _build_agent(
        task=task,
        settings=settings,
        workspace_key=workspace_key,
        github_repo=github_repo,
    )
    if hasattr(agent, "set_nexus_task_context"):
        agent.set_nexus_task_context(nexus_context)

    async with agent:
        checkpoint: list[ChatCompletionMessageParam] = await _get_latest_checkpoint(database, task.id)
        claimed_feedback = await _claim_pending_github_feedback(
            database,
            task.id,
            limit=getattr(settings, "github_feedback_batch_size", 20),
        )
        if claimed_feedback:
            logger.info(
                "Task %s is resuming from checkpoint to process %s GitHub feedback item(s).",
                task.id,
                len(claimed_feedback),
            )
            nexus_context.current_work_item_id = None
            try:
                await _run_agent(
                    agent=agent,
                    question=_build_github_feedback_prompt(task, claimed_feedback),
                    checkpoint=checkpoint,
                    on_progress=on_progress,
                )
            except Exception:
                await _requeue_github_feedback(database, claimed_feedback)
                raise
            await _mark_github_feedback_processed(database, claimed_feedback)
            return

        while True:
            async with database.session() as session:
                work_items = await TaskWorkItemRepository.list_by_task(session, task.id)
            # refresh to get the latest checkpoint
            # pass checkpoint whether the task is recovered or not.
            checkpoint = await _get_latest_checkpoint(database, task.id)

            # first not work_items -> run once
            # agent maybe generate work_items also maybe not.
            if not work_items:
                logger.info("Task %s has no Nexus work items; starting normal task run.", task.id)
                nexus_context.current_work_item_id = None
                # first run agent pass original task.question
                await _run_agent(
                    agent=agent,
                    question=task.question,
                    checkpoint=checkpoint,
                    on_progress=on_progress,
                )

                # refresh because agent probably generates work items in its execution.
                async with database.session() as session:
                    work_items = await TaskWorkItemRepository.list_by_task(session, task.id)
                if not work_items:
                    logger.info(
                        "Task %s completed without Nexus work items; treating as "
                        "small-task external PR run.",
                        task.id,
                    )
                    break

                logger.info(
                    "Task %s was split into %s work items by agent %s.",
                    task.id,
                    len(work_items),
                    agent.name,
                )
                continue

            if _all_work_items_review_ready(work_items):
                logger.info("Task %s has no executable work items; waiting for review.", task.id)
                break

            # solve work_item one by one
            work_item: TaskWorkItemRecord = await _claim_next_work_item(database, task.id)
            if work_item is None:
                logger.info("Task %s has no executable work item; waiting for Nexus review.", task.id)
                break

            logger.info(
                "Task %s starting Nexus work item %s: %s",
                task.id,
                work_item.order_index,
                work_item.title,
            )
            nexus_context.current_work_item_id = work_item.id
            # qustion is the current question not task.question
            await _run_agent(
                agent=agent,
                question=_build_work_item_prompt(
                    work_item,
                    is_final_work_item=_is_final_executable_work_item(work_items, work_item.id),
                ),
                checkpoint=checkpoint,
                on_progress=on_progress,
            )

            async with database.session() as session:
                refreshed = await TaskWorkItemRepository.get(session, work_item.id)

            if refreshed is None:
                raise RuntimeError(f"Work item {work_item.id} of task {task.id} disappeared during execution.")
            if refreshed.status.value != "ready_for_review":
                raise RuntimeError(
                    "Agent finished a work item without calling finish_current_task_work_item."
                )

            logger.info(
                "Task %s work item %s is ready for review.",
                task.id,
                refreshed.order_index,
            )


async def _run_pm_agent_workflow(
    *,
    database: Database,
    task: TaskRecord,
    on_progress,
    settings: Settings,
    workspace_key: str,
    github_repo: str | None,
):
    nexus_context = NexusTaskContext(
        task_id=task.id,
        database=database,
        repo=task.repo or github_repo or "",
    )
    agent = _build_agent(
        task=task,
        settings=settings,
        workspace_key=workspace_key,
        github_repo=github_repo,
    )
    if hasattr(agent, "set_nexus_task_context"):
        agent.set_nexus_task_context(nexus_context)
    async with agent:
        checkpoint = await _get_latest_checkpoint(database, task.id)
        response = await _run_agent(
            agent=agent,
            question=task.question,
            checkpoint=checkpoint,
            on_progress=on_progress,
        )
    await _mark_waiting_for_review(database, task.id, response.response)


def _all_work_items_review_ready(work_items: list[TaskWorkItemRecord]) -> bool:
    return bool(work_items) and all(
        work_item.status in _WORK_ITEM_REVIEW_READY_STATUSES
        for work_item in work_items
    )


def _is_final_executable_work_item(work_items: list[TaskWorkItemRecord], work_item_id: uuid.UUID) -> bool:
    return all(
        work_item.id == work_item_id or work_item.status in _WORK_ITEM_REVIEW_READY_STATUSES
        for work_item in work_items
    )


async def _claim_next_work_item(database: Database, task_id: uuid.UUID) -> TaskWorkItemRecord:
    async with database.session() as session:
        running_work_item = await TaskWorkItemRepository.get_running(session, task_id)
        if running_work_item is not None:
            return running_work_item

        next_work_item = await TaskWorkItemRepository.get_next_for_execution(session, task_id)
        if next_work_item is None:
            return None

        work_item = await TaskWorkItemRepository.set_running(session, next_work_item.id)
        if work_item is None:
            raise RuntimeError(f"Failed to start Nexus work item {next_work_item.id}.")
        return work_item

async def _run_agent(
    *,
    agent: Agent,
    question: str,
    checkpoint: list[ChatCompletionMessageParam] | None = None,
    on_progress,
) -> BaseAgentResponse:
    work_kwargs = {
        "question": question,
        "update_process_callback": on_progress,
        "from_checkpoint": bool(checkpoint),
    }
    if checkpoint:
        work_kwargs["checkpoint"] = checkpoint
    return await agent.work(**work_kwargs)


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

    agent_name = task.agent.value
    resolved_repo = task.repo or github_repo
    if agent_name in _CODING_AGENTS and not resolved_repo:
        raise RuntimeError("Missing task repo.")

    shared = {
        "base_url": settings.base_url,
        "api_key": api_key,
        "model": settings.model,
        "max_context": settings.max_context,
        "max_attempts": settings.max_attempts,
    }

    agent_builder: Agent = _agents.get(agent_name)
    if not agent_builder:
        raise RuntimeError(
            f"Task {task.id} failed to create agent `{agent_name}` due to invalid agent name."
            f" Detailed task repo({task.repo})"
        )

    github_token = settings.github_tokens.get(agent_name)
    if agent_name in _CODING_AGENTS:
        if not github_token:
            raise RuntimeError(f"Task {task.id} failed to create coding agent `{agent_name}` without github token.")
        return agent_builder.create(
            **shared,
            github_repo=resolved_repo,
            sandbox_workspace_key=workspace_key,
            github_token=github_token,
        )

    if resolved_repo or github_token:
        return agent_builder.create(
            **shared,
            github_repo=resolved_repo,
            github_token=github_token,
        )

    return agent_builder.create(**shared)


def _build_work_item_prompt(
    work_item: TaskWorkItemRecord,
    *,
    is_final_work_item: bool = False,
) -> str:
    external_pr_instruction = (
        "This is the final executable work item. After committing the scoped changes, "
        "create or update exactly one real GitHub pull request for the accumulated "
        "task changes, then call finish_current_task_work_item. "
    ) if is_final_work_item else (
        "Do not create a github pull request for this work item. "
    )

    return (
        f"Implement only this work item {work_item.title}. Commit this work item's scoped changes before finishing; "
        "Nexus records this work item's review scope from base_commit..head_commit. "
        f"{external_pr_instruction}"
        "When the scoped implementation is complete, call finish_current_task_work_item"
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
        project = task.project
        if task.agent.value in _CODING_AGENTS and github_repo is None:
            raise RuntimeError("Missing task repo.")

        workspace = await WorkspaceRepository.ensure_for_agent_instance(
            session,
            instance,
        )

    return _ExecutionBinding(
        github_repo=github_repo,
        project=project,
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
    project: str | None,
) -> None:
    if github_repo is None and project is None:
        raise RuntimeError("Missing task repo/project.")
    async with database.session() as session:
        await WorkspaceRepository.set_running(
            session,
            agent_instance_id=agent_instance_id,
            github_repo=github_repo or "",
            project=project
        )

async def _get_latest_checkpoint(database: Database, task_id: uuid.UUID) -> list[ChatCompletionMessageParam]:
    task = await _load_task(database, task_id)
    return task.checkpoint if task.checkpoint is not None else []


async def _release_workspace(database: Database, agent_instance_id: uuid.UUID) -> None:
    """Release workspace not delete.
    Set workspace status as idle/inactive while preserving the agent binding.
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


async def _mark_waiting_for_review(database: Database, task_id: uuid.UUID, result: str | None) -> None:
    async with database.session() as session:
        await TaskRepository.set_waiting_for_review(session, task_id, result=result)


async def _mark_post_execution_wait_state(
    database: Database,
    task_id: uuid.UUID,
    result: str | None,
) -> None:
    async with database.session() as session:
        task = await TaskRepository.get(session, task_id)
        if task is None:
            return
        if task.status in {
            TaskStatus.merged,
            TaskStatus.closed,
            TaskStatus.failed,
        }:
            return
        await TaskRepository.set_waiting_for_review(session, task_id, result=result)


async def _claim_pending_github_feedback(
    database: Database,
    task_id: uuid.UUID,
    *,
    limit: int,
) -> list[GithubPullRequestFeedbackRecord]:
    async with database.session() as session:
        return await GithubPullRequestFeedbackRepository.claim_pending_by_task(
            session,
            task_id,
            limit=limit,
        )


async def _mark_github_feedback_processed(
    database: Database,
    feedback_items: list[GithubPullRequestFeedbackRecord],
) -> None:
    async with database.session() as session:
        await GithubPullRequestFeedbackRepository.mark_processed(
            session,
            [item.id for item in feedback_items],
        )


async def _requeue_github_feedback(
    database: Database,
    feedback_items: list[GithubPullRequestFeedbackRecord],
) -> None:
    async with database.session() as session:
        await GithubPullRequestFeedbackRepository.requeue_processing(
            session,
            [item.id for item in feedback_items],
        )


def _build_github_feedback_prompt(
    task: TaskRecord,
    feedback_items: list[GithubPullRequestFeedbackRecord],
) -> str:
    pull_number = feedback_items[0].pull_request_number
    lines = [
        "Continue the current task.",
        f"There is new GitHub feedback on the existing pull request #{pull_number} in {task.repo}.",
        "This is not a new task and you must not open a new pull request.",
        "If code changes are needed, update the existing branch/PR and then reply on GitHub.",
        "If a `pr_merge_conflict` item is present, resolve the merge conflicts locally and push the existing PR branch again.",
        "Use `reply_to_pr` for `pr_comment`, `pr_review`, and `pr_merge_conflict` items.",
        "Use `reply_to_pr_review_comment` for `pr_review_comment` items with the exact `comment_id` shown below.",
        "Handle every feedback item exactly once.",
        "",
        "Feedback items:",
    ]

    for index, item in enumerate(feedback_items, start=1):
        reply_tool = (
            f"reply_to_pr_review_comment(pull_number={pull_number}, comment_id={item.external_id})"
            if item.kind == GithubPullRequestFeedbackKind.pr_review_comment
            else f"reply_to_pr(pull_number={pull_number})"
        )
        summary_parts = [
            f"{index}. kind={item.kind.value}",
            f"github_id={item.external_id}",
            f"reply_with={reply_tool}",
            f"author={item.author or 'unknown'}",
        ]
        if item.review_state:
            summary_parts.append(f"review_state={item.review_state}")
        if item.file_path:
            summary_parts.append(f"file={item.file_path}")
        if item.line is not None:
            summary_parts.append(f"line={item.line}")
        if item.html_url:
            summary_parts.append(f"url={item.html_url}")
        lines.append("; ".join(summary_parts))
        if item.body:
            lines.append(_format_github_feedback_message(item))
        lines.append("")

    return "\n".join(lines).rstrip()


def _format_github_feedback_message(item: GithubPullRequestFeedbackRecord) -> str:
    reminder_parts = [
        "The following feedback was sent from GitHub",
        f"by `{item.author}`" if item.author else "by an unknown GitHub user",
        f"as `{item.kind.value}`",
    ]
    if item.review_state:
        reminder_parts.append(f"with review state `{item.review_state}`")
    reminder = " ".join(reminder_parts) + "."
    return f"<agent-system-reminder>{reminder}</agent-system-reminder>{item.body}"


async def _mark_failed(database: Database, task_id: uuid.UUID, error: str) -> None:
    async with database.session() as session:
        await TaskRepository.set_failed(session, task_id, error=error)


async def _mark_queued_for_redispatch(database: Database, task_id: uuid.UUID) -> None:
    async with database.session() as session:
        task = await TaskRepository.get(session, task_id)
        if task is None:
            return
        if task.status == TaskStatus.failed:
            return
        await TaskRepository.set_queued(session, task_id)


def _is_worker_shutdown_exception(exc: BaseException) -> bool:
    return isinstance(exc, asyncio.CancelledError | KeyboardInterrupt | SystemExit)
