from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from src.server.api.dependencies import get_current_user
from src.server.postgres.database import Database
from src.server.postgres.models import (
    AgentName,
    ProductProposalStatus,
    FeatureStatus,
    UserRecord,
)
from src.server.postgres.repositories import (
    AgentInstanceRepository,
    ProductProposalRepository,
    FeatureItemRepository,
    FeatureRepository,
    TaskRepository,
)
from src.server.runner import AgentTaskRunner
from src.server.schemas import (
    AgentKind,
    TaskCreateRequest,
    ProductProposalCreateRequest,
    ProductProposalResponse,
    ProductProposalStatusUpdateRequest,
    FeatureResponse,
)

router = APIRouter(prefix="/v1/product", tags=["product"])


@router.post("/proposals", response_model=ProductProposalResponse, status_code=201)
async def create_proposal(
    request: Request,
    payload: ProductProposalCreateRequest,
    user: UserRecord = Depends(get_current_user),
) -> ProductProposalResponse:
    database: Database = request.app.state.database
    async with database.session() as session:
        proposal = await ProductProposalRepository.create(
            session,
            title=payload.title,
            plan_type=payload.plan_type,
            summary=payload.summary,
            answer=payload.answer,
            project=payload.project,
            repo=payload.repo,
            user_id=user.id,
            source_task_id=payload.source_task_id,
        )
    return ProductProposalResponse.from_record(proposal)


@router.get("/proposals", response_model=list[ProductProposalResponse])
async def list_proposals(
    request: Request,
    status: ProductProposalStatus | None = Query(default=None),
    project: str | None = Query(default=None),
    repo: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    user: UserRecord = Depends(get_current_user),
) -> list[ProductProposalResponse]:
    database: Database = request.app.state.database
    async with database.session() as session:
        proposals = await ProductProposalRepository.list(
            session,
            status=status,
            project=project,
            repo=repo,
            user_id=user.id,
            limit=limit,
        )
    return [ProductProposalResponse.from_record(proposal) for proposal in proposals]


@router.get("/proposals/{proposal_id}", response_model=ProductProposalResponse)
async def get_proposal(
    request: Request,
    proposal_id: uuid.UUID,
    user: UserRecord = Depends(get_current_user),
) -> ProductProposalResponse:
    database: Database = request.app.state.database
    async with database.session() as session:
        proposal = await ProductProposalRepository.get(session, proposal_id)
    if proposal is None or proposal.user_id != user.id:
        raise HTTPException(status_code=404, detail="Proposal not found")
    return ProductProposalResponse.from_record(proposal)


@router.patch("/proposals/{proposal_id}/status", response_model=ProductProposalResponse)
async def update_proposal_status(
    request: Request,
    proposal_id: uuid.UUID,
    payload: ProductProposalStatusUpdateRequest,
    user: UserRecord = Depends(get_current_user),
) -> ProductProposalResponse:
    database: Database = request.app.state.database
    async with database.session() as session:
        existing = await ProductProposalRepository.get(session, proposal_id)
        if existing is None or existing.user_id != user.id:
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
        async with database.session() as session:
            marc_instances = await AgentInstanceRepository.list_by_active_task_load(
                session,
                agent=AgentName.marc,
                user_id=user.id,
                limit=1,
            )
        if not marc_instances:
            raise HTTPException(status_code=409, detail="No active Marc agent instance is available")

        runner: AgentTaskRunner = request.app.state.runner
        await runner.submit_task(
            TaskCreateRequest(
                agent_instance_id=marc_instances[0].id,
                agent=AgentKind.marc,
                question=(
                    "Plan the approved product proposal below. "
                    "Create one or more features, then create one or more feature items for each feature.\n\n"
                    f"Proposal ID: {proposal.id}\n"
                    f"Title: {proposal.title}\n"
                    f"Plan type: {proposal.plan_type}\n"
                    f"Project: {proposal.project}\n"
                    f"Repo: {proposal.repo}\n"
                    f"Summary: {proposal.summary}\n"
                    f"Answer: {proposal.answer}"
                ),
                repo=proposal.repo,
                project=proposal.project,
                external_issue_url=None,
            )
        )
    return ProductProposalResponse.from_record(proposal)


@router.get("/features", response_model=list[FeatureResponse])
async def list_features(
    request: Request,
    status: FeatureStatus | None = Query(default=None),
    project: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    user: UserRecord = Depends(get_current_user),
) -> list[FeatureResponse]:
    database: Database = request.app.state.database
    async with database.session() as session:
        features = await FeatureRepository.list(
            session,
            status=status,
            project=project,
            user_id=user.id,
            limit=limit,
        )
    return [FeatureResponse.from_record(feature) for feature in features]


@router.get("/features/{feature_id}", response_model=FeatureResponse)
async def get_feature(
    request: Request,
    feature_id: uuid.UUID,
    user: UserRecord = Depends(get_current_user),
) -> FeatureResponse:
    database: Database = request.app.state.database
    async with database.session() as session:
        feature = await FeatureRepository.get(session, feature_id)
        if feature is None:
            raise HTTPException(status_code=404, detail="Feature not found")
        if feature.proposal_id is None:
            raise HTTPException(status_code=404, detail="Feature not found")
        proposal = await ProductProposalRepository.get(session, feature.proposal_id)
        if proposal is None or proposal.user_id != user.id:
            raise HTTPException(status_code=404, detail="Feature not found")
        items = await FeatureItemRepository.list_by_feature(session, feature_id)
    return FeatureResponse.from_record(feature, items=items)
