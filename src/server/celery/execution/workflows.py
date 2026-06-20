from __future__ import annotations

import uuid

from openai.types.chat.chat_completion_message_param import ChatCompletionMessageParam

from src.agents.base.agent import Agent, BaseAgentResponse
from src.logger import logger
from src.server.config import Settings
from src.server.postgres.database import Database
from src.server.postgres.models import (
    TaskCategory,
    TaskRecord,
    TaskWorkItemRecord,
    TaskWorkItemStatus,
)
from src.server.postgres.repositories import TaskWorkItemRepository
from src.tools.nexus import NexusAssistantEventContext, NexusTaskContext

from . import agents, checkpoints, prompt_helper, state


_WORK_ITEM_REVIEW_READY_STATUSES = {
    TaskWorkItemStatus.ready_for_review,
    TaskWorkItemStatus.approved,
    TaskWorkItemStatus.closed,
}


async def run_agent(
    *,
    agent: Agent,
    question: str,
    checkpoint: list[ChatCompletionMessageParam] | None = None,
    on_progress,
) -> BaseAgentResponse:
    """Run an agent with an optional replay checkpoint.

    Args:
        agent: Agent instance to execute.
        question: Prompt for the current agent turn.
        checkpoint: Persisted message context to resume from, or ``None`` to
            start a fresh turn.
        on_progress: Callback passed through to ``Agent.work`` for progress and
            checkpoint events.

    Returns:
        Agent response for the completed turn.
    """
    work_kwargs = {
        "question": question,
        "update_process_callback": on_progress,
        "from_checkpoint": bool(checkpoint),
    }
    if checkpoint:
        work_kwargs["checkpoint"] = checkpoint
    return await agent.work(**work_kwargs)


async def run_agent_workflow(
    *,
    database: Database,
    task: TaskRecord,
    on_progress,
    settings: Settings,
    user_id: uuid.UUID,
    workspace_key: str,
    github_repo: str | None,
):
    """Dispatch a task to its category-specific workflow.

    Args:
        database: Connected database wrapper.
        task: Running task record to execute.
        on_progress: Progress callback to pass to the agent.
        settings: Runtime settings for agent creation and feedback batching.
        user_id: User that owns the task.
        workspace_key: Sandbox workspace key bound to the agent instance.
        github_repo: Repository resolved from the workspace binding.

    Raises:
        RuntimeError: If the task category is not supported.
    """
    if task.category == TaskCategory.coding:
        await run_code_agent_workflow(
            database=database,
            task=task,
            on_progress=on_progress,
            settings=settings,
            user_id=user_id,
            workspace_key=workspace_key,
            github_repo=github_repo,
        )
        return
    if task.category == TaskCategory.pm:
        await run_pm_agent_workflow(
            database=database,
            task=task,
            on_progress=on_progress,
            settings=settings,
            user_id=user_id,
            workspace_key=workspace_key,
            github_repo=github_repo,
        )
        return
    if task.category == TaskCategory.review:
        await run_review_agent_workflow(
            database=database,
            task=task,
            on_progress=on_progress,
            settings=settings,
            user_id=user_id,
            workspace_key=workspace_key,
            github_repo=github_repo,
        )
        return
    raise RuntimeError(f"Unsupported task category: {task.category}")


async def run_code_agent_workflow(
    *,
    database: Database,
    task: TaskRecord,
    on_progress,
    settings: Settings,
    user_id: uuid.UUID,
    workspace_key: str,
    github_repo: str | None,
):
    """Run a coding task through feedback, small-task, and work-item paths.

    Args:
        database: Connected database wrapper.
        task: Running coding task.
        on_progress: Progress callback to pass to the agent.
        settings: Runtime settings for agent creation and GitHub feedback
            batching.
        user_id: User that owns the task.
        workspace_key: Sandbox workspace key bound to the agent instance.
        github_repo: Repository resolved from the workspace binding.

    Raises:
        RuntimeError: If repo/project context is missing, a claimed work item
            disappears, or the agent finishes without marking the work item
            ready for review.
    """
    repo = task.repo or github_repo
    project = task.project
    if not repo or not project:
        raise RuntimeError("Missing repo/project context.")

    nexus_context = NexusTaskContext(
        task_id=task.id,
        database=database,
        user_id=user_id,
        repo=repo,
        project=project,
        agent_name=task.agent.value,
    )
    agent = agents.build_agent(
        task=task,
        settings=settings,
        workspace_key=workspace_key,
        github_repo=github_repo,
    )
    agent.set_nexus_task_context(nexus_context)

    async with agent:
        checkpoint = await state.get_latest_checkpoint(database, task.id)
        claimed_feedback = await state.claim_pending_github_feedback(
            database,
            task.id,
            limit=settings.github_feedback_batch_size,
        )
        if claimed_feedback:
            feedback_prompt = prompt_helper.build_github_feedback_prompt(task, claimed_feedback)
            if checkpoints.checkpoint_completed_prompt(checkpoint, feedback_prompt):
                logger.info(
                    "Task %s GitHub feedback was already completed in checkpoint; marking feedback processed.",
                    task.id,
                )
                await state.mark_github_feedback_processed(database, claimed_feedback)
                return

            logger.info(
                "Task %s is resuming from checkpoint to process %s GitHub feedback item(s).",
                task.id,
                len(claimed_feedback),
            )
            nexus_context.current_work_item_id = None
            try:
                await run_agent(
                    agent=agent,
                    question=feedback_prompt,
                    checkpoint=checkpoint,
                    on_progress=on_progress,
                )
            except Exception:
                await state.requeue_github_feedback(database, claimed_feedback)
                raise
            await state.mark_github_feedback_processed(database, claimed_feedback)
            return

        while True:
            async with database.session() as session:
                work_items = await TaskWorkItemRepository.list_by_task(session, task.id)
            # Always pass the latest checkpoint so Celery redelivery can continue
            # from the last safe replay boundary.
            checkpoint = await state.get_latest_checkpoint(database, task.id)

            if not work_items:
                if checkpoints.checkpoint_has_completed_turn(checkpoint):
                    logger.info(
                        "Task %s has a completed checkpoint and no Nexus work items; skipping agent rerun.",
                        task.id,
                    )
                    break

                logger.info("Task %s has no Nexus work items; starting normal task run.", task.id)
                nexus_context.current_work_item_id = None
                await run_agent(
                    agent=agent,
                    question=task.question,
                    checkpoint=checkpoint,
                    on_progress=on_progress,
                )

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

            if all_work_items_review_ready(work_items):
                logger.info("Task %s has no executable work items; waiting for review.", task.id)
                break

            work_item = await state.claim_next_work_item(database, task.id)
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
            await run_agent(
                agent=agent,
                question=prompt_helper.build_work_item_prompt(
                    work_item,
                    is_final_work_item=is_final_executable_work_item(work_items, work_item.id),
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


async def run_pm_agent_workflow(
    *,
    database: Database,
    task: TaskRecord,
    on_progress,
    settings: Settings,
    user_id: uuid.UUID,
    workspace_key: str,
    github_repo: str | None,
):
    """Run a PM planning task and move it to review when complete.

    Args:
        database: Connected database wrapper.
        task: Running PM task.
        on_progress: Progress callback to pass to the agent.
        settings: Runtime settings for agent creation.
        user_id: User that owns the task.
        workspace_key: Sandbox workspace key bound to the agent instance.
        github_repo: Repository resolved from the workspace binding.

    Raises:
        RuntimeError: If repo/project context is missing.
    """
    repo = task.repo or github_repo
    project = task.project
    if not repo or not project:
        raise RuntimeError("Missing repo/project context.")

    nexus_context = NexusTaskContext(
        task_id=task.id,
        database=database,
        user_id=user_id,
        repo=repo,
        project=project,
        agent_name=task.agent.value,
    )
    agent = agents.build_agent(
        task=task,
        settings=settings,
        workspace_key=workspace_key,
        github_repo=github_repo,
    )
    # not every one has `set_nexus_task_context` function
    if hasattr(agent, "set_nexus_task_context"):
        agent.set_nexus_task_context(nexus_context)
    async with agent:
        checkpoint = await state.get_latest_checkpoint(database, task.id)
        if checkpoints.checkpoint_has_completed_turn(checkpoint):
            await state.mark_waiting_for_review(
                database,
                task.id,
                checkpoints.checkpoint_completion_text(checkpoint),
            )
            return

        response = await run_agent(
            agent=agent,
            question=task.question,
            checkpoint=checkpoint,
            on_progress=on_progress,
        )
    await state.mark_waiting_for_review(database, task.id, response.response)


async def run_review_agent_workflow(
    *,
    database: Database,
    task: TaskRecord,
    on_progress,
    settings: Settings,
    user_id: uuid.UUID,
    workspace_key: str,
    github_repo: str | None,
):
    """Run an Assistant PR review turn and keep the PR thread watchable."""
    repo = task.repo or github_repo
    project = task.project
    if not repo or not project:
        raise RuntimeError("Missing repo/project context.")

    nexus_context = NexusTaskContext(
        task_id=task.id,
        database=database,
        user_id=user_id,
        repo=repo,
        project=project,
        agent_name=task.agent.value,
    )
    agent = agents.build_agent(
        task=task,
        settings=settings,
        workspace_key=workspace_key,
        github_repo=github_repo,
    )
    if hasattr(agent, "set_nexus_task_context"):
        agent.set_nexus_task_context(nexus_context)
    if hasattr(agent, "set_nexus_assistant_event_context"):
        agent.set_nexus_assistant_event_context(
            NexusAssistantEventContext(
                agent_instance_id=task.agent_instance_id,
                database=database,
                repo=repo,
                project=project,
                current_task_id=task.id,
            )
        )

    async with agent:
        checkpoint = await state.get_latest_checkpoint(database, task.id)
        claimed_feedback = await state.claim_pending_github_feedback(
            database,
            task.id,
            limit=settings.github_feedback_batch_size,
        )
        if claimed_feedback:
            feedback_prompt = prompt_helper.build_assistant_github_feedback_prompt(task, claimed_feedback)
            if checkpoints.checkpoint_completed_prompt(checkpoint, feedback_prompt):
                logger.info(
                    "Assistant task %s GitHub feedback was already completed in checkpoint; marking feedback processed.",
                    task.id,
                )
                await state.mark_github_feedback_processed(database, claimed_feedback)
                await state.mark_review_completed(
                    database,
                    task.id,
                    checkpoints.checkpoint_completion_text(checkpoint),
                )
                return

            logger.info(
                "Assistant task %s is resuming from checkpoint to process %s GitHub feedback item(s).",
                task.id,
                len(claimed_feedback),
            )
            try:
                response = await run_agent(
                    agent=agent,
                    question=feedback_prompt,
                    checkpoint=checkpoint,
                    on_progress=on_progress,
                )
            except Exception:
                await state.requeue_github_feedback(database, claimed_feedback)
                raise
            await state.mark_github_feedback_processed(database, claimed_feedback)
            await state.mark_review_completed(database, task.id, response.response)
            return

        if checkpoints.checkpoint_completed_prompt(checkpoint, task.question):
            await state.mark_review_completed(
                database,
                task.id,
                checkpoints.checkpoint_completion_text(checkpoint),
            )
            return

        response = await run_agent(
            agent=agent,
            question=task.question,
            checkpoint=checkpoint,
            on_progress=on_progress,
        )
    await state.mark_review_completed(database, task.id, response.response)


def all_work_items_review_ready(work_items: list[TaskWorkItemRecord]) -> bool:
    """Return whether all work items are past execution.

    Args:
        work_items: Work items currently attached to the task.

    Returns:
        ``True`` when there is at least one item and every item is ready for
        review, approved, or closed.
    """
    return bool(work_items) and all(
        work_item.status in _WORK_ITEM_REVIEW_READY_STATUSES
        for work_item in work_items
    )


def is_final_executable_work_item(work_items: list[TaskWorkItemRecord], work_item_id: uuid.UUID) -> bool:
    """Return whether a work item is the final item that still needs execution.

    Args:
        work_items: Work items currently attached to the task.
        work_item_id: Candidate work item ID.

    Returns:
        ``True`` when every other work item is already review-ready, approved,
        or closed.
    """
    return all(
        work_item.id == work_item_id or work_item.status in _WORK_ITEM_REVIEW_READY_STATUSES
        for work_item in work_items
    )
