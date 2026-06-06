from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from src.server.api.dependencies import get_current_user
from src.server.postgres.database import Database
from src.server.postgres.models import (
    ProductProposalRecord,
    ProductProposalStatus,
    ProposalPlanningRunStatus,
    FeatureStatus,
    UserRecord,
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
from src.server.services.proposal_planning import (
    NoActiveMarcAgentInstanceError,
    ProposalNotFoundAfterPlanningStartError,
    start_proposal_planning,
)
from src.server.schemas import (
    ProductProposalCreateRequest,
    ProductProposalResponse,
    ProductProposalStatusUpdateRequest,
    FeatureResponse,
)

router = APIRouter(prefix="/v1/product", tags=["product"])

def _proposal_owned_by_user(
    proposal: ProductProposalRecord,
    user_id: uuid.UUID,
) -> bool:
    """Return whether the product proposal belongs to the current user."""
    return proposal.user_id == user_id


@router.post("/proposals", response_model=ProductProposalResponse, status_code=201)
async def create_proposal(
    request: Request,
    payload: ProductProposalCreateRequest,
    user: UserRecord = Depends(get_current_user),
) -> ProductProposalResponse:
    """Create a product proposal for a user-owned workspace."""
    database: Database = request.app.state.database
    async with database.session() as session:
        workspaces = await WorkspaceRepository.list_for_user(session, user_id=user.id)
        if not any(workspace.github_repo == payload.repo and workspace.project == payload.project for workspace in workspaces):
            raise HTTPException(status_code=403, detail="Repo/project is not available for this user")
        if payload.source_task_id is not None:
            source_task = await TaskRepository.get(session, payload.source_task_id)
            if source_task is None:
                raise HTTPException(status_code=404, detail="Source task not found")
            instance = await AgentInstanceRepository.get(session, source_task.agent_instance_id)
            if instance is None or instance.user_id != user.id:
                raise HTTPException(status_code=404, detail="Source task not found")
        proposal = await ProductProposalRepository.create(
            session,
            title=payload.title,
            plan_type=payload.plan_type,
            summary=payload.summary,
            answer=payload.answer,
            user_id=user.id,
            project=payload.project,
            repo=payload.repo,
            source_task_id=payload.source_task_id,
        )
        latest_planning_run = await ProposalPlanningRunRepository.get_latest_by_proposal(session, proposal.id)
        latest_planning_task_exists = None
        if latest_planning_run is not None:
            latest_planning_task_exists = (await TaskRepository.get(session, latest_planning_run.task_id)) is not None
        return ProductProposalResponse.from_record(
            proposal,
            latest_planning_run=latest_planning_run,
            latest_planning_task_exists=latest_planning_task_exists,
        )


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
        proposals = await ProductProposalRepository.list(
            session,
            user_id=user.id,
            status=status,
            project=project,
            repo=repo,
            limit=limit,
        )
        latest_runs = await ProposalPlanningRunRepository.get_latest_by_proposal_ids(
            session,
            [proposal.id for proposal in proposals],
        )
        existing_task_ids = await TaskRepository.list_existing_ids(
            session,
            [run.task_id for run in latest_runs.values()],
        )
        return [
            ProductProposalResponse.from_record(
                proposal,
                latest_planning_run=latest_runs.get(proposal.id),
                latest_planning_task_exists=(
                    latest_runs.get(proposal.id).task_id in existing_task_ids
                    if latest_runs.get(proposal.id) is not None
                    else None
                ),
            )
            for proposal in proposals
        ]


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
        if proposal is None or not _proposal_owned_by_user(proposal, user.id):
            raise HTTPException(status_code=404, detail="Proposal not found")
        latest_planning_run = await ProposalPlanningRunRepository.get_latest_by_proposal(session, proposal.id)
        latest_planning_task_exists = None
        if latest_planning_run is not None:
            latest_planning_task_exists = (await TaskRepository.get(session, latest_planning_run.task_id)) is not None
        return ProductProposalResponse.from_record(
            proposal,
            latest_planning_run=latest_planning_run,
            latest_planning_task_exists=latest_planning_task_exists,
        )


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
        if existing is None or not _proposal_owned_by_user(existing, user.id):
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
            try:
                proposal = await start_proposal_planning(
                    session,
                    runner=runner,
                    proposal=proposal,
                    user_id=user.id,
                )
            except NoActiveMarcAgentInstanceError as exc:
                raise HTTPException(status_code=409, detail="No active Marc agent instance is available") from exc
            except ProposalNotFoundAfterPlanningStartError as exc:
                raise HTTPException(status_code=404, detail="Proposal not found") from exc
        latest_planning_run = await ProposalPlanningRunRepository.get_latest_by_proposal(session, proposal.id)
        latest_planning_task_exists = None
        if latest_planning_run is not None:
            latest_planning_task_exists = (await TaskRepository.get(session, latest_planning_run.task_id)) is not None
        return ProductProposalResponse.from_record(
            proposal,
            latest_planning_run=latest_planning_run,
            latest_planning_task_exists=latest_planning_task_exists,
        )


@router.post("/proposals/{proposal_id}/retry-planning", response_model=ProductProposalResponse)
async def retry_proposal_planning(
    request: Request,
    proposal_id: uuid.UUID,
    user: UserRecord = Depends(get_current_user),
) -> ProductProposalResponse:
    database: Database = request.app.state.database
    runner: AgentTaskRunner = request.app.state.runner
    async with database.session() as session:
        proposal = await ProductProposalRepository.get(session, proposal_id)
        if proposal is None or not _proposal_owned_by_user(proposal, user.id):
            raise HTTPException(status_code=404, detail="Proposal not found")
        if proposal.status != ProductProposalStatus.approved:
            raise HTTPException(status_code=409, detail="Only approved proposals can retry planning")

        latest_planning_run = await ProposalPlanningRunRepository.get_latest_by_proposal(session, proposal.id)
        retry_of_task_id: uuid.UUID | None = None
        if latest_planning_run is not None:
            latest_planning_task = await TaskRepository.get(session, latest_planning_run.task_id)
            if latest_planning_task is not None:
                if latest_planning_run.status in {
                    ProposalPlanningRunStatus.queued,
                    ProposalPlanningRunStatus.running,
                }:
                    raise HTTPException(status_code=409, detail="Planning is already in progress")
                if latest_planning_run.status == ProposalPlanningRunStatus.completed:
                    raise HTTPException(status_code=409, detail="Planning is already completed")
                if latest_planning_run.status != ProposalPlanningRunStatus.failed:
                    raise HTTPException(
                        status_code=409,
                        detail="Only failed planning runs can be retried",
                    )
                retry_of_task_id = latest_planning_run.task_id

        try:
            proposal = await start_proposal_planning(
                session,
                runner=runner,
                proposal=proposal,
                user_id=user.id,
                retry_of_task_id=retry_of_task_id,
            )
        except NoActiveMarcAgentInstanceError as exc:
            raise HTTPException(status_code=409, detail="No active Marc agent instance is available") from exc
        except ProposalNotFoundAfterPlanningStartError as exc:
            raise HTTPException(status_code=404, detail="Proposal not found") from exc
        latest_planning_run = await ProposalPlanningRunRepository.get_latest_by_proposal(session, proposal.id)
        latest_planning_task_exists = None
        if latest_planning_run is not None:
            latest_planning_task_exists = (await TaskRepository.get(session, latest_planning_run.task_id)) is not None
        return ProductProposalResponse.from_record(
            proposal,
            latest_planning_run=latest_planning_run,
            latest_planning_task_exists=latest_planning_task_exists,
        )


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
        features = await FeatureRepository.list(
            session,
            user_id=user.id,
            status=status,
            project=project,
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
        if proposal is None or not _proposal_owned_by_user(proposal, user.id):
            raise HTTPException(status_code=404, detail="Feature not found")
        items = await FeatureItemRepository.list_by_feature(session, feature_id)
    return FeatureResponse.from_record(feature, items=items)
