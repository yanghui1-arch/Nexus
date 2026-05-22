from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from src.server.config import get_settings
from src.server.api.dependencies import get_current_user
from src.server.postgres.database import Database
from src.server.postgres.models import (
    AgentName,
    ProductProposalRecord,
    ProductProposalStatus,
    FeatureStatus,
    UserRecord,
    WorkspaceRecord,
)
from src.server.postgres.repositories import (
    AgentInstanceRepository,
    FeatureItemRepository,
    FeatureRepository,
    ProductProposalRepository,
    ProposalPlanningRunRepository,
    TaskRepository,
    WorkspaceRepository,
)
from src.server.runner import AgentTaskRunner
from src.server.schemas import (
    AgentKind,
    TaskCreateRequest,
    ProductProposalCreateRequest,
    ProductProposalResponse,
    ProductProposalSummaryResponse,
    ProductProposalStatusUpdateRequest,
    FeatureResponse,
)

router = APIRouter(prefix="/v1/product", tags=["product"])


def _proposal_accessible_to_user_workspaces(
    proposal: ProductProposalRecord,
    workspaces: list[WorkspaceRecord],
) -> bool:
    """Check whether a proposal belongs to one of the user's workspaces.

    Product proposals do not store user ownership directly. A user can access a
    proposal only when the proposal's repo/project pair matches a workspace owned
    by one of the user's agent instances.

    Args:
        proposal: Product proposal being accessed.
        workspaces: Workspaces owned by the current user's agent instances.

    Returns:
        True when the proposal repo/project is visible to the user; otherwise False.
    """
    return any(
        workspace.github_repo == proposal.repo and workspace.project == proposal.project
        for workspace in workspaces
    )


def _build_planning_question(proposal: ProductProposalRecord) -> str:
    """Build the Marc planning prompt for an approved proposal."""
    return (
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


async def _proposal_response(
    session,
    proposal: ProductProposalRecord,
) -> ProductProposalResponse:
    """Build a proposal response with its latest planning run."""
    latest_planning_run = await ProposalPlanningRunRepository.get_latest_by_proposal(session, proposal.id)
    return ProductProposalResponse.from_record(proposal, latest_planning_run=latest_planning_run)


@router.post("/proposals", response_model=ProductProposalResponse, status_code=201)
async def create_proposal(
    request: Request,
    payload: ProductProposalCreateRequest,
    user: UserRecord = Depends(get_current_user),
) -> ProductProposalResponse:
    """Create a product proposal for an accessible workspace."""
    database: Database = request.app.state.database
    async with database.session() as session:
        # Product proposals do not store a user_id directly. Access is derived from
        # the current user's agent workspaces, so users may only create proposals
        # for repo/project pairs that one of their agent instances owns.
        workspaces = await WorkspaceRepository.list_for_user(session, user_id=user.id)
        if not any(workspace.github_repo == payload.repo and workspace.project == payload.project for workspace in workspaces):
            raise HTTPException(status_code=403, detail="Repo/project is not available for this user")
        proposal = await ProductProposalRepository.create(
            session,
            title=payload.title,
            plan_type=payload.plan_type,
            summary=payload.summary,
            answer=payload.answer,
            project=payload.project,
            repo=payload.repo,
            source_task_id=payload.source_task_id,
        )
        return await _proposal_response(session, proposal)


@router.get("/proposals", response_model=list[ProductProposalResponse])
async def list_proposals(
    request: Request,
    status: ProductProposalStatus | None = Query(default=None),
    project: str | None = Query(default=None),
    repo: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    user: UserRecord = Depends(get_current_user),
) -> list[ProductProposalResponse]:
    """List product proposals visible to the current user."""
    database: Database = request.app.state.database
    async with database.session() as session:
        workspaces = await WorkspaceRepository.list_for_user(session, user_id=user.id)
        proposals = await ProductProposalRepository.list(
            session,
            status=status,
            project=project,
            repo=repo,
            workspaces=workspaces,
            limit=limit,
        )
        latest_runs = await ProposalPlanningRunRepository.get_latest_by_proposal_ids(
            session,
            [proposal.id for proposal in proposals],
        )
        return [
            ProductProposalResponse.from_record(
                proposal,
                latest_planning_run=latest_runs.get(proposal.id),
            )
            for proposal in proposals
        ]


@router.get("/proposals/recent-summaries", response_model=list[ProductProposalSummaryResponse])
async def list_recent_proposal_summaries(
    request: Request,
    project: str | None = Query(default=None),
    repo: str | None = Query(default=None),
    user: UserRecord = Depends(get_current_user),
) -> list[ProductProposalSummaryResponse]:
    """List recent lightweight proposal summaries visible to the current user."""
    database: Database = request.app.state.database
    limit = get_settings().recent_proposal_summary_limit
    async with database.session() as session:
        workspaces = await WorkspaceRepository.list_for_user(session, user_id=user.id)
        proposals = await ProductProposalRepository.list_recent_summaries(
            session,
            project=project,
            repo=repo,
            workspaces=workspaces,
            limit=limit,
        )
    return [ProductProposalSummaryResponse.from_record(proposal) for proposal in proposals]


@router.get("/proposals/{proposal_id}", response_model=ProductProposalResponse)
async def get_proposal(
    request: Request,
    proposal_id: uuid.UUID,
    user: UserRecord = Depends(get_current_user),
) -> ProductProposalResponse:
    """Return one product proposal visible to the current user."""
    database: Database = request.app.state.database
    async with database.session() as session:
        proposal = await ProductProposalRepository.get(session, proposal_id)
        workspaces = await WorkspaceRepository.list_for_user(session, user_id=user.id)
        if proposal is None or not _proposal_accessible_to_user_workspaces(proposal, workspaces):
            raise HTTPException(status_code=404, detail="Proposal not found")
        return await _proposal_response(session, proposal)


@router.patch("/proposals/{proposal_id}/status", response_model=ProductProposalResponse)
async def update_proposal_status(
    request: Request,
    proposal_id: uuid.UUID,
    payload: ProductProposalStatusUpdateRequest,
    user: UserRecord = Depends(get_current_user),
) -> ProductProposalResponse:
    """Update product proposal status and schedule planning when approved."""
    database: Database = request.app.state.database
    runner: AgentTaskRunner = request.app.state.runner
    async with database.session() as session:
        existing = await ProductProposalRepository.get(session, proposal_id)
        workspaces = await WorkspaceRepository.list_for_user(session, user_id=user.id)
        if existing is None or not _proposal_accessible_to_user_workspaces(existing, workspaces):
            raise HTTPException(status_code=404, detail="Proposal not found")
        previous_status = existing.status
        proposal = await ProductProposalRepository.set_status(session, proposal_id, payload.status)
        if proposal is not None and proposal.source_task_id is not None:
            # Once a PM-reviewed proposal reaches a terminal outcome, move its source task
            # out of active states so the hourly discovery poller can schedule new proposals.
            if payload.status == ProductProposalStatus.approved:
                await TaskRepository.set_merged(session, proposal.source_task_id)
            elif payload.status == ProductProposalStatus.rejected:
                await TaskRepository.set_closed(session, proposal.source_task_id)
        if proposal is None:
            raise HTTPException(status_code=404, detail="Proposal not found")

        if payload.status == ProductProposalStatus.approved and previous_status != ProductProposalStatus.approved:
            # A newly approved proposal needs a separate Marc planning task; coding task publishing is handled by ProductWorkflowPoller.
            marc_instances = await AgentInstanceRepository.list_by_active_task_load(
                session,
                agent=AgentName.marc,
                user_id=user.id,
                github_repo=proposal.repo,
                project=proposal.project,
                limit=1,
            )
            if not marc_instances:
                raise HTTPException(status_code=409, detail="No active Marc agent instance is available")

            planning_request = TaskCreateRequest(
                agent_instance_id=marc_instances[0].id,
                agent=AgentKind.marc,
                question=_build_planning_question(proposal),
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
            await runner.dispatch_existing_task(planning_task.id, recovered=False, mark_failed=True)
            proposal = await ProductProposalRepository.get(session, proposal_id)
            if proposal is None:
                raise HTTPException(status_code=404, detail="Proposal not found")

        return await _proposal_response(session, proposal)


@router.get("/features", response_model=list[FeatureResponse])
async def list_features(
    request: Request,
    status: FeatureStatus | None = Query(default=None),
    project: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    user: UserRecord = Depends(get_current_user),
) -> list[FeatureResponse]:
    """List features visible to the current user."""
    database: Database = request.app.state.database
    async with database.session() as session:
        workspaces = await WorkspaceRepository.list_for_user(session, user_id=user.id)
        features = await FeatureRepository.list(
            session,
            status=status,
            project=project,
            workspaces=workspaces,
            limit=limit,
        )
    return [FeatureResponse.from_record(feature) for feature in features]


@router.get("/features/{feature_id}", response_model=FeatureResponse)
async def get_feature(
    request: Request,
    feature_id: uuid.UUID,
    user: UserRecord = Depends(get_current_user),
) -> FeatureResponse:
    """Return one feature visible to the current user."""
    database: Database = request.app.state.database
    async with database.session() as session:
        feature = await FeatureRepository.get(session, feature_id)
        if feature is None:
            raise HTTPException(status_code=404, detail="Feature not found")
        if feature.proposal_id is None:
            raise HTTPException(status_code=404, detail="Feature not found")
        proposal = await ProductProposalRepository.get(session, feature.proposal_id)
        workspaces = await WorkspaceRepository.list_for_user(session, user_id=user.id)
        if proposal is None or not _proposal_accessible_to_user_workspaces(proposal, workspaces):
            raise HTTPException(status_code=404, detail="Feature not found")
        items = await FeatureItemRepository.list_by_feature(session, feature_id)
    return FeatureResponse.from_record(feature, items=items)
