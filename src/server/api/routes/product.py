from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query, Request

from src.server.postgres.database import Database
from src.server.postgres.models import (
    AgentName,
    ProductProposalStatus,
    FeatureItemStatus,
    FeatureStatus,
)
from src.server.postgres.repositories import (
    AgentInstanceRepository,
    ProductProposalRepository,
    FeatureItemRepository,
    FeatureRepository,
)
from src.server.runner import AgentTaskRunner
from src.server.schemas import (
    AgentKind,
    TaskCreateRequest,
    ProductProposalCreateRequest,
    ProductProposalResponse,
    ProductProposalStatusUpdateRequest,
    FeatureCreateRequest,
    FeatureItemResponse,
    FeatureItemStatusUpdateRequest,
    FeatureResponse,
    FeatureStatusUpdateRequest,
)

router = APIRouter(prefix="/v1/product", tags=["product"])


@router.post("/proposals", response_model=ProductProposalResponse, status_code=201)
async def create_proposal(
    request: Request,
    payload: ProductProposalCreateRequest,
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
) -> list[ProductProposalResponse]:
    database: Database = request.app.state.database
    async with database.session() as session:
        proposals = await ProductProposalRepository.list(
            session,
            status=status,
            project=project,
            repo=repo,
            limit=limit,
        )
    return [ProductProposalResponse.from_record(proposal) for proposal in proposals]


@router.get("/proposals/{proposal_id}", response_model=ProductProposalResponse)
async def get_proposal(
    request: Request,
    proposal_id: uuid.UUID,
) -> ProductProposalResponse:
    database: Database = request.app.state.database
    async with database.session() as session:
        proposal = await ProductProposalRepository.get(session, proposal_id)
    if proposal is None:
        raise HTTPException(status_code=404, detail="Proposal not found")
    return ProductProposalResponse.from_record(proposal)


@router.patch("/proposals/{proposal_id}/status", response_model=ProductProposalResponse)
async def update_proposal_status(
    request: Request,
    proposal_id: uuid.UUID,
    payload: ProductProposalStatusUpdateRequest,
) -> ProductProposalResponse:
    database: Database = request.app.state.database
    async with database.session() as session:
        existing = await ProductProposalRepository.get(session, proposal_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="Proposal not found")
        previous_status = existing.status
        proposal = await ProductProposalRepository.set_status(session, proposal_id, payload.status)
    if proposal is None:
        raise HTTPException(status_code=404, detail="Proposal not found")
    if payload.status == ProductProposalStatus.approved and previous_status != ProductProposalStatus.approved:
        # A newly approved proposal needs a separate Marc planning task; coding task publishing is handled by ProductWorkflowPoller.
        async with database.session() as session:
            marc_instances = await AgentInstanceRepository.list_by_active_task_load(
                session,
                agent=AgentName.marc,
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


@router.post("/features", response_model=FeatureResponse, status_code=201)
async def create_feature(
    request: Request,
    payload: FeatureCreateRequest,
) -> FeatureResponse:
    database: Database = request.app.state.database
    async with database.session() as session:
        if payload.proposal_id is not None:
            proposal = await ProductProposalRepository.get(session, payload.proposal_id)
            if proposal is None:
                raise HTTPException(status_code=404, detail="Proposal not found")
            if proposal.status != ProductProposalStatus.approved:
                raise HTTPException(status_code=409, detail="Only approved proposals can become features")
        feature, items = await FeatureRepository.create_with_items(
            session,
            proposal_id=payload.proposal_id,
            title=payload.title,
            description=payload.description,
            project=payload.project,
            items=[item.model_dump() for item in payload.items],
        )
    return FeatureResponse.from_record(feature, items=items)


@router.get("/features", response_model=list[FeatureResponse])
async def list_features(
    request: Request,
    status: FeatureStatus | None = Query(default=None),
    project: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
) -> list[FeatureResponse]:
    database: Database = request.app.state.database
    async with database.session() as session:
        features = await FeatureRepository.list(
            session,
            status=status,
            project=project,
            limit=limit,
        )
    return [FeatureResponse.from_record(feature) for feature in features]


@router.get("/features/{feature_id}", response_model=FeatureResponse)
async def get_feature(
    request: Request,
    feature_id: uuid.UUID,
) -> FeatureResponse:
    database: Database = request.app.state.database
    async with database.session() as session:
        feature = await FeatureRepository.get(session, feature_id)
        if feature is None:
            raise HTTPException(status_code=404, detail="Feature not found")
        items = await FeatureItemRepository.list_by_feature(session, feature_id)
    return FeatureResponse.from_record(feature, items=items)


@router.patch("/features/{feature_id}/status", response_model=FeatureResponse)
async def update_feature_status(
    request: Request,
    feature_id: uuid.UUID,
    payload: FeatureStatusUpdateRequest,
) -> FeatureResponse:
    database: Database = request.app.state.database
    async with database.session() as session:
        feature = await FeatureRepository.set_status(session, feature_id, payload.status)
        if feature is None:
            raise HTTPException(status_code=404, detail="Feature not found")
        items = await FeatureItemRepository.list_by_feature(session, feature_id)
    return FeatureResponse.from_record(feature, items=items)


@router.patch("/feature-items/{item_id}/status", response_model=FeatureItemResponse)
async def update_feature_item_status(
    request: Request,
    item_id: uuid.UUID,
    payload: FeatureItemStatusUpdateRequest,
) -> FeatureItemResponse:
    database: Database = request.app.state.database
    async with database.session() as session:
        item = await FeatureItemRepository.set_status(session, item_id, payload.status)
    if item is None:
        raise HTTPException(status_code=404, detail="Feature item not found")
    return FeatureItemResponse.from_record(item)
