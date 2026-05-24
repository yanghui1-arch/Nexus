from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from src.server.postgres.models import AgentName, ProductProposalRecord
from src.server.postgres.repositories import (
    AgentInstanceRepository,
    ProductProposalRepository,
    ProposalPlanningRunRepository,
)
from src.server.runner import AgentTaskRunner
from src.server.schemas import AgentKind, TaskCreateRequest


class ProposalPlanningError(Exception):
    """Base error for proposal-planning service failures."""


class NoActiveMarcAgentInstanceError(ProposalPlanningError):
    """Raised when no Marc agent instance can accept the planning task."""


class ProposalNotFoundAfterPlanningStartError(ProposalPlanningError):
    """Raised when the proposal disappears during planning task startup."""


def _build_planning_question(
    proposal: ProductProposalRecord,
    *,
    retry_of_task_id: uuid.UUID | None = None,
) -> str:
    question = (
        "Plan the approved product proposal below. "
        "Create one or more features, then create one or more feature items for each feature.\n\n"
        f"Proposal ID: {proposal.id}\n"
        f"Title: {proposal.title}\n"
        f"Plan type: {proposal.plan_type}\n"
        f"Project: {proposal.project}\n"
        f"Repo: {proposal.repo}\n"
        f"Summary: {proposal.summary}\n"
        f"Answer: {proposal.answer}"
    )
    if retry_of_task_id is not None:
        question = f"{question}\n\nRetry source failed task ID: {retry_of_task_id}"
    return question


async def start_proposal_planning(
    session: AsyncSession,
    *,
    runner: AgentTaskRunner,
    proposal: ProductProposalRecord,
    user_id: uuid.UUID,
    retry_of_task_id: uuid.UUID | None = None,
) -> ProductProposalRecord:
    """Start the Marc planning task for an approved proposal.

    This service owns the cross-repository orchestration required to turn an
    approved proposal into an observable planning run:
    1. Pick an eligible Marc agent instance for the proposal workspace.
    2. Create the PM planning task row.
    3. Create the linked proposal-planning tracking row in the same transaction.
    4. Commit before dispatch so broker/worker failures still leave traceable state.

    Args:
        session: Open database session that participates in the surrounding workflow.
        runner: Task runner used to create and dispatch the planning task.
        proposal: Approved proposal that should be decomposed into features/items.
        user_id: Current user id used to scope Marc instance selection.
        retry_of_task_id: Failed planning task id that this new task retries, when applicable.

    Returns:
        The refreshed proposal record after the planning task has been enqueued.

    Raises:
        NoActiveMarcAgentInstanceError: No Marc instance can accept this proposal.
        ProposalNotFoundAfterPlanningStartError: Proposal vanished before refresh.
    """
    marc_instances = await AgentInstanceRepository.list_by_active_task_load(
        session,
        agent=AgentName.marc,
        user_id=user_id,
        github_repo=proposal.repo,
        project=proposal.project,
        limit=1,
    )
    if not marc_instances:
        raise NoActiveMarcAgentInstanceError

    planning_request = TaskCreateRequest(
        agent_instance_id=marc_instances[0].id,
        agent=AgentKind.marc,
        question=_build_planning_question(proposal, retry_of_task_id=retry_of_task_id),
        external_issue_url=None,
    )
    # Persist both the planning task row and its tracking row before dispatch.
    # This keeps the approved proposal observable even if broker dispatch or
    # worker execution fails immediately afterwards.
    planning_task = await runner.create_task_record(planning_request, session=session)
    await ProposalPlanningRunRepository.create_pending(
        session,
        proposal_id=proposal.id,
        task_id=planning_task.id,
    )
    await session.commit()
    await runner.dispatch_existing_task(
        planning_task.id,
        recovered=False,
        fail_task_on_dispatch_error=True,
    )
    refreshed_proposal = await ProductProposalRepository.get(session, proposal.id)
    if refreshed_proposal is None:
        raise ProposalNotFoundAfterPlanningStartError
    return refreshed_proposal
