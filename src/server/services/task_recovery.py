"""Task recovery assessment service."""

from __future__ import annotations

from typing import Protocol

from src.server.postgres.models import TaskStatus
from src.server.schemas import TaskExecutionEventResponse, TaskRecoveryAssessmentResponse


class TaskWorkspace(Protocol):
    github_repo: str | None
    project: str | None


def assess_task_recovery(
    *,
    task,
    events,
    agent_instance,
    workspace: TaskWorkspace | None,
    running_conflict,
) -> TaskRecoveryAssessmentResponse:
    """Build recovery readiness metadata without exposing checkpoint contents."""
    checkpoint_count = len(task.checkpoint) if isinstance(task.checkpoint, list) else 0
    checkpoint_exists = checkpoint_count > 0
    repo = task.repo or (workspace.github_repo if workspace is not None else None)
    project = task.project if task.project is not None else (workspace.project if workspace is not None else None)
    agent_available = agent_instance is not None and bool(agent_instance.is_active)
    repo_available = bool(repo)
    project_available = bool(project)
    terminal_without_failure = {TaskStatus.waiting_for_review, TaskStatus.merged, TaskStatus.closed}

    reasons: list[str] = []
    risks: list[str] = []
    actions: list[str] = []
    if task.status in terminal_without_failure:
        reasons.append(f"Task status {task.status.value} does not require recovery")
    if not checkpoint_exists:
        reasons.append("No checkpoint is available for replay")
    if not agent_available:
        reasons.append("Agent instance is inactive or unavailable")
    if not repo_available:
        reasons.append("Repository context is unavailable")
    if running_conflict is not None:
        reasons.append("Agent instance already has another running task")
    if task.error:
        risks.append("Previous failure may recur: " + task.error[:240])
    if events:
        latest = max(events, key=lambda event: event.created_at)
        if latest.message:
            risks.append("Latest event: " + latest.message[:240])
    if not project_available:
        risks.append("Project context is unavailable")

    recoverable = not reasons
    actions.append(
        "Resume the task from the latest checkpoint"
        if recoverable
        else "Start a new task after resolving unrecoverable reasons"
    )
    if running_conflict is not None:
        actions.append("Wait for the conflicting running task to finish")
    if not agent_available:
        actions.append("Reactivate or replace the agent instance")
    if not repo_available:
        actions.append("Set a repository on the task or workspace")

    return TaskRecoveryAssessmentResponse(
        task_id=task.id,
        recoverable=recoverable,
        unrecoverable_reasons=reasons,
        recommended_actions=actions,
        risk_summary=risks,
        checkpoint_exists=checkpoint_exists,
        checkpoint_updated_at=task.updated_at if checkpoint_exists else None,
        checkpoint_message_count=checkpoint_count,
        recent_events=[TaskExecutionEventResponse.from_record(event) for event in events],
        agent_instance_available=agent_available,
        repo_available=repo_available,
        project_available=project_available,
        running_task_conflict=running_conflict is not None,
        conflicting_task_id=running_conflict.id if running_conflict is not None else None,
    )
