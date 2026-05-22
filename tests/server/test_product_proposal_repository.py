from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.server.postgres.models import ProductProposalRecord, ProductProposalStatus, WorkspaceRecord
from src.server.postgres.repositories import ProductProposalRepository


@pytest.fixture
async def proposal_session():
    """Create an isolated database with product proposal tables."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(
            ProductProposalRecord.metadata.create_all,
            tables=[ProductProposalRecord.__table__],
        )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


async def _create_proposal(session, *, status=ProductProposalStatus.proposed, repo="owner/repo", project="nexus"):
    return await ProductProposalRepository.create(
        session,
        title="Improve product discovery",
        plan_type="feature",
        summary="Add a useful product improvement.",
        answer="Implement the change in small slices.",
        project=project,
        repo=repo,
    ) if status == ProductProposalStatus.proposed else await _create_non_proposed(session, status=status, repo=repo, project=project)


async def _create_non_proposed(session, *, status, repo, project):
    proposal = await ProductProposalRepository.create(
        session,
        title="Improve product discovery",
        plan_type="feature",
        summary="Add a useful product improvement.",
        answer="Implement the change in small slices.",
        project=project,
        repo=repo,
    )
    return await ProductProposalRepository.set_status(session, proposal.id, status)


@pytest.mark.asyncio
async def test_count_pending_for_workspace_returns_zero(proposal_session):
    workspace = WorkspaceRecord(github_repo="owner/repo", project="nexus")

    count = await ProductProposalRepository.count_pending_for_workspace(proposal_session, workspace=workspace)

    assert count == 0


@pytest.mark.asyncio
async def test_count_pending_for_workspace_counts_below_limit(proposal_session):
    workspace = WorkspaceRecord(github_repo="owner/repo", project="nexus")
    await _create_proposal(proposal_session)
    await _create_proposal(proposal_session)

    count = await ProductProposalRepository.count_pending_for_workspace(proposal_session, workspace=workspace)

    assert count == 2
    assert count < 3


@pytest.mark.asyncio
async def test_count_pending_for_workspace_counts_at_limit(proposal_session):
    workspace = WorkspaceRecord(github_repo="owner/repo", project="nexus")
    for _ in range(3):
        await _create_proposal(proposal_session)

    count = await ProductProposalRepository.count_pending_for_workspace(proposal_session, workspace=workspace)

    assert count == 3
    assert count >= 3


@pytest.mark.asyncio
async def test_count_pending_for_workspace_uses_exact_filters_and_ignores_non_proposed(proposal_session):
    workspace = WorkspaceRecord(github_repo="owner/repo", project="nexus")
    await _create_proposal(proposal_session)
    await _create_proposal(proposal_session, repo="owner/other")
    await _create_proposal(proposal_session, project="other-project")
    await _create_proposal(proposal_session, status=ProductProposalStatus.approved)
    await _create_proposal(proposal_session, status=ProductProposalStatus.rejected)
    await _create_proposal(proposal_session, status=ProductProposalStatus.planned)
    await _create_proposal(proposal_session, status=ProductProposalStatus.completed)

    count = await ProductProposalRepository.count_pending_for_workspace(proposal_session, workspace=workspace)

    assert count == 1
