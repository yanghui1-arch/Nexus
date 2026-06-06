from __future__ import annotations

import uuid
from decimal import Decimal
from datetime import datetime, timedelta, timezone
from typing import Any, cast

from openai.types.chat.chat_completion_message_param import ChatCompletionMessageParam
from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.server.postgres.models import (
    AgentInstanceRecord,
    AgentName,
    AgentPurchaseRecord,
    AuthSessionRecord,
    FeatureItemRecord,
    FeatureItemStatus,
    FeatureRecord,
    FeatureStatus,
    ProductProposalRecord,
    ProductProposalStatus,
    ProposalPlanningRunRecord,
    ProposalPlanningRunStatus,
    TaskCategory,
    GithubPullRequestFeedbackKind,
    GithubPullRequestFeedbackRecord,
    GithubPullRequestFeedbackStatus,
    TaskRecord,
    TaskStatus,
    TaskWorkItemRecord,
    TaskWorkItemStatus,
    UserRecord,
    WorkspaceRecord,
    WorkspaceStatus,
)


def utc_now() -> datetime:
    """Return the current UTC timestamp."""
    return datetime.now(timezone.utc)


class AgentInstanceRepository:
    @staticmethod
    async def list_by_active_task_load(
        session: AsyncSession,
        *,
        agent: AgentName,
        user_id: uuid.UUID | None = None,
        github_repo: str | None = None,
        project: str | None = None,
        limit: int = 100,
    ) -> list[AgentInstanceRecord]:
        """List agent instances ordered by active task load."""
        active_statuses = [
            TaskStatus.queued,
            TaskStatus.running,
            TaskStatus.waiting_for_review,
        ]
        load_query = (
            select(
                TaskRecord.agent_instance_id.label("agent_instance_id"),
                func.count(TaskRecord.id).label("active_task_count"),
            )
            .where(
                TaskRecord.category == TaskCategory.coding,
                TaskRecord.status.in_(active_statuses),
            )
            .group_by(TaskRecord.agent_instance_id)
            .subquery()
        )
        query = (
            select(AgentInstanceRecord)
            .outerjoin(load_query, AgentInstanceRecord.id == load_query.c.agent_instance_id)
            .where(
                AgentInstanceRecord.agent == agent,
                AgentInstanceRecord.is_active.is_(True),
            )
        )
        if user_id is not None:
            query = query.where(AgentInstanceRecord.user_id == user_id)
        if github_repo is not None or project is not None:
            query = query.join(WorkspaceRecord, WorkspaceRecord.agent_instance_id == AgentInstanceRecord.id).where(
                WorkspaceRecord.github_repo == github_repo,
                WorkspaceRecord.project == project,
            )
        query = query.order_by(
            func.coalesce(load_query.c.active_task_count, 0).asc(),
            AgentInstanceRecord.created_at.asc(),
        ).limit(limit)
        result = await session.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def create(
        session: AsyncSession,
        *,
        agent: AgentName,
        client_id: str,
        display_name: str | None,
        user_id: uuid.UUID,
        is_active: bool = True,
    ) -> AgentInstanceRecord:
        """Create a new database record."""
        instance = AgentInstanceRecord(
            user_id=user_id,
            agent=agent,
            client_id=client_id,
            display_name=display_name,
            is_active=is_active,
        )
        session.add(instance)
        await session.commit()
        await session.refresh(instance)
        return instance

    @staticmethod
    async def list_product_discovery_candidates(
        session: AsyncSession,
        *,
        limit: int = 200,
    ) -> list[AgentInstanceRecord]:
        """List agent instances eligible for product discovery."""
        query = (
            select(AgentInstanceRecord)
            .where(
                AgentInstanceRecord.agent == AgentName.marc,
                AgentInstanceRecord.is_active.is_(True),
            )
            .order_by(AgentInstanceRecord.created_at.asc())
            .limit(limit)
        )
        result = await session.execute(query)
        instances = list(result.scalars().all())

        if not instances:
            return []

        candidate_ids = [instance.id for instance in instances]
        task_query = (
            select(TaskRecord.agent_instance_id)
            .where(
                TaskRecord.agent_instance_id.in_(candidate_ids),
                TaskRecord.category == TaskCategory.pm,
                TaskRecord.status.in_(
                    [
                        TaskStatus.queued,
                        TaskStatus.running,
                    ]
                ),
            )
        )
        task_result = await session.execute(task_query)
        blocked_ids = set(task_result.scalars().all())
        return [instance for instance in instances if instance.id not in blocked_ids]

    @staticmethod
    async def get(session: AsyncSession, instance_id: uuid.UUID) -> AgentInstanceRecord | None:
        """Return a record by identifier."""
        return await session.get(AgentInstanceRecord, instance_id)

    @staticmethod
    async def list(
        session: AsyncSession,
        *,
        agent: AgentName | None = None,
        client_id: str | None = None,
        is_active: bool | None = None,
        user_id: uuid.UUID | None = None,
        limit: int = 500,
    ) -> list[AgentInstanceRecord]:
        """List records matching filters."""
        query = select(AgentInstanceRecord)
        if user_id is not None:
            query = query.where(AgentInstanceRecord.user_id == user_id)
        if agent is not None:
            query = query.where(AgentInstanceRecord.agent == agent)
        if client_id is not None:
            query = query.where(AgentInstanceRecord.client_id == client_id)
        if is_active is not None:
            query = query.where(AgentInstanceRecord.is_active == is_active)
        query = query.order_by(AgentInstanceRecord.created_at.asc()).limit(limit)
        result = await session.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def set_active(
        session: AsyncSession,
        instance_id: uuid.UUID,
        *,
        is_active: bool,
    ) -> AgentInstanceRecord | None:
        """Set whether an agent instance is active."""
        instance = await AgentInstanceRepository.get(session, instance_id)
        if instance is None:
            return None
        instance.is_active = is_active
        instance.updated_at = utc_now()
        await session.commit()
        await session.refresh(instance)
        return instance

    @staticmethod
    async def set_display_name(
        session: AsyncSession,
        instance_id: uuid.UUID,
        *,
        display_name: str | None,
    ) -> AgentInstanceRecord | None:
        """Update the user-facing display name for an agent instance."""
        instance = await AgentInstanceRepository.get(session, instance_id)
        if instance is None:
            return None
        instance.display_name = display_name
        instance.updated_at = utc_now()
        await session.commit()
        await session.refresh(instance)
        return instance


class WorkspaceRepository:
    @staticmethod
    async def get_by_agent_instance_id(
        session: AsyncSession,
        agent_instance_id: uuid.UUID,
    ) -> WorkspaceRecord | None:
        """Return a record for an agent instance."""
        query = select(WorkspaceRecord).where(WorkspaceRecord.agent_instance_id == agent_instance_id)
        result = await session.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def list_for_user(
        session: AsyncSession,
        *,
        user_id: uuid.UUID,
    ) -> list[WorkspaceRecord]:
        """List records visible to a user."""
        query = (
            select(WorkspaceRecord)
            .join(AgentInstanceRecord, AgentInstanceRecord.id == WorkspaceRecord.agent_instance_id)
            .where(AgentInstanceRecord.user_id == user_id)
        )
        result = await session.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def ensure_for_agent_instance(
        session: AsyncSession,
        agent_instance: AgentInstanceRecord,
    ) -> WorkspaceRecord:
        """Ensure an agent instance has a durable workspace record.

        The workspace stores frontend-owned repo/project context plus worker-owned
        runtime status. Task execution may flip status, but repo/project should be
        updated explicitly by the frontend workflow instead of inferred from tasks.
        """
        workspace = await WorkspaceRepository.get_by_agent_instance_id(session, agent_instance.id)
        if workspace is None:
            workspace = WorkspaceRecord(
                agent_instance_id=agent_instance.id,
                workspace_key=f"agent-instance:{agent_instance.id}",
                github_repo=None,
                project=None,
                status=WorkspaceStatus.idle,
            )
            session.add(workspace)
            await session.commit()
            await session.refresh(workspace)
        return workspace

    @staticmethod
    async def set_running(
        session: AsyncSession,
        *,
        agent_instance_id: uuid.UUID,
    ) -> WorkspaceRecord | None:
        """Mark a record as running."""
        return await WorkspaceRepository._set_status(
            session,
            agent_instance_id=agent_instance_id,
            status=WorkspaceStatus.running,
        )

    @staticmethod
    async def set_context(
        session: AsyncSession,
        *,
        agent_instance_id: uuid.UUID,
        github_repo: str | None,
        project: str | None,
    ) -> WorkspaceRecord | None:
        """Update workspace repository and project context."""
        workspace = await WorkspaceRepository.get_by_agent_instance_id(session, agent_instance_id)
        if workspace is None:
            return None

        now = utc_now()
        workspace.github_repo = github_repo
        workspace.project = project
        workspace.last_used_at = now
        workspace.updated_at = now
        await session.commit()
        await session.refresh(workspace)
        return workspace

    @staticmethod
    async def set_idle(
        session: AsyncSession,
        *,
        agent_instance_id: uuid.UUID,
    ) -> WorkspaceRecord | None:
        """Mark a workspace as idle."""
        return await WorkspaceRepository._set_status(
            session,
            agent_instance_id=agent_instance_id,
            status=WorkspaceStatus.idle,
        )

    @staticmethod
    async def set_inactive(
        session: AsyncSession,
        *,
        agent_instance_id: uuid.UUID,
    ) -> WorkspaceRecord | None:
        """Mark a workspace as inactive."""
        return await WorkspaceRepository._set_status(
            session,
            agent_instance_id=agent_instance_id,
            status=WorkspaceStatus.inactive,
        )

    @staticmethod
    async def _set_status(
        session: AsyncSession,
        *,
        agent_instance_id: uuid.UUID,
        status: WorkspaceStatus,
    ) -> WorkspaceRecord | None:
        """Set a record status."""
        workspace = await WorkspaceRepository.get_by_agent_instance_id(session, agent_instance_id)
        if workspace is None:
            return None

        now = utc_now()
        workspace.status = status
        workspace.last_used_at = now
        workspace.updated_at = now
        await session.commit()
        await session.refresh(workspace)
        return workspace

class ProductProposalRepository:
    @staticmethod
    async def create(
        session: AsyncSession,
        *,
        title: str,
        plan_type: str,
        summary: str,
        answer: str,
        user_id: uuid.UUID,
        project: str | None,
        repo: str | None,
        source_task_id: uuid.UUID | None = None,
    ) -> ProductProposalRecord:
        """Create a new database record."""
        proposal = ProductProposalRecord(
            title=title,
            plan_type=plan_type,
            summary=summary,
            answer=answer,
            user_id=user_id,
            project=project,
            repo=repo,
            source_task_id=source_task_id,
            status=ProductProposalStatus.proposed,
        )
        session.add(proposal)
        await session.commit()
        await session.refresh(proposal)
        return proposal

    @staticmethod
    async def get(session: AsyncSession, proposal_id: uuid.UUID) -> ProductProposalRecord | None:
        """Return a record by identifier."""
        return await session.get(ProductProposalRecord, proposal_id)

    @staticmethod
    async def list(
        session: AsyncSession,
        *,
        user_id: uuid.UUID | None = None,
        status: ProductProposalStatus | None = None,
        project: str | None = None,
        repo: str | None = None,
        limit: int = 200,
    ) -> list[ProductProposalRecord]:
        """List records matching filters."""
        query = select(ProductProposalRecord)
        if user_id is not None:
            query = query.where(ProductProposalRecord.user_id == user_id)
        if status is not None:
            query = query.where(ProductProposalRecord.status == status)
        if project is not None:
            query = query.where(ProductProposalRecord.project == project)
        if repo is not None:
            query = query.where(ProductProposalRecord.repo == repo)
        query = query.order_by(ProductProposalRecord.created_at.desc()).limit(limit)
        result = await session.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def set_status(
        session: AsyncSession,
        proposal_id: uuid.UUID,
        status: ProductProposalStatus,
    ) -> ProductProposalRecord | None:
        """Handle set status."""
        proposal = await session.get(ProductProposalRecord, proposal_id)
        if proposal is None:
            return None
        proposal.status = status
        proposal.updated_at = utc_now()
        await session.commit()
        await session.refresh(proposal)
        return proposal

    @staticmethod
    async def sync_status_from_features(
        session: AsyncSession,
        proposal_id: uuid.UUID,
    ) -> ProductProposalRecord | None:
        # Proposal completion is derived from its linked features rather than set directly.
        """Synchronize proposal status from feature state."""
        proposal = await session.get(ProductProposalRecord, proposal_id)
        if proposal is None:
            return None
        if proposal.status == ProductProposalStatus.rejected:
            return proposal

        result = await session.execute(
            select(FeatureRecord.id, FeatureRecord.status).where(FeatureRecord.proposal_id == proposal_id)
        )
        feature_rows = list(result.all())
        if not feature_rows:
            return proposal

        feature_ids = [row[0] for row in feature_rows]
        item_result = await session.execute(
            select(func.count(FeatureItemRecord.id)).where(FeatureItemRecord.feature_id.in_(feature_ids))
        )
        item_count = int(item_result.scalar_one())
        feature_statuses = [row[1] for row in feature_rows]
        # `planned` means the proposal has a usable implementation plan, not merely
        # feature shells. Until at least one feature item exists, keep the proposal
        # at `approved` and let the planning run status explain the in-flight state.
        next_status = (
            ProductProposalStatus.completed
            if item_count > 0 and all(status in {FeatureStatus.completed, FeatureStatus.closed} for status in feature_statuses)
            else ProductProposalStatus.planned
            if item_count > 0
            else ProductProposalStatus.approved
        )
        if proposal.status != next_status:
            proposal.status = next_status
            proposal.updated_at = utc_now()
        return proposal


class ProposalPlanningRunRepository:
    @staticmethod
    async def create_pending(
        session: AsyncSession,
        *,
        proposal_id: uuid.UUID,
        task_id: uuid.UUID,
    ) -> ProposalPlanningRunRecord:
        """Create a pending tracking record."""
        result = await session.execute(
            select(func.coalesce(func.max(ProposalPlanningRunRecord.attempt), 0)).where(
                ProposalPlanningRunRecord.proposal_id == proposal_id
            )
        )
        next_attempt = int(result.scalar_one()) + 1
        run = ProposalPlanningRunRecord(
            proposal_id=proposal_id,
            task_id=task_id,
            attempt=next_attempt,
            status=ProposalPlanningRunStatus.queued,
        )
        session.add(run)
        await session.flush()
        return run

    @staticmethod
    async def get_by_task_id(
        session: AsyncSession,
        task_id: uuid.UUID,
    ) -> ProposalPlanningRunRecord | None:
        """Return a record for a task."""
        query = select(ProposalPlanningRunRecord).where(ProposalPlanningRunRecord.task_id == task_id)
        result = await session.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_latest_by_proposal(
        session: AsyncSession,
        proposal_id: uuid.UUID,
    ) -> ProposalPlanningRunRecord | None:
        """Return the latest planning run for a proposal."""
        query = (
            select(ProposalPlanningRunRecord)
            .where(ProposalPlanningRunRecord.proposal_id == proposal_id)
            .order_by(ProposalPlanningRunRecord.attempt.desc(), ProposalPlanningRunRecord.created_at.desc())
            .limit(1)
        )
        result = await session.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_latest_by_proposal_ids(
        session: AsyncSession,
        proposal_ids: list[uuid.UUID],
    ) -> dict[uuid.UUID, ProposalPlanningRunRecord]:
        """Return latest planning runs for proposal ids."""
        if not proposal_ids:
            return {}
        query = (
            select(ProposalPlanningRunRecord)
            .where(ProposalPlanningRunRecord.proposal_id.in_(proposal_ids))
            .order_by(
                ProposalPlanningRunRecord.proposal_id.asc(),
                ProposalPlanningRunRecord.attempt.desc(),
                ProposalPlanningRunRecord.created_at.desc(),
            )
        )
        result = await session.execute(query)
        latest_by_proposal_id: dict[uuid.UUID, ProposalPlanningRunRecord] = {}
        for run in result.scalars().all():
            latest_by_proposal_id.setdefault(run.proposal_id, run)
        return latest_by_proposal_id

    @staticmethod
    async def validate_plan(
        session: AsyncSession,
        proposal_id: uuid.UUID,
    ) -> str | None:
        """Validate whether a proposal has a usable generated plan.

        A planning run is only considered successful when it creates at least one
        feature and every created feature has at least one feature item. This is
        the minimum structure required for downstream product workflow to publish
        executable coding tasks.

        Args:
            session: Active database session used to inspect generated features and
                feature items.
            proposal_id: Identifier of the approved proposal whose generated plan
                should be checked.

        Returns:
            None if the generated plan is structurally valid. Otherwise returns a
            human-readable validation error describing why the plan is incomplete.
        """
        feature_result = await session.execute(
            select(FeatureRecord.id).where(FeatureRecord.proposal_id == proposal_id).order_by(FeatureRecord.created_at.asc())
        )
        feature_ids = list(feature_result.scalars().all())
        if not feature_ids:
            return "Planning task completed without creating any features."

        # Planning is considered successful only when every created feature has
        # at least one executable feature item. Otherwise the proposal would still
        # be reviewable in UI but unusable for downstream coding task publishing.
        rows = await session.execute(
            select(FeatureRecord.id, func.count(FeatureItemRecord.id))
            .outerjoin(FeatureItemRecord, FeatureItemRecord.feature_id == FeatureRecord.id)
            .where(FeatureRecord.proposal_id == proposal_id)
            .group_by(FeatureRecord.id)
        )
        empty_feature_count = sum(1 for _, item_count in rows.all() if int(item_count) == 0)
        if empty_feature_count > 0:
            return f"Planning task completed with {empty_feature_count} feature(s) missing feature items."
        return None

    @staticmethod
    async def set_running(
        session: AsyncSession,
        run_id: uuid.UUID,
    ) -> ProposalPlanningRunRecord | None:
        """Mark a record as running."""
        run = await session.get(ProposalPlanningRunRecord, run_id)
        if run is None:
            return None

        now = utc_now()
        run.status = ProposalPlanningRunStatus.running
        run.error = None
        run.started_at = run.started_at or now
        run.finished_at = None
        run.updated_at = now
        await session.commit()
        await session.refresh(run)
        return run

    @staticmethod
    async def set_failed(
        session: AsyncSession,
        run_id: uuid.UUID,
        *,
        error: str,
    ) -> ProposalPlanningRunRecord | None:
        """Mark a record as failed."""
        run = await session.get(ProposalPlanningRunRecord, run_id)
        if run is None:
            return None

        now = utc_now()
        run.status = ProposalPlanningRunStatus.failed
        run.error = error
        run.finished_at = now
        run.updated_at = now
        await session.commit()
        await session.refresh(run)
        return run

    @staticmethod
    async def set_completed(
        session: AsyncSession,
        run_id: uuid.UUID,
    ) -> ProposalPlanningRunRecord | None:
        """Mark a record as completed."""
        run = await session.get(ProposalPlanningRunRecord, run_id)
        if run is None:
            return None

        now = utc_now()
        run.status = ProposalPlanningRunStatus.completed
        run.error = None
        run.started_at = run.started_at or now
        run.finished_at = now
        run.updated_at = now
        await session.commit()
        await session.refresh(run)
        return run


class FeatureRepository:
    @staticmethod
    async def create(
        session: AsyncSession,
        *,
        proposal_id: uuid.UUID | None,
        title: str,
        description: str,
        project: str | None,
    ) -> FeatureRecord:
        """Create a new database record."""
        feature = FeatureRecord(
            proposal_id=proposal_id,
            title=title,
            description=description,
            project=project,
            status=FeatureStatus.planned,
        )
        session.add(feature)
        await session.flush()
        await session.commit()
        await session.refresh(feature)
        return feature

    async def get(session: AsyncSession, feature_id: uuid.UUID) -> FeatureRecord | None:
        """Return a record by identifier."""
        return await session.get(FeatureRecord, feature_id)

    @staticmethod
    async def list(
        session: AsyncSession,
        *,
        user_id: uuid.UUID | None = None,
        status: FeatureStatus | None = None,
        project: str | None = None,
        limit: int = 200,
    ) -> list[FeatureRecord]:
        """List records matching filters."""
        query = select(FeatureRecord)
        if user_id is not None:
            query = query.join(
                ProductProposalRecord,
                ProductProposalRecord.id == FeatureRecord.proposal_id,
            ).where(ProductProposalRecord.user_id == user_id)
        if status is not None:
            query = query.where(FeatureRecord.status == status)
        if project is not None:
            query = query.where(FeatureRecord.project == project)
        query = query.order_by(FeatureRecord.created_at.desc()).limit(limit)
        result = await session.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def sync_status_from_items(
        session: AsyncSession,
        feature_id: uuid.UUID,
    ) -> FeatureRecord | None:
        """Synchronize feature status from item state."""
        feature = await session.get(FeatureRecord, feature_id)
        if feature is None:
            return None

        result = await session.execute(
            select(FeatureItemRecord.status).where(FeatureItemRecord.feature_id == feature_id)
        )
        item_statuses = list(result.scalars().all())
        if not item_statuses:
            return feature

        next_status = (
            FeatureStatus.completed
            if all(status in {FeatureItemStatus.completed, FeatureItemStatus.closed} for status in item_statuses)
            else FeatureStatus.in_progress
            if any(status == FeatureItemStatus.in_progress for status in item_statuses)
            else FeatureStatus.planned
        )
        if feature.status != next_status:
            feature.status = next_status
            feature.updated_at = utc_now()
        if feature.proposal_id is not None:
            # Feature-item progress rolls the parent feature forward, which can also advance the parent proposal.
            await ProductProposalRepository.sync_status_from_features(session, feature.proposal_id)
        return feature


class FeatureItemRepository:
    @staticmethod
    async def get_feature(session: AsyncSession, item_id: uuid.UUID) -> FeatureRecord | None:
        """Return the related feature record."""
        query = (
            select(FeatureRecord)
            .join(FeatureItemRecord, FeatureItemRecord.feature_id == FeatureRecord.id)
            .where(FeatureItemRecord.id == item_id)
        )
        result = await session.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_repo(session: AsyncSession, item_id: uuid.UUID) -> str | None:
        """Return the repository for a record."""
        query = (
            select(ProductProposalRecord.repo)
            .join(FeatureRecord, FeatureRecord.proposal_id == ProductProposalRecord.id)
            .join(FeatureItemRecord, FeatureItemRecord.feature_id == FeatureRecord.id)
            .where(FeatureItemRecord.id == item_id)
        )
        result = await session.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_proposal(session: AsyncSession, item_id: uuid.UUID) -> ProductProposalRecord | None:
        """Return the related proposal record."""
        query = (
            select(ProductProposalRecord)
            .join(FeatureRecord, FeatureRecord.proposal_id == ProductProposalRecord.id)
            .join(FeatureItemRecord, FeatureItemRecord.feature_id == FeatureRecord.id)
            .where(FeatureItemRecord.id == item_id)
        )
        result = await session.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def list_unassigned_by_proposal(
        session: AsyncSession,
        proposal_id: uuid.UUID,
    ) -> list[FeatureItemRecord]:
        """List unassigned feature items for a proposal."""
        query = (
            select(FeatureItemRecord)
            .join(FeatureRecord, FeatureItemRecord.feature_id == FeatureRecord.id)
            .where(
                FeatureRecord.proposal_id == proposal_id,
                FeatureItemRecord.task_id.is_(None),
                FeatureItemRecord.status == FeatureItemStatus.pending,
            )
            .order_by(FeatureRecord.created_at.asc(), FeatureItemRecord.order_index.asc())
        )
        result = await session.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def assign_task(
        session: AsyncSession,
        item_id: uuid.UUID,
        *,
        task_id: uuid.UUID,
    ) -> FeatureItemRecord | None:
        """Assign a task to a feature item."""
        now = utc_now()
        stmt = (
            update(FeatureItemRecord)
            .where(
                FeatureItemRecord.id == item_id,
                FeatureItemRecord.task_id.is_(None),
            )
            .values(
                task_id=task_id,
                status=FeatureItemStatus.in_progress,
                started_at=now,
                updated_at=now,
            )
            .returning(FeatureItemRecord)
        )
        result = await session.execute(stmt)
        item = result.scalar_one_or_none()
        if item is None:
            await session.rollback()
            return None
        await FeatureRepository.sync_status_from_items(session, item.feature_id)
        await session.commit()
        return item

    @staticmethod
    async def create(
        session: AsyncSession,
        *,
        feature_id: uuid.UUID,
        title: str,
        description: str,
    ) -> FeatureItemRecord:
        """Create a new database record."""
        query = select(func.coalesce(func.max(FeatureItemRecord.order_index), 0)).where(
            FeatureItemRecord.feature_id == feature_id
        )
        result = await session.execute(query)
        next_order_index = int(result.scalar_one()) + 1

        item = FeatureItemRecord(
            feature_id=feature_id,
            order_index=next_order_index,
            title=title,
            description=description,
            status=FeatureItemStatus.pending,
        )
        session.add(item)
        await session.flush()
        await FeatureRepository.sync_status_from_items(session, feature_id)
        await session.commit()
        await session.refresh(item)
        return item

    @staticmethod
    async def list_by_feature(session: AsyncSession, feature_id: uuid.UUID) -> list[FeatureItemRecord]:
        """List feature items for a feature."""
        query = (
            select(FeatureItemRecord)
            .where(FeatureItemRecord.feature_id == feature_id)
            .order_by(FeatureItemRecord.order_index.asc())
        )
        result = await session.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def reassign_task(
        session: AsyncSession,
        *,
        source_task_id: uuid.UUID,
        retry_task_id: uuid.UUID,
    ) -> list[FeatureItemRecord]:
        """Move feature-item ownership from a failed task to its retry task."""
        now = utc_now()
        result = await session.execute(
            select(FeatureItemRecord).where(FeatureItemRecord.task_id == source_task_id)
        )
        items = list(result.scalars().all())
        affected_feature_ids: set[uuid.UUID] = set()
        for item in items:
            item.task_id = retry_task_id
            item.status = FeatureItemStatus.in_progress
            item.finished_at = None
            item.updated_at = now
            if item.started_at is None:
                item.started_at = now
            affected_feature_ids.add(item.feature_id)
        for feature_id in affected_feature_ids:
            await FeatureRepository.sync_status_from_items(session, feature_id)
        return items

    async def set_status_by_task_id(
        session: AsyncSession,
        task_id: uuid.UUID,
        *,
        status: FeatureItemStatus,
        updated_at: datetime,
    ) -> list[FeatureItemRecord]:
        """Set feature item status using its task id."""
        result = await session.execute(
            select(FeatureItemRecord).where(FeatureItemRecord.task_id == task_id)
        )
        items = list(result.scalars().all())
        affected_feature_ids: set[uuid.UUID] = set()
        for item in items:
            item.status = status
            item.updated_at = updated_at
            if item.started_at is None:
                item.started_at = updated_at
            if status in {FeatureItemStatus.completed, FeatureItemStatus.closed}:
                item.finished_at = updated_at
            affected_feature_ids.add(item.feature_id)
        for feature_id in affected_feature_ids:
            await FeatureRepository.sync_status_from_items(session, feature_id)
        await session.commit()
        return items


class TaskRepository:
    @staticmethod
    async def create_pending(
        session: AsyncSession,
        *,
        agent: AgentName,
        agent_instance_id: uuid.UUID,
        category: TaskCategory,
        question: str,
        repo: str | None,
        project: str | None,
        external_issue_url: str | None,
    ) -> TaskRecord:
        """Create a pending tracking record."""
        task = TaskRecord(
            agent=agent,
            agent_instance_id=agent_instance_id,
            category=category,
            question=question,
            repo=repo,
            project=project,
            external_issue_url=external_issue_url,
            status=TaskStatus.queued,
        )
        session.add(task)
        await session.flush()
        return task

    @staticmethod
    async def create(
        session: AsyncSession,
        *,
        agent: AgentName,
        agent_instance_id: uuid.UUID,
        category: TaskCategory,
        question: str,
        repo: str | None,
        project: str | None,
        external_issue_url: str | None,
    ) -> TaskRecord:
        """Create a new database record."""
        task = await TaskRepository.create_pending(
            session,
            agent=agent,
            agent_instance_id=agent_instance_id,
            category=category,
            question=question,
            repo=repo,
            project=project,
            external_issue_url=external_issue_url,
        )
        await session.commit()
        await session.refresh(task)
        return task

    @staticmethod
    async def get(session: AsyncSession, task_id: uuid.UUID) -> TaskRecord | None:
        """Return a record by identifier."""
        return await session.get(TaskRecord, task_id)

    @staticmethod
    async def list_existing_ids(
        session: AsyncSession,
        task_ids: list[uuid.UUID],
    ) -> set[uuid.UUID]:
        if not task_ids:
            return set()
        result = await session.execute(
            select(TaskRecord.id).where(TaskRecord.id.in_(task_ids))
        )
        return set(result.scalars().all())

    @staticmethod
    async def list(
        session: AsyncSession,
        *,
        agent_instance_id: uuid.UUID | None = None,
        status: TaskStatus | None = None,
        category: TaskCategory | None = None,
        repo: str | None = None,
        project: str | None = None,
        user_id: uuid.UUID | None = None,
        limit: int = 200,
    ) -> list[TaskRecord]:
        """List records matching filters."""
        query = select(TaskRecord)
        if user_id is not None:
            query = query.join(AgentInstanceRecord, AgentInstanceRecord.id == TaskRecord.agent_instance_id).where(
                AgentInstanceRecord.user_id == user_id
            )

        if agent_instance_id is not None:
            query = query.where(TaskRecord.agent_instance_id == agent_instance_id)
        if status is not None:
            query = query.where(TaskRecord.status == status)
        if category is not None:
            query = query.where(TaskRecord.category == category)
        if repo is not None or project is not None:
            query = query.join(WorkspaceRecord, WorkspaceRecord.agent_instance_id == TaskRecord.agent_instance_id)
            if repo is not None:
                query = query.where(WorkspaceRecord.github_repo == repo)
            if project is not None:
                query = query.where(WorkspaceRecord.project == project)

        query = query.order_by(TaskRecord.created_at.desc()).limit(limit)
        result = await session.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def list_external_pull_request_candidates(
        session: AsyncSession,
        *,
        limit: int = 200,
    ) -> list[TaskRecord]:
        """List tasks needing external pull request discovery."""
        query = (
            select(TaskRecord)
            .where(
                TaskRecord.category == TaskCategory.coding,
                TaskRecord.repo.is_not(None),
                TaskRecord.external_pull_request_url.is_not(None),
                TaskRecord.status == TaskStatus.waiting_for_review,
            )
            .order_by(TaskRecord.updated_at.asc(), TaskRecord.created_at.asc())
            .limit(limit)
        )
        result = await session.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def list_review_queue(
        session: AsyncSession,
        *,
        limit: int = 200,
    ) -> list[TaskRecord]:
        """List tasks waiting in review queue."""
        reviewable_running_task = and_(
            TaskRecord.status == TaskStatus.running,
            select(TaskWorkItemRecord.id)
            .where(
                TaskWorkItemRecord.task_id == TaskRecord.id,
                TaskWorkItemRecord.status == TaskWorkItemStatus.ready_for_review,
            )
            .exists(),
        )
        query = (
            select(TaskRecord)
            .where(
                TaskRecord.category == TaskCategory.coding,
                or_(
                    TaskRecord.status.in_(
                        [
                            TaskStatus.waiting_for_review,
                            TaskStatus.merged,
                            TaskStatus.closed,
                        ]
                    ),
                    reviewable_running_task,
                )
            )
            .order_by(TaskRecord.updated_at.desc(), TaskRecord.created_at.desc())
            .limit(limit)
        )
        result = await session.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def list_recoverable(
        session: AsyncSession,
        *,
        limit: int = 1000,
    ) -> list[TaskRecord]:
        """Return queued/running tasks whose dispatch lease is missing or expired.
        Recoverable task is three types - Queued tasks but not be submitted, Running task but not finalized
        and Queued tasks submitted to worker but exceeds `celery_visibility_timeout_seconds`.
        """
        now = utc_now()

        lease_missing_or_expired = (
            TaskRecord.dispatch_token.is_(None)
            | TaskRecord.lease_expires_at.is_(None)
            | (TaskRecord.lease_expires_at <= now)
        )
        queued_recoverable = and_(
            TaskRecord.status == TaskStatus.queued,
            lease_missing_or_expired,
        )
        running_recoverable = and_(
            TaskRecord.status == TaskStatus.running,
            lease_missing_or_expired,
        )

        query = (
            select(TaskRecord)
            .where(or_(queued_recoverable, running_recoverable))
            .order_by(TaskRecord.created_at.asc())
            .limit(limit)
        )
        result = await session.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def mark_dispatched(
        session: AsyncSession,
        task_id: uuid.UUID,
        *,
        lease_seconds: int,
    ) -> TaskRecord | None:
        """Acquire a dispatch lease before send_task.

        This is a compare-and-set update in PostgreSQL to prevent duplicate dispatches
        from concurrent runner instances.
        """
        now = utc_now()
        lease_ttl = max(1, lease_seconds)
        token = str(uuid.uuid4())

        stmt = (
            update(TaskRecord)
            .where(
                TaskRecord.id == task_id,
                TaskRecord.status == TaskStatus.queued,
                or_(
                    TaskRecord.dispatch_token.is_(None),
                    TaskRecord.lease_expires_at.is_(None),
                    TaskRecord.lease_expires_at <= now,
                ),
            )
            .values(
                dispatch_token=token,
                lease_expires_at=now + timedelta(seconds=lease_ttl),
                updated_at=now,
            )
            .returning(TaskRecord)
        )

        result = await session.execute(stmt)
        task = result.scalar_one_or_none()
        if task is None:
            await session.rollback()
            return None

        await session.commit()
        return task
    
    @staticmethod
    async def claim_dispatched_running(
        session: AsyncSession,
        task_id: uuid.UUID,
        *,
        dispatch_token: str,
        lease_seconds: int,
        expected_agent_instance_id: uuid.UUID,
    ) -> TaskRecord | None:
        """Worker-side claim: queued -> running only when dispatch_token matches current lease."""
        now = utc_now()

        where_conditions: list[Any] = [
            TaskRecord.id == task_id,
            TaskRecord.status == TaskStatus.queued,
            TaskRecord.dispatch_token == dispatch_token,
            TaskRecord.agent_instance_id == expected_agent_instance_id,
        ]

        stmt = (
            update(TaskRecord)
            .where(*where_conditions)
            .values(
                status=TaskStatus.running,
                started_at=now,
                updated_at=now,
                lease_expires_at=now + timedelta(seconds=max(1, lease_seconds)),
            )
            .returning(TaskRecord)
        )

        try:
            result = await session.execute(stmt)
            task = result.scalar_one_or_none()
            if task is None:
                await session.rollback()
                return None
            await session.commit()
        except IntegrityError:
            await session.rollback()
            return None

        return task
    
    @staticmethod
    async def extend_lease(
        session: AsyncSession,
        task_id: uuid.UUID,
        *,
        dispatch_token: str,
        lease_seconds: int,
        require_running: bool = True,
    ) -> bool:
        """Heartbeat lease extension.

        Recovery only touches tasks with expired leases, so active workers periodically extend this value.
        """
        now = utc_now()

        where_conditions: list[Any] = [
            TaskRecord.id == task_id,
            TaskRecord.dispatch_token == dispatch_token,
        ]
        if require_running:
            where_conditions.append(TaskRecord.status == TaskStatus.running)

        stmt = (
            update(TaskRecord)
            .where(*where_conditions)
            .values(
                lease_expires_at=now + timedelta(seconds=max(1, lease_seconds)),
                updated_at=now,
            )
        )

        result: CursorResult[Any] = cast(CursorResult[Any], await session.execute(stmt))
        if result.rowcount == 0:
            await session.rollback()
            return False

        await session.commit()
        return True
    
    @staticmethod
    async def update_checkpoint(
        session: AsyncSession,
        task_id: uuid.UUID,
        *,
        checkpoint: list[ChatCompletionMessageParam] | None,
    ) -> TaskRecord | None:
        """Persist the latest task checkpoint."""
        task = await session.get(TaskRecord, task_id)
        if task is None:
            return None

        task.checkpoint = checkpoint
        task.updated_at = utc_now()
        await session.commit()
        await session.refresh(task)
        return task

    @staticmethod
    async def set_queued(
        session: AsyncSession,
        task_id: uuid.UUID,
        *,
        error: str | None = None,
    ) -> TaskRecord | None:
        """Set task queued"""

        task = await session.get(TaskRecord, task_id)
        if task is None:
            return None

        now = utc_now()
        task.status = TaskStatus.queued
        task.updated_at = now
        task.result = None
        task.error = error
        task.started_at = None
        task.finished_at = None
        task.dispatch_token = None
        task.lease_expires_at = None
        await session.commit()
        await session.refresh(task)
        return task

    @staticmethod
    async def queue_github_feedback(
        session: AsyncSession,
        task_id: uuid.UUID,
    ) -> TaskRecord | None:
        """Queue GitHub feedback for task execution."""
        task = await session.get(TaskRecord, task_id)
        if task is None:
            return None
        if task.status != TaskStatus.waiting_for_review:
            return None

        now = utc_now()
        task.status = TaskStatus.queued
        task.error = None
        task.finished_at = None
        task.dispatch_token = None
        task.lease_expires_at = None
        task.updated_at = now
        await session.commit()
        await session.refresh(task)
        return task

    @staticmethod
    async def restore_github_feedback_dispatch(
        session: AsyncSession,
        task_id: uuid.UUID,
        *,
        error: str | None = None,
    ) -> TaskRecord | None:
        """Restore a task after feedback dispatch failure."""
        task = await session.get(TaskRecord, task_id)
        if task is None:
            return None

        task.status = TaskStatus.waiting_for_review
        task.resume_status = None
        task.error = error
        task.finished_at = None
        task.dispatch_token = None
        task.lease_expires_at = None
        task.updated_at = utc_now()
        await session.commit()
        await session.refresh(task)
        return task

    @staticmethod
    async def set_waiting_for_review(
        session: AsyncSession,
        task_id: uuid.UUID,
        *,
        result: str | None,
    ) -> TaskRecord | None:
        """Mark a task as waiting for review."""
        task = await session.get(TaskRecord, task_id)
        if task is None:
            return None

        now = utc_now()
        task.status = TaskStatus.waiting_for_review
        task.result = result
        task.error = None
        task.finished_at = None
        task.resume_status = None
        task.updated_at = now
        task.dispatch_token = None
        task.lease_expires_at = None
        await session.commit()
        await session.refresh(task)
        return task

    @staticmethod
    async def set_merged(
        session: AsyncSession,
        task_id: uuid.UUID,
    ) -> TaskRecord | None:
        """Mark a task as merged."""
        task = await session.get(TaskRecord, task_id)
        if task is None:
            return None

        now = utc_now()
        task.status = TaskStatus.merged
        task.error = None
        task.finished_at = now
        task.resume_status = None
        task.updated_at = now
        task.dispatch_token = None
        task.lease_expires_at = None
        await session.commit()
        await session.refresh(task)
        return task

    @staticmethod
    async def set_closed(
        session: AsyncSession,
        task_id: uuid.UUID,
    ) -> TaskRecord | None:
        """Mark a task as closed."""
        task = await session.get(TaskRecord, task_id)
        if task is None:
            return None

        now = utc_now()
        task.status = TaskStatus.closed
        task.error = None
        task.finished_at = now
        task.resume_status = None
        task.updated_at = now
        task.dispatch_token = None
        task.lease_expires_at = None
        await session.commit()
        await session.refresh(task)
        return task

    @staticmethod
    async def set_failed(
        session: AsyncSession,
        task_id: uuid.UUID,
        *,
        error: str,
    ) -> TaskRecord | None:
        """Mark a record as failed."""
        task = await session.get(TaskRecord, task_id)
        if task is None:
            return None

        now = utc_now()
        task.status = TaskStatus.failed
        task.error = error
        task.finished_at = now
        task.resume_status = None
        task.updated_at = now
        task.dispatch_token = None
        task.lease_expires_at = None
        await session.commit()
        await session.refresh(task)
        return task

    @staticmethod
    async def set_external_pull_request_url(
        session: AsyncSession,
        task_id: uuid.UUID,
        *,
        external_pull_request_url: str | None,
    ) -> TaskRecord | None:
        """Store the task pull request URL."""
        task = await session.get(TaskRecord, task_id)
        if task is None:
            return None

        task.external_pull_request_url = external_pull_request_url
        task.updated_at = utc_now()
        await session.commit()
        await session.refresh(task)
        return task


class TaskWorkItemRepository:
    @staticmethod
    async def create_many(
        session: AsyncSession,
        *,
        task_id: uuid.UUID,
        items: list[dict[str, str]],
    ) -> list[TaskWorkItemRecord]:
        """Create multiple task work items."""
        existing = await TaskWorkItemRepository.list_by_task(session, task_id)
        if existing:
            return existing

        records = [
            TaskWorkItemRecord(
                task_id=task_id,
                order_index=index,
                title=item["title"].strip(),
                description=item["description"].strip(),
                status=TaskWorkItemStatus.pending,
            )
            for index, item in enumerate(items, start=1)
        ]
        session.add_all(records)
        await session.commit()
        for record in records:
            await session.refresh(record)
        return records

    @staticmethod
    async def list_by_task(
        session: AsyncSession,
        task_id: uuid.UUID,
    ) -> list[TaskWorkItemRecord]:
        """List work items for a task."""
        query = (
            select(TaskWorkItemRecord)
            .where(TaskWorkItemRecord.task_id == task_id)
            .order_by(TaskWorkItemRecord.order_index.asc())
        )
        result = await session.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def count_by_task(session: AsyncSession, task_id: uuid.UUID) -> int:
        """Count work items for a task."""
        return len(await TaskWorkItemRepository.list_by_task(session, task_id))

    @staticmethod
    async def get(
        session: AsyncSession,
        work_item_id: uuid.UUID,
    ) -> TaskWorkItemRecord | None:
        """Return a record by identifier."""
        return await session.get(TaskWorkItemRecord, work_item_id)

    @staticmethod
    async def get_running(
        session: AsyncSession,
        task_id: uuid.UUID,
    ) -> TaskWorkItemRecord | None:
        """Return the currently running work item."""
        query = select(TaskWorkItemRecord).where(
            TaskWorkItemRecord.task_id == task_id,
            TaskWorkItemRecord.status == TaskWorkItemStatus.running,
        )
        result = await session.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_next_for_execution(
        session: AsyncSession,
        task_id: uuid.UUID,
    ) -> TaskWorkItemRecord | None:
        """Return the next work item ready to execute."""
        query = (
            select(TaskWorkItemRecord)
            .where(
                TaskWorkItemRecord.task_id == task_id,
                TaskWorkItemRecord.status == TaskWorkItemStatus.pending,
            )
            .order_by(TaskWorkItemRecord.order_index.asc())
            .limit(1)
        )
        result = await session.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def set_running(
        session: AsyncSession,
        work_item_id: uuid.UUID,
    ) -> TaskWorkItemRecord | None:
        """Mark a record as running."""
        work_item = await session.get(TaskWorkItemRecord, work_item_id)
        if work_item is None:
            return None

        now = utc_now()
        previous_status = work_item.status
        work_item.status = TaskWorkItemStatus.running
        work_item.summary = None
        if previous_status == TaskWorkItemStatus.pending:
            work_item.local_path = None
            previous_item = await TaskWorkItemRepository.get_previous(session, work_item)
            work_item.base_commit = previous_item.head_commit if previous_item else None
        work_item.head_commit = None
        work_item.started_at = now
        work_item.finished_at = None
        work_item.updated_at = now
        await session.commit()
        await session.refresh(work_item)
        return work_item

    async def get_previous(
        session: AsyncSession,
        work_item: TaskWorkItemRecord,
    ) -> TaskWorkItemRecord | None:
        """Return the previous work item."""
        if work_item.order_index <= 1:
            return None
        query = select(TaskWorkItemRecord).where(
            TaskWorkItemRecord.task_id == work_item.task_id,
            TaskWorkItemRecord.order_index == work_item.order_index - 1,
        )
        result = await session.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def mark_ready_for_review(
        session: AsyncSession,
        work_item_id: uuid.UUID,
        *,
        summary: str,
        base_commit: str,
        head_commit: str,
        local_path: str,
    ) -> TaskWorkItemRecord | None:
        """Mark a work item ready for review."""
        work_item = await session.get(TaskWorkItemRecord, work_item_id)
        if work_item is None:
            return None

        now = utc_now()
        work_item.status = TaskWorkItemStatus.ready_for_review
        work_item.summary = summary
        work_item.base_commit = base_commit
        work_item.head_commit = head_commit
        work_item.local_path = local_path
        work_item.finished_at = now
        work_item.updated_at = now
        await session.commit()
        await session.refresh(work_item)
        return work_item

    @staticmethod
    async def mark_approved(
        session: AsyncSession,
        work_item_id: uuid.UUID,
    ) -> TaskWorkItemRecord | None:
        """Mark a work item approved."""
        return await TaskWorkItemRepository._set_status(
            session,
            work_item_id,
            status=TaskWorkItemStatus.approved,
        )

    @staticmethod
    async def mark_closed(
        session: AsyncSession,
        work_item_id: uuid.UUID,
    ) -> TaskWorkItemRecord | None:
        """Mark a work item closed."""
        return await TaskWorkItemRepository._set_status(
            session,
            work_item_id,
            status=TaskWorkItemStatus.closed,
        )

    @staticmethod
    async def reopen_for_review(
        session: AsyncSession,
        work_item_id: uuid.UUID,
    ) -> TaskWorkItemRecord | None:
        """Reopen a work item for review."""
        return await TaskWorkItemRepository._set_status(
            session,
            work_item_id,
            status=TaskWorkItemStatus.ready_for_review,
        )

    async def _set_status(
        session: AsyncSession,
        work_item_id: uuid.UUID,
        *,
        status: TaskWorkItemStatus,
    ) -> TaskWorkItemRecord | None:
        """Set a record status."""
        work_item = await session.get(TaskWorkItemRecord, work_item_id)
        if work_item is None:
            return None

        work_item.status = status
        work_item.updated_at = utc_now()
        await session.commit()
        await session.refresh(work_item)
        return work_item


class GithubPullRequestFeedbackRepository:
    @staticmethod
    async def upsert_discovered(
        session: AsyncSession,
        *,
        task_id: uuid.UUID,
        pull_request_number: int,
        kind: GithubPullRequestFeedbackKind,
        external_id: str,
        status: GithubPullRequestFeedbackStatus,
        author: str | None,
        body: str | None,
        review_state: str | None = None,
        file_path: str | None = None,
        line: int | None = None,
        original_line: int | None = None,
        commit_id: str | None = None,
        html_url: str | None = None,
        external_created_at: datetime | None = None,
        external_updated_at: datetime | None = None,
        ignored_reason: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> tuple[GithubPullRequestFeedbackRecord, bool]:
        """Create or refresh one discovered GitHub feedback record.

        Args:
            session: Active database session.
            task_id: Nexus task that owns the external pull request.
            pull_request_number: GitHub pull request number for this feedback item.
            kind: Normalized feedback kind, such as review, comment, or merge conflict.
            external_id: Stable source identifier used to deduplicate one feedback
                item within a task. GitHub-native events use GitHub's own id as
                text; merge conflicts use a synthetic episode id.
            status: Initial local lifecycle status for the discovered feedback.
            author: GitHub login of the feedback author when available.
            body: Human-readable feedback body.
            review_state: Optional GitHub review state such as APPROVED or
                CHANGES_REQUESTED.
            file_path: Optional file path for inline review comments.
            line: Optional current line number for inline review comments.
            original_line: Optional original line number for inline review comments.
            commit_id: Optional commit SHA associated with the feedback.
            html_url: Optional GitHub URL pointing to the feedback item.
            external_created_at: Creation time reported by GitHub.
            external_updated_at: Last update time reported by GitHub.
            ignored_reason: Local reason for storing the item as ignored.
            payload: Raw GitHub payload kept for debugging and recovery.

        Returns:
            A tuple of ``(record, created)`` where ``record`` is the persisted
            feedback row and ``created`` indicates whether a new row had to be
            inserted instead of refreshing an existing one.
        """
        # Compatibility normalization: the column now stores textual external ids,
        # but older call sites/tests may still pass numeric ids. Keep coercion here
        # for now so cleanup can happen incrementally in one place.
        external_id_value = str(external_id)
        query = select(GithubPullRequestFeedbackRecord).where(
            GithubPullRequestFeedbackRecord.task_id == task_id,
            GithubPullRequestFeedbackRecord.kind == kind,
            GithubPullRequestFeedbackRecord.external_id == external_id_value,
        )
        result = await session.execute(query)
        record = result.scalar_one_or_none()
        now = utc_now()

        if record is None:
            record = GithubPullRequestFeedbackRecord(
                task_id=task_id,
                pull_request_number=pull_request_number,
                kind=kind,
                status=status,
                external_id=external_id_value,
                author=author,
                body=body,
                review_state=review_state,
                file_path=file_path,
                line=line,
                original_line=original_line,
                commit_id=commit_id,
                html_url=html_url,
                external_created_at=external_created_at,
                external_updated_at=external_updated_at,
                ignored_reason=ignored_reason,
                payload=payload,
            )
            session.add(record)
            await session.commit()
            await session.refresh(record)
            return record, True

        record.author = author
        record.body = body
        record.review_state = review_state
        record.file_path = file_path
        record.line = line
        record.original_line = original_line
        record.commit_id = commit_id
        record.html_url = html_url
        record.external_created_at = external_created_at
        record.external_updated_at = external_updated_at
        record.payload = payload
        record.updated_at = now

        # Only the poller may refresh the lifecycle of feedback that has not been
        # claimed/finished yet. Once a worker has moved a record into processing or
        # processed, preserve that worker-owned state and only update the mirrored
        # GitHub metadata above.
        if record.status in {
            GithubPullRequestFeedbackStatus.pending,
            GithubPullRequestFeedbackStatus.ignored,
        }:
            record.status = status
            record.ignored_reason = ignored_reason
            # Reopened actionable feedback should no longer look completed.
            if status != GithubPullRequestFeedbackStatus.processed:
                record.processed_at = None

        await session.commit()
        await session.refresh(record)
        return record, False

    @staticmethod
    async def has_pending_for_task(
        session: AsyncSession,
        task_id: uuid.UUID,
    ) -> bool:
        """Return whether pending feedback exists for a task."""
        query = (
            select(GithubPullRequestFeedbackRecord.id)
            .where(
                GithubPullRequestFeedbackRecord.task_id == task_id,
                GithubPullRequestFeedbackRecord.status == GithubPullRequestFeedbackStatus.pending,
            )
            .limit(1)
        )
        result = await session.execute(query)
        return result.scalar_one_or_none() is not None

    @staticmethod
    async def has_pending_newer_than(
        session: AsyncSession,
        task_id: uuid.UUID,
        *,
        cutoff: datetime,
    ) -> bool:
        """Return whether newer pending feedback exists."""
        query = (
            select(GithubPullRequestFeedbackRecord.id)
            .where(
                GithubPullRequestFeedbackRecord.task_id == task_id,
                GithubPullRequestFeedbackRecord.status == GithubPullRequestFeedbackStatus.pending,
                GithubPullRequestFeedbackRecord.created_at > cutoff,
            )
            .limit(1)
        )
        result = await session.execute(query)
        return result.scalar_one_or_none() is not None

    @staticmethod
    async def claim_pending_by_task(
        session: AsyncSession,
        task_id: uuid.UUID,
        *,
        limit: int = 20,
    ) -> list[GithubPullRequestFeedbackRecord]:
        """Claim pending feedback for a task."""
        query = (
            select(GithubPullRequestFeedbackRecord)
            .where(
                GithubPullRequestFeedbackRecord.task_id == task_id,
                GithubPullRequestFeedbackRecord.status == GithubPullRequestFeedbackStatus.pending,
            )
            .order_by(
                GithubPullRequestFeedbackRecord.external_created_at.asc(),
                GithubPullRequestFeedbackRecord.created_at.asc(),
            )
            .limit(limit)
        )
        result = await session.execute(query)
        records = list(result.scalars().all())
        if not records:
            return []

        now = utc_now()
        for record in records:
            record.status = GithubPullRequestFeedbackStatus.processing
            record.ignored_reason = None
            record.updated_at = now

        await session.commit()
        return records

    @staticmethod
    async def mark_processed(
        session: AsyncSession,
        feedback_ids: list[uuid.UUID],
    ) -> None:
        """Mark feedback as processed."""
        if not feedback_ids:
            return

        now = utc_now()
        query = select(GithubPullRequestFeedbackRecord).where(
            GithubPullRequestFeedbackRecord.id.in_(feedback_ids)
        )
        result = await session.execute(query)
        records = list(result.scalars().all())
        for record in records:
            record.status = GithubPullRequestFeedbackStatus.processed
            record.processed_at = now
            record.updated_at = now
            record.ignored_reason = None
        await session.commit()

    @staticmethod
    async def requeue_processing(
        session: AsyncSession,
        feedback_ids: list[uuid.UUID],
    ) -> None:
        """Requeue stuck processing feedback."""
        if not feedback_ids:
            return

        now = utc_now()
        query = select(GithubPullRequestFeedbackRecord).where(
            GithubPullRequestFeedbackRecord.id.in_(feedback_ids)
        )
        result = await session.execute(query)
        records = list(result.scalars().all())
        for record in records:
            record.status = GithubPullRequestFeedbackStatus.pending
            record.processed_at = None
            record.updated_at = now
        await session.commit()


class UserRepository:
    @staticmethod
    async def get(session: AsyncSession, user_id: uuid.UUID) -> UserRecord | None:
        """Return a record by identifier."""
        return await session.get(UserRecord, user_id)

    @staticmethod
    async def get_by_github_id(session: AsyncSession, github_id: str) -> UserRecord | None:
        """Return a user by GitHub id."""
        result = await session.execute(select(UserRecord).where(UserRecord.github_id == github_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def upsert_github_user(
        session: AsyncSession,
        *,
        github_id: str,
        github_login: str,
        email: str | None,
    ) -> UserRecord:
        """Create or update a GitHub user."""
        user = await UserRepository.get_by_github_id(session, github_id)
        if user is None:
            user = UserRecord(github_id=github_id, github_login=github_login, email=email)
            session.add(user)
        else:
            user.github_login = github_login
            user.email = email or user.email
            user.updated_at = utc_now()
        await session.commit()
        await session.refresh(user)
        return user

    @staticmethod
    async def add_balance(session: AsyncSession, user_id: uuid.UUID, amount: Decimal) -> UserRecord | None:
        """Add balance to a user account."""
        user = await session.get(UserRecord, user_id)
        if user is None:
            return None
        user.balance += amount
        user.updated_at = utc_now()
        await session.commit()
        await session.refresh(user)
        return user


class AuthSessionRepository:
    @staticmethod
    async def create(
        session: AsyncSession,
        *,
        token_hash: str,
        user_id: uuid.UUID,
        expires_at: datetime,
    ) -> AuthSessionRecord:
        """Create a new database record."""
        auth_session = AuthSessionRecord(token_hash=token_hash, user_id=user_id, expires_at=expires_at)
        session.add(auth_session)
        await session.commit()
        await session.refresh(auth_session)
        return auth_session

    @staticmethod
    async def get_user_by_token_hash(session: AsyncSession, token_hash: str) -> UserRecord | None:
        """Return a session user by token hash."""
        result = await session.execute(
            select(UserRecord)
            .join(AuthSessionRecord, AuthSessionRecord.user_id == UserRecord.id)
            .where(AuthSessionRecord.token_hash == token_hash, AuthSessionRecord.expires_at > utc_now())
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def delete(session: AsyncSession, token_hash: str) -> None:
        """Delete a database record."""
        auth_session = await session.get(AuthSessionRecord, token_hash)
        if auth_session is not None:
            await session.delete(auth_session)
            await session.commit()


class AgentPurchaseRepository:
    @staticmethod
    async def create_purchase(
        session: AsyncSession,
        *,
        user_id: uuid.UUID,
        agent: AgentName,
        price: Decimal,
        expires_at: datetime,
    ) -> AgentPurchaseRecord:
        # Purchasing touches user balance, agent instance, workspace, and purchase records;
        # keep every related write in this method so one commit/rollback covers the flow.
        """Create an agent purchase record."""
        try:
            user = await session.get(UserRecord, user_id, with_for_update=True)
            if user is None:
                raise ValueError("User not found")
            if user.balance < price:
                raise ValueError("Insufficient balance")

            user.balance -= price
            user.updated_at = utc_now()
            agent_instance = AgentInstanceRecord(
                user_id=user_id,
                agent=agent,
                client_id=f"purchase-{user_id.hex[:8]}-{uuid.uuid4().hex[:8]}",
                display_name=f"{agent.value.title()} subscription",
                expires_at=expires_at,
                is_active=True,
            )
            session.add(agent_instance)
            await session.flush()
            workspace = WorkspaceRecord(
                agent_instance_id=agent_instance.id,
                workspace_key=f"agent-instance:{agent_instance.id}",
                github_repo=None,
                project=None,
                status=WorkspaceStatus.idle,
            )
            session.add(workspace)

            purchase = AgentPurchaseRecord(
                user_id=user_id,
                agent_instance_id=agent_instance.id,
                agent=agent,
                price=price,
            )
            session.add(purchase)
            await session.commit()
            await session.refresh(purchase)
            return purchase
        except Exception:
            await session.rollback()
            raise
