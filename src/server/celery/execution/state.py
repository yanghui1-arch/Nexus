from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from openai.types.chat.chat_completion_message_param import ChatCompletionMessageParam

from src.server.postgres.database import Database
from src.server.postgres.models import (
    GithubPullRequestFeedbackRecord,
    TaskCategory,
    TaskRecord,
    TaskStatus,
    TaskWorkItemRecord,
)
from src.server.postgres.models import FeatureItemStatus
from src.server.postgres.repositories import (
    AgentInstanceRepository,
    FeatureItemRepository,
    GithubPullRequestFeedbackRepository,
    ProductProposalRepository,
    ProposalPlanningRunRepository,
    TaskRepository,
    TaskWorkItemRepository,
    WorkspaceRepository,
)


@dataclass(frozen=True)
class ExecutionBinding:
    """Resolved workspace and ownership context for task execution.

    Attributes:
        user_id: User that owns the agent instance.
        github_repo: Repository snapshot or workspace repository.
        project: Project snapshot or workspace project.
        workspace_key: Sandbox workspace key for the agent instance.
    """

    user_id: uuid.UUID
    github_repo: str | None
    project: str | None
    workspace_key: str


@dataclass(frozen=True)
class TaskClaimFailureSnapshot:
    """Database state useful for explaining why a task claim failed."""

    task_status: str | None
    task_agent_instance_id: uuid.UUID | None
    conflicting_running_task_id: uuid.UUID | None
    conflicting_running_task_started_at: datetime | None
    conflicting_running_task_updated_at: datetime | None
    workspace_status: str | None
    workspace_updated_at: datetime | None


async def load_task(database: Database, task_id: uuid.UUID) -> TaskRecord:
    """Load a task record for execution.

    Args:
        database: Connected database wrapper.
        task_id: Task ID to load.

    Returns:
        Task record for ``task_id``.

    Raises:
        RuntimeError: If the task does not exist.
    """
    async with database.session() as session:
        task = await TaskRepository.get(session, task_id)
    if task is None:
        raise RuntimeError(f"task_id={task_id} does not exist")
    return task


async def load_binding(database: Database, task: TaskRecord) -> ExecutionBinding:
    """Resolve the workspace and repo/project context for a task.

    Args:
        database: Connected database wrapper.
        task: Task whose agent instance should be bound to a workspace.

    Returns:
        Resolved execution binding.

    Raises:
        RuntimeError: If the agent instance is missing, inactive, belongs to a
            different agent, or lacks repo/project context.
    """
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

        workspace = await WorkspaceRepository.ensure_for_agent_instance(
            session,
            instance,
        )

        # Newer tasks snapshot repo/project at submission time so later workspace edits
        # do not retarget in-flight or recoverable work. Keep workspace as a fallback
        # for legacy rows that predate that snapshot behavior.
        github_repo = task.repo or workspace.github_repo
        project = task.project if task.project is not None else workspace.project
        if not github_repo or not project:
            raise RuntimeError("Missing repo/project context.")

    return ExecutionBinding(
        user_id=instance.user_id,
        github_repo=github_repo,
        project=project,
        workspace_key=workspace.workspace_key,
    )


async def mark_task_running(
    database: Database,
    task_id: uuid.UUID,
    *,
    expected_agent_instance_id: uuid.UUID,
    allow_running: bool,
) -> TaskRecord | None:
    """Mark a task as running for this agent instance.

    Args:
        database: Connected database wrapper.
        task_id: Task ID to transition.
        expected_agent_instance_id: Agent instance that must still own the task.
        allow_running: Whether an already-running task may be accepted.

    Returns:
        Updated task record, or ``None`` when the task could not be claimed.
    """
    async with database.session() as session:
        task = await TaskRepository.set_running(
            session,
            task_id,
            expected_agent_instance_id=expected_agent_instance_id,
            allow_running=allow_running,
        )
        if task is None:
            return None
        if task.category == TaskCategory.pm:
            # Only planning PM tasks can have a linked proposal-planning run.
            # Keep the condition here so readers do not have to inspect repository
            # internals to understand why most tasks do not touch this state.
            planning_run = await ProposalPlanningRunRepository.get_by_task_id(session, task_id)
            if planning_run is not None:
                await ProposalPlanningRunRepository.set_running(session, planning_run.id)
        return task


async def load_task_claim_failure_snapshot(
    database: Database,
    task_id: uuid.UUID,
    *,
    expected_agent_instance_id: uuid.UUID,
) -> TaskClaimFailureSnapshot:
    """Return current DB state for a failed task claim."""
    # Keep this helper on the failed-claim path only; it trades a few extra
    # reads for actionable logs and should not add overhead to normal execution.
    async with database.session() as session:
        task = await TaskRepository.get(session, task_id)
        conflicting_running_task = await TaskRepository.get_running_for_agent_instance(
            session,
            expected_agent_instance_id,
            exclude_task_id=task_id,
        )
        workspace = await WorkspaceRepository.get_by_agent_instance_id(
            session,
            expected_agent_instance_id,
        )

    return TaskClaimFailureSnapshot(
        task_status=task.status.value if task is not None else None,
        task_agent_instance_id=task.agent_instance_id if task is not None else None,
        conflicting_running_task_id=conflicting_running_task.id if conflicting_running_task is not None else None,
        conflicting_running_task_started_at=(
            conflicting_running_task.started_at if conflicting_running_task is not None else None
        ),
        conflicting_running_task_updated_at=(
            conflicting_running_task.updated_at if conflicting_running_task is not None else None
        ),
        workspace_status=workspace.status.value if workspace is not None else None,
        workspace_updated_at=workspace.updated_at if workspace is not None else None,
    )


async def mark_workspace_running(
    database: Database,
    agent_instance_id: uuid.UUID,
) -> None:
    """Mark an agent instance workspace as running.

    Args:
        database: Connected database wrapper.
        agent_instance_id: Agent instance whose workspace should be marked
            running.
    """
    async with database.session() as session:
        await WorkspaceRepository.set_running(
            session,
            agent_instance_id=agent_instance_id,
        )


async def get_latest_checkpoint(database: Database, task_id: uuid.UUID) -> list[ChatCompletionMessageParam]:
    """Return the latest persisted checkpoint for a task.

    Args:
        database: Connected database wrapper.
        task_id: Task ID whose checkpoint should be loaded.

    Returns:
        Persisted checkpoint messages, or an empty list when no checkpoint has
        been saved.

    Raises:
        RuntimeError: If the task does not exist.
    """
    task = await load_task(database, task_id)
    return task.checkpoint if task.checkpoint is not None else []


async def release_workspace(database: Database, agent_instance_id: uuid.UUID) -> None:
    """Release a workspace after task execution ends.

    Args:
        database: Connected database wrapper.
        agent_instance_id: Agent instance whose workspace should leave the
            running state.
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


async def mark_waiting_for_review(database: Database, task_id: uuid.UUID, result: str | None) -> None:
    """Mark a task as waiting for review and finalize PM planning state.

    Args:
        database: Connected database wrapper.
        task_id: Task ID to transition.
        result: Final agent response to store on the task.
    """
    async with database.session() as session:
        await TaskRepository.set_waiting_for_review(session, task_id, result=result)
        planning_run = await ProposalPlanningRunRepository.get_by_task_id(session, task_id)
        if planning_run is None:
            return

        # PM tasks historically finished at `waiting_for_review`. Proposal planning
        # needs one extra gate: do not leave the proposal looking "planned" unless
        # the run produced features and feature items that downstream workflow can use.
        validation_error = await ProposalPlanningRunRepository.validate_plan(session, planning_run.proposal_id)
        if validation_error is not None:
            await TaskRepository.set_failed(session, task_id, error=validation_error)
            await ProposalPlanningRunRepository.set_failed(session, planning_run.id, error=validation_error)
            return

        await ProposalPlanningRunRepository.set_completed(session, planning_run.id)
        await ProductProposalRepository.sync_status_from_features(session, planning_run.proposal_id)
        await session.commit()


async def mark_post_execution_wait_state(
    database: Database,
    task_id: uuid.UUID,
    result: str | None,
) -> None:
    """Restore a task's wait state after a worker run.

    Args:
        database: Connected database wrapper.
        task_id: Task ID to update.
        result: Optional result text to persist with the wait state.
    """
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


async def claim_next_work_item(database: Database, task_id: uuid.UUID) -> TaskWorkItemRecord | None:
    """Claim the current or next executable work item.

    Args:
        database: Connected database wrapper.
        task_id: Task whose work item should be claimed.

    Returns:
        Running work item, newly claimed work item, or ``None`` when no work is
        executable.

    Raises:
        RuntimeError: If the repository selects a next item but cannot mark it
            running.
    """
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


async def claim_pending_github_feedback(
    database: Database,
    task_id: uuid.UUID,
    *,
    limit: int,
) -> list[GithubPullRequestFeedbackRecord]:
    """Claim pending GitHub feedback for agent processing.

    Args:
        database: Connected database wrapper.
        task_id: Task whose feedback should be claimed.
        limit: Maximum number of feedback records to claim.

    Returns:
        Claimed feedback records.
    """
    async with database.session() as session:
        return await GithubPullRequestFeedbackRepository.claim_pending_by_task(
            session,
            task_id,
            limit=limit,
        )


async def mark_github_feedback_processed(
    database: Database,
    feedback_items: list[GithubPullRequestFeedbackRecord],
) -> None:
    """Mark claimed GitHub feedback as processed.

    Args:
        database: Connected database wrapper.
        feedback_items: Claimed feedback records that were handled by the
            agent.
    """
    async with database.session() as session:
        await GithubPullRequestFeedbackRepository.mark_processed(
            session,
            [item.id for item in feedback_items],
        )


async def requeue_github_feedback(
    database: Database,
    feedback_items: list[GithubPullRequestFeedbackRecord],
) -> None:
    """Return claimed GitHub feedback to the pending queue.

    Args:
        database: Connected database wrapper.
        feedback_items: Claimed feedback records that should be retried later.
    """
    async with database.session() as session:
        await GithubPullRequestFeedbackRepository.requeue_processing(
            session,
            [item.id for item in feedback_items],
        )


async def mark_failed(database: Database, task_id: uuid.UUID, error: str) -> None:
    """Mark task execution as failed and sync PM planning failure state.

    Args:
        database: Connected database wrapper.
        task_id: Task ID to fail.
        error: Failure message to store.
    """
    async with database.session() as session:
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
