from __future__ import annotations

import re
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
    TaskCategory,
    GithubPullRequestFeedbackKind,
    GithubPullRequestFeedbackRecord,
    GithubPullRequestFeedbackStatus,
    TaskRecord,
    TaskStatus,
    TaskWorkItemRecord,
    TaskWorkItemStatus,
    UserRecord,
    VirtualPullRequestCommentRecord,
    VirtualPullRequestLineSide,
    VirtualPullRequestRecord,
    VirtualPullRequestReviewDecision,
    VirtualPullRequestReviewRecord,
    VirtualPullRequestStatus,
    VirtualPullRequestThreadKind,
    VirtualPullRequestThreadRecord,
    VirtualPullRequestThreadStatus,
    WorkspaceRecord,
    WorkspaceStatus,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


_HUNK_HEADER_RE = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@")


def _normalize_diff_path(value: str) -> str | None:
    trimmed = value.strip()
    if not trimmed or trimmed == "/dev/null":
        return None
    if trimmed.startswith(("a/", "b/")):
        return trimmed[2:]
    return trimmed


def _diff_file_matches(file_path: str, old_path: str | None, new_path: str | None) -> bool:
    if old_path and new_path and old_path != new_path:
        display_path = f"{old_path} \u2192 {new_path}"
    else:
        display_path = new_path or old_path

    candidates = [path for path in (old_path, new_path, display_path) if path]
    return any(candidate == file_path or candidate.endswith(file_path) for candidate in candidates)


def _extract_code_snapshot(
    raw_diff: str | None,
    *,
    file_path: str | None,
    start_line: int | None,
    end_line: int | None,
    line_side: VirtualPullRequestLineSide | None,
) -> str | None:
    if not raw_diff or not file_path or start_line is None or line_side is None:
        return None

    lower_line = min(start_line, end_line or start_line)
    upper_line = max(start_line, end_line or start_line)
    captured: list[str] = []
    old_path: str | None = None
    new_path: str | None = None
    old_line_number = 0
    new_line_number = 0
    in_target_file = False

    def capture(line_number: int | None, raw_line: str) -> None:
        if line_number is not None and lower_line <= line_number <= upper_line:
            captured.append(raw_line)

    for line in raw_diff.replace("\r\n", "\n").split("\n"):
        if line.startswith("diff --git "):
            parts = line.split(" ")
            old_path = _normalize_diff_path(parts[2]) if len(parts) > 2 else None
            new_path = _normalize_diff_path(parts[3]) if len(parts) > 3 else None
            in_target_file = False
            continue
        if line.startswith("--- "):
            old_path = _normalize_diff_path(line[4:])
            continue
        if line.startswith("+++ "):
            new_path = _normalize_diff_path(line[4:])
            continue
        if line.startswith("@@ "):
            match = _HUNK_HEADER_RE.match(line)
            old_line_number = int(match.group(1)) if match else 0
            new_line_number = int(match.group(2)) if match else 0
            in_target_file = _diff_file_matches(file_path, old_path, new_path)
            continue
        if not in_target_file:
            continue

        if line.startswith("+") and not line.startswith("+++"):
            capture(new_line_number if line_side == VirtualPullRequestLineSide.new else None, line)
            new_line_number += 1
            continue
        if line.startswith("-") and not line.startswith("---"):
            capture(old_line_number if line_side == VirtualPullRequestLineSide.old else None, line)
            old_line_number += 1
            continue
        if line.startswith(" "):
            line_number = new_line_number if line_side == VirtualPullRequestLineSide.new else old_line_number
            capture(line_number, line)
            old_line_number += 1
            new_line_number += 1

    return "\n".join(captured) if captured else None


class AgentInstanceRepository:
    @staticmethod
    async def list_by_active_task_load(
        session: AsyncSession,
        *,
        agent: AgentName,
        limit: int = 100,
    ) -> list[AgentInstanceRecord]:
        active_statuses = [
            TaskStatus.queued,
            TaskStatus.running,
            TaskStatus.waiting_for_review,
            TaskStatus.waiting_for_merge,
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
            .order_by(func.coalesce(load_query.c.active_task_count, 0).asc(), AgentInstanceRecord.created_at.asc())
            .limit(limit)
        )
        result = await session.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def create(
        session: AsyncSession,
        *,
        agent: AgentName,
        client_id: str,
        display_name: str | None,
        is_active: bool = True,
    ) -> AgentInstanceRecord:
        instance = AgentInstanceRecord(
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
                        TaskStatus.waiting_for_review,
                        TaskStatus.waiting_for_merge,
                    ]
                ),
            )
        )
        task_result = await session.execute(task_query)
        blocked_ids = set(task_result.scalars().all())
        return [instance for instance in instances if instance.id not in blocked_ids]

    @staticmethod
    async def get(session: AsyncSession, instance_id: uuid.UUID) -> AgentInstanceRecord | None:
        return await session.get(AgentInstanceRecord, instance_id)

    @staticmethod
    async def list(
        session: AsyncSession,
        *,
        agent: AgentName | None = None,
        client_id: str | None = None,
        is_active: bool | None = None,
        limit: int = 500,
    ) -> list[AgentInstanceRecord]:
        query = select(AgentInstanceRecord)
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
        instance = await session.get(AgentInstanceRecord, instance_id)
        if instance is None:
            return None
        instance.is_active = is_active
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
        query = select(WorkspaceRecord).where(WorkspaceRecord.agent_instance_id == agent_instance_id)
        result = await session.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def ensure_for_agent_instance(
        session: AsyncSession,
        agent_instance: AgentInstanceRecord,
    ) -> WorkspaceRecord:
        """Ensure agent instance has a separate workspace."""
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
        github_repo: str,
        project: str | None,
    ) -> WorkspaceRecord | None:
        return await WorkspaceRepository._set_state(
            session,
            agent_instance_id=agent_instance_id,
            status=WorkspaceStatus.running,
            github_repo=github_repo,
            project=project,
        )

    @staticmethod
    async def set_idle(
        session: AsyncSession,
        *,
        agent_instance_id: uuid.UUID,
    ) -> WorkspaceRecord | None:
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

    @staticmethod
    async def _set_state(
        session: AsyncSession,
        *,
        agent_instance_id: uuid.UUID,
        status: WorkspaceStatus,
        github_repo: str | None,
        project: str | None,
    ) -> WorkspaceRecord | None:
        workspace = await WorkspaceRepository.get_by_agent_instance_id(session, agent_instance_id)
        if workspace is None:
            return None

        now = utc_now()
        workspace.status = status
        workspace.github_repo = github_repo
        workspace.project = project
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
        project: str | None,
        repo: str | None,
        source_task_id: uuid.UUID | None = None,
    ) -> ProductProposalRecord:
        proposal = ProductProposalRecord(
            title=title,
            plan_type=plan_type,
            summary=summary,
            answer=answer,
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
        return await session.get(ProductProposalRecord, proposal_id)

    @staticmethod
    async def list(
        session: AsyncSession,
        *,
        status: ProductProposalStatus | None = None,
        project: str | None = None,
        repo: str | None = None,
        limit: int = 200,
    ) -> list[ProductProposalRecord]:
        query = select(ProductProposalRecord)
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
        proposal = await session.get(ProductProposalRecord, proposal_id)
        if proposal is None:
            return None
        proposal.status = status
        proposal.updated_at = utc_now()
        await session.commit()
        await session.refresh(proposal)
        return proposal


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
        feature = FeatureRecord(
            proposal_id=proposal_id,
            title=title,
            description=description,
            project=project,
            status=FeatureStatus.planned,
        )
        session.add(feature)
        await session.flush()
        if proposal_id is not None:
            proposal = await session.get(ProductProposalRecord, proposal_id)
            if proposal is not None:
                proposal.status = ProductProposalStatus.planned
                proposal.updated_at = utc_now()
        await session.commit()
        await session.refresh(feature)
        return feature

    @staticmethod
    async def create_with_items(
        session: AsyncSession,
        *,
        proposal_id: uuid.UUID | None,
        title: str,
        description: str,
        project: str | None,
        items: list[dict[str, str]],
    ) -> tuple[FeatureRecord, list[FeatureItemRecord]]:
        feature = FeatureRecord(
            proposal_id=proposal_id,
            title=title,
            description=description,
            project=project,
            status=FeatureStatus.planned,
        )
        session.add(feature)
        await session.flush()
        feature_items = [
            FeatureItemRecord(
                feature_id=feature.id,
                order_index=index,
                title=item["title"],
                description=item["description"],
                status=FeatureItemStatus.pending,
            )
            for index, item in enumerate(items, start=1)
        ]
        session.add_all(feature_items)
        await session.flush()
        if proposal_id is not None:
            proposal = await session.get(ProductProposalRecord, proposal_id)
            if proposal is not None:
                proposal.status = ProductProposalStatus.planned
                proposal.updated_at = utc_now()
        await session.commit()
        await session.refresh(feature)
        for item in feature_items:
            await session.refresh(item)
        return feature, feature_items

    @staticmethod
    async def get(session: AsyncSession, feature_id: uuid.UUID) -> FeatureRecord | None:
        return await session.get(FeatureRecord, feature_id)

    @staticmethod
    async def list(
        session: AsyncSession,
        *,
        status: FeatureStatus | None = None,
        project: str | None = None,
        limit: int = 200,
    ) -> list[FeatureRecord]:
        query = select(FeatureRecord)
        if status is not None:
            query = query.where(FeatureRecord.status == status)
        if project is not None:
            query = query.where(FeatureRecord.project == project)
        query = query.order_by(FeatureRecord.created_at.desc()).limit(limit)
        result = await session.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def set_status(
        session: AsyncSession,
        feature_id: uuid.UUID,
        status: FeatureStatus,
    ) -> FeatureRecord | None:
        feature = await session.get(FeatureRecord, feature_id)
        if feature is None:
            return None
        feature.status = status
        feature.updated_at = utc_now()
        await session.commit()
        await session.refresh(feature)
        return feature


class FeatureItemRepository:
    @staticmethod
    async def get_next_unassigned(session: AsyncSession) -> FeatureItemRecord | None:
        query = (
            select(FeatureItemRecord)
            .where(
                FeatureItemRecord.task_id.is_(None),
                FeatureItemRecord.status == FeatureItemStatus.pending,
            )
            .order_by(FeatureItemRecord.created_at.asc(), FeatureItemRecord.order_index.asc())
            .limit(1)
        )
        result = await session.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_feature(session: AsyncSession, item_id: uuid.UUID) -> FeatureRecord | None:
        query = (
            select(FeatureRecord)
            .join(FeatureItemRecord, FeatureItemRecord.feature_id == FeatureRecord.id)
            .where(FeatureItemRecord.id == item_id)
        )
        result = await session.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_repo(session: AsyncSession, item_id: uuid.UUID) -> str | None:
        query = (
            select(ProductProposalRecord.repo)
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
        result: CursorResult[Any] = cast(CursorResult[Any], await session.execute(stmt))
        item = result.scalar_one_or_none()
        if item is None:
            await session.rollback()
            return None
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
        await session.commit()
        await session.refresh(item)
        return item

    @staticmethod
    async def list_by_feature(session: AsyncSession, feature_id: uuid.UUID) -> list[FeatureItemRecord]:
        query = (
            select(FeatureItemRecord)
            .where(FeatureItemRecord.feature_id == feature_id)
            .order_by(FeatureItemRecord.order_index.asc())
        )
        result = await session.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def set_status(
        session: AsyncSession,
        item_id: uuid.UUID,
        status: FeatureItemStatus,
    ) -> FeatureItemRecord | None:
        item = await session.get(FeatureItemRecord, item_id)
        if item is None:
            return None
        item.status = status
        item.updated_at = utc_now()
        if status == FeatureItemStatus.in_progress and item.started_at is None:
            item.started_at = utc_now()
        if status in {FeatureItemStatus.completed, FeatureItemStatus.closed}:
            item.finished_at = utc_now()
        await session.commit()
        await session.refresh(item)
        return item


class TaskRepository:
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
        await session.commit()
        await session.refresh(task)
        return task

    @staticmethod
    async def get(session: AsyncSession, task_id: uuid.UUID) -> TaskRecord | None:
        return await session.get(TaskRecord, task_id)

    @staticmethod
    async def list(
        session: AsyncSession,
        *,
        agent_instance_id: uuid.UUID | None = None,
        status: TaskStatus | None = None,
        category: TaskCategory | None = None,
        repo: str | None = None,
        project: str | None = None,
        limit: int = 200,
    ) -> list[TaskRecord]:
        query = select(TaskRecord)

        if agent_instance_id is not None:
            query = query.where(TaskRecord.agent_instance_id == agent_instance_id)
        if status is not None:
            query = query.where(TaskRecord.status == status)
        if category is not None:
            query = query.where(TaskRecord.category == category)
        if repo is not None:
            query = query.where(TaskRecord.repo == repo)
        if project is not None:
            query = query.where(TaskRecord.project == project)

        query = query.order_by(TaskRecord.created_at.desc()).limit(limit)
        result = await session.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def list_external_pull_request_candidates(
        session: AsyncSession,
        *,
        limit: int = 200,
    ) -> list[TaskRecord]:
        query = (
            select(TaskRecord)
            .where(
                TaskRecord.category == TaskCategory.coding,
                TaskRecord.repo.is_not(None),
                TaskRecord.external_pull_request_url.is_not(None),
                TaskRecord.status.in_(
                    [
                        TaskStatus.queued,
                        TaskStatus.running,
                        TaskStatus.waiting_for_review,
                        TaskStatus.waiting_for_merge,
                    ]
                ),
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
        reviewable_running_task = and_(
            TaskRecord.status == TaskStatus.running,
            select(VirtualPullRequestRecord.id)
            .where(VirtualPullRequestRecord.task_id == TaskRecord.id)
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
                            TaskStatus.waiting_for_merge,
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

        result: CursorResult[Any] = cast(CursorResult[Any], await session.execute(stmt))
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
            result: CursorResult[Any] = cast(CursorResult[Any], await session.execute(stmt))
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
        task = await session.get(TaskRecord, task_id)
        if task is None:
            return None
        if task.status not in {TaskStatus.waiting_for_review, TaskStatus.waiting_for_merge}:
            return None

        now = utc_now()
        task.resume_status = task.status
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
        task = await session.get(TaskRecord, task_id)
        if task is None:
            return None

        task.status = task.resume_status or TaskStatus.waiting_for_review
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
    async def set_waiting_for_merge(
        session: AsyncSession,
        task_id: uuid.UUID,
        *,
        result: str | None,
    ) -> TaskRecord | None:
        task = await session.get(TaskRecord, task_id)
        if task is None:
            return None

        now = utc_now()
        task.status = TaskStatus.waiting_for_merge
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
        query = (
            select(TaskWorkItemRecord)
            .where(TaskWorkItemRecord.task_id == task_id)
            .order_by(TaskWorkItemRecord.order_index.asc())
        )
        result = await session.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def count_by_task(session: AsyncSession, task_id: uuid.UUID) -> int:
        return len(await TaskWorkItemRepository.list_by_task(session, task_id))

    @staticmethod
    async def get(
        session: AsyncSession,
        work_item_id: uuid.UUID,
    ) -> TaskWorkItemRecord | None:
        return await session.get(TaskWorkItemRecord, work_item_id)

    @staticmethod
    async def get_running(
        session: AsyncSession,
        task_id: uuid.UUID,
    ) -> TaskWorkItemRecord | None:
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
        work_item = await session.get(TaskWorkItemRecord, work_item_id)
        if work_item is None:
            return None

        work_item.status = status
        work_item.updated_at = utc_now()
        await session.commit()
        await session.refresh(work_item)
        return work_item


class VirtualPullRequestRepository:
    @staticmethod
    async def list_by_task(
        session: AsyncSession,
        task_id: uuid.UUID,
    ) -> list[VirtualPullRequestRecord]:
        query = (
            select(VirtualPullRequestRecord)
            .where(VirtualPullRequestRecord.task_id == task_id)
            .order_by(VirtualPullRequestRecord.created_at.asc())
        )
        result = await session.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get(
        session: AsyncSession,
        virtual_pr_id: uuid.UUID,
    ) -> VirtualPullRequestRecord | None:
        return await session.get(VirtualPullRequestRecord, virtual_pr_id)

    @staticmethod
    async def get_by_work_item(
        session: AsyncSession,
        work_item_id: uuid.UUID,
    ) -> VirtualPullRequestRecord | None:
        query = select(VirtualPullRequestRecord).where(
            VirtualPullRequestRecord.work_item_id == work_item_id
        )
        result = await session.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def upsert_for_work_item(
        session: AsyncSession,
        *,
        task_id: uuid.UUID,
        work_item_id: uuid.UUID,
        base_commit: str,
        head_commit: str,
        summary: str,
        changed_files: list[str],
        additions: int,
        deletions: int,
        diff: str,
    ) -> VirtualPullRequestRecord:
        virtual_pr = await VirtualPullRequestRepository.get_by_work_item(session, work_item_id)
        if virtual_pr is None:
            virtual_pr = VirtualPullRequestRecord(
                task_id=task_id,
                work_item_id=work_item_id,
                status=VirtualPullRequestStatus.ready_for_review,
                base_commit=base_commit,
                head_commit=head_commit,
                summary=summary,
                changed_files=changed_files,
                additions=additions,
                deletions=deletions,
                diff=diff,
            )
            session.add(virtual_pr)
        else:
            virtual_pr.status = VirtualPullRequestStatus.ready_for_review
            virtual_pr.base_commit = base_commit
            virtual_pr.head_commit = head_commit
            virtual_pr.summary = summary
            virtual_pr.changed_files = changed_files
            virtual_pr.additions = additions
            virtual_pr.deletions = deletions
            virtual_pr.diff = diff
            virtual_pr.updated_at = utc_now()

        await session.commit()
        await session.refresh(virtual_pr)
        return virtual_pr

    @staticmethod
    async def add_review(
        session: AsyncSession,
        *,
        virtual_pr_id: uuid.UUID,
        decision: VirtualPullRequestReviewDecision,
        reviewer: str | None,
        comment: str | None,
    ) -> VirtualPullRequestReviewRecord | None:
        virtual_pr = await session.get(VirtualPullRequestRecord, virtual_pr_id)
        if virtual_pr is None:
            return None

        if decision == VirtualPullRequestReviewDecision.approved:
            virtual_pr.status = VirtualPullRequestStatus.approved
        elif decision == VirtualPullRequestReviewDecision.closed:
            virtual_pr.status = VirtualPullRequestStatus.closed
        elif decision == VirtualPullRequestReviewDecision.reopened:
            virtual_pr.status = VirtualPullRequestStatus.ready_for_review
        virtual_pr.updated_at = utc_now()

        review = VirtualPullRequestReviewRecord(
            task_id=virtual_pr.task_id,
            virtual_pr_id=virtual_pr.id,
            decision=decision,
            reviewer=reviewer,
            comment=comment,
        )
        session.add(review)
        await session.commit()
        await session.refresh(review)
        return review

    @staticmethod
    async def list_reviews_by_virtual_pr(
        session: AsyncSession,
        virtual_pr_id: uuid.UUID,
    ) -> list[VirtualPullRequestReviewRecord]:
        query = (
            select(VirtualPullRequestReviewRecord)
            .where(VirtualPullRequestReviewRecord.virtual_pr_id == virtual_pr_id)
            .order_by(VirtualPullRequestReviewRecord.created_at.asc())
        )
        result = await session.execute(query)
        return list(result.scalars().all())


class VirtualPullRequestThreadRepository:
    @staticmethod
    async def list_by_virtual_pr(
        session: AsyncSession,
        virtual_pr_id: uuid.UUID,
    ) -> list[VirtualPullRequestThreadRecord]:
        query = (
            select(VirtualPullRequestThreadRecord)
            .where(VirtualPullRequestThreadRecord.virtual_pr_id == virtual_pr_id)
            .order_by(VirtualPullRequestThreadRecord.created_at.asc())
        )
        result = await session.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get(
        session: AsyncSession,
        thread_id: uuid.UUID,
    ) -> VirtualPullRequestThreadRecord | None:
        return await session.get(VirtualPullRequestThreadRecord, thread_id)

    @staticmethod
    async def create(
        session: AsyncSession,
        *,
        task_id: uuid.UUID,
        virtual_pr_id: uuid.UUID,
        kind: VirtualPullRequestThreadKind,
        created_by: str | None,
        body: str,
        file_path: str | None = None,
        start_line: int | None = None,
        end_line: int | None = None,
        line_side: VirtualPullRequestLineSide | None = None,
        diff_hunk: str | None = None,
    ) -> tuple[VirtualPullRequestThreadRecord, VirtualPullRequestCommentRecord] | None:
        virtual_pr = await session.get(VirtualPullRequestRecord, virtual_pr_id)
        if virtual_pr is None or virtual_pr.task_id != task_id:
            return None

        thread = VirtualPullRequestThreadRecord(
            task_id=task_id,
            virtual_pr_id=virtual_pr_id,
            kind=kind,
            status=VirtualPullRequestThreadStatus.open,
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            line_side=line_side,
            diff_hunk=diff_hunk,
            code_snapshot=_extract_code_snapshot(
                virtual_pr.diff,
                file_path=file_path,
                start_line=start_line,
                end_line=end_line,
                line_side=line_side,
            ),
            created_by=created_by,
        )
        session.add(thread)
        await session.flush()

        comment = VirtualPullRequestCommentRecord(
            thread_id=thread.id,
            author=created_by,
            body=body,
        )
        session.add(comment)
        await session.commit()
        await session.refresh(thread)
        await session.refresh(comment)
        return thread, comment

    @staticmethod
    async def update_status(
        session: AsyncSession,
        *,
        virtual_pr_id: uuid.UUID,
        thread_id: uuid.UUID,
        status: VirtualPullRequestThreadStatus,
    ) -> VirtualPullRequestThreadRecord | None:
        thread = await session.get(VirtualPullRequestThreadRecord, thread_id)
        if thread is None or thread.virtual_pr_id != virtual_pr_id:
            return None
        thread.status = status
        thread.updated_at = utc_now()
        await session.commit()
        await session.refresh(thread)
        return thread

    @staticmethod
    async def add_comment(
        session: AsyncSession,
        *,
        thread_id: uuid.UUID,
        author: str | None,
        parent_comment_id: uuid.UUID | None = None,
        body: str,
    ) -> VirtualPullRequestCommentRecord | None:
        thread = await session.get(VirtualPullRequestThreadRecord, thread_id)
        if thread is None:
            return None

        if parent_comment_id is not None:
            parent_comment = await session.get(VirtualPullRequestCommentRecord, parent_comment_id)
            if parent_comment is None or parent_comment.thread_id != thread_id:
                return None

        comment = VirtualPullRequestCommentRecord(
            thread_id=thread_id,
            parent_comment_id=parent_comment_id,
            author=author,
            body=body,
        )
        thread.updated_at = utc_now()
        session.add(comment)
        await session.commit()
        await session.refresh(comment)
        return comment


class VirtualPullRequestCommentRepository:
    @staticmethod
    async def list_by_thread_ids(
        session: AsyncSession,
        thread_ids: list[uuid.UUID],
    ) -> list[VirtualPullRequestCommentRecord]:
        if not thread_ids:
            return []

        query = (
            select(VirtualPullRequestCommentRecord)
            .where(VirtualPullRequestCommentRecord.thread_id.in_(thread_ids))
            .order_by(VirtualPullRequestCommentRecord.created_at.asc())
        )
        result = await session.execute(query)
        return list(result.scalars().all())


class GithubPullRequestFeedbackRepository:
    @staticmethod
    async def upsert_discovered(
        session: AsyncSession,
        *,
        task_id: uuid.UUID,
        pull_request_number: int,
        kind: GithubPullRequestFeedbackKind,
        external_id: int,
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
        query = select(GithubPullRequestFeedbackRecord).where(
            GithubPullRequestFeedbackRecord.task_id == task_id,
            GithubPullRequestFeedbackRecord.kind == kind,
            GithubPullRequestFeedbackRecord.external_id == external_id,
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
                external_id=external_id,
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

        if record.status in {
            GithubPullRequestFeedbackStatus.pending,
            GithubPullRequestFeedbackStatus.ignored,
        }:
            record.status = status
            record.ignored_reason = ignored_reason
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
        return await session.get(UserRecord, user_id)

    @staticmethod
    async def get_by_github_id(session: AsyncSession, github_id: str) -> UserRecord | None:
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
        auth_session = AuthSessionRecord(token_hash=token_hash, user_id=user_id, expires_at=expires_at)
        session.add(auth_session)
        await session.commit()
        await session.refresh(auth_session)
        return auth_session

    @staticmethod
    async def get_user_by_token_hash(session: AsyncSession, token_hash: str) -> UserRecord | None:
        result = await session.execute(
            select(UserRecord)
            .join(AuthSessionRecord, AuthSessionRecord.user_id == UserRecord.id)
            .where(AuthSessionRecord.token_hash == token_hash, AuthSessionRecord.expires_at > utc_now())
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def delete(session: AsyncSession, token_hash: str) -> None:
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
        user = await session.get(UserRecord, user_id, with_for_update=True)
        if user is None:
            raise ValueError("User not found")
        if user.balance < price:
            raise ValueError("Insufficient balance")
        user.balance -= price
        user.updated_at = utc_now()
        purchase = AgentPurchaseRecord(
            user_id=user_id,
            agent=agent,
            price=price,
            expires_at=expires_at,
        )
        session.add(purchase)
        await session.commit()
        await session.refresh(purchase)
        return purchase
