from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, cast

from sqlalchemy import and_, or_, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.server.postgres.models import (
    AgentInstanceRecord,
    AgentName,
    TaskRecord,
    TaskStatus,
    WorkspaceRecord,
    WorkspaceStatus,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)



class AgentInstanceRepository:
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
    ) -> WorkspaceRecord | None:
        return await WorkspaceRepository._set_state(
            session,
            agent_instance_id=agent_instance_id,
            status=WorkspaceStatus.running,
            github_repo=github_repo,
        )

    @staticmethod
    async def set_idle(
        session: AsyncSession,
        *,
        agent_instance_id: uuid.UUID,
    ) -> WorkspaceRecord | None:
        return await WorkspaceRepository._set_state(
            session,
            agent_instance_id=agent_instance_id,
            status=WorkspaceStatus.idle,
            github_repo=None,
        )

    @staticmethod
    async def set_inactive(
        session: AsyncSession,
        *,
        agent_instance_id: uuid.UUID,
    ) -> WorkspaceRecord | None:
        return await WorkspaceRepository._set_state(
            session,
            agent_instance_id=agent_instance_id,
            status=WorkspaceStatus.inactive,
            github_repo=None,
        )
    
    @staticmethod
    async def _set_state(
        session: AsyncSession,
        *,
        agent_instance_id: uuid.UUID,
        status: WorkspaceStatus,
        github_repo: str | None,
    ) -> WorkspaceRecord | None:
        workspace = await WorkspaceRepository.get_by_agent_instance_id(session, agent_instance_id)
        if workspace is None:
            return None

        now = utc_now()
        workspace.status = status
        workspace.github_repo = github_repo
        workspace.last_used_at = now
        workspace.updated_at = now
        await session.commit()
        await session.refresh(workspace)
        return workspace


class TaskRepository:
    @staticmethod
    async def create(
        session: AsyncSession,
        *,
        agent: AgentName,
        agent_instance_id: uuid.UUID,
        question: str,
        repo: str | None,
        project: str | None,
        current_session_ctx: list[dict[str, Any]],
        history_session_ctx: list[dict[str, Any]],
    ) -> TaskRecord:
        task = TaskRecord(
            agent=agent,
            agent_instance_id=agent_instance_id,
            question=question,
            repo=repo,
            project=project,
            requested_current_session_ctx=list(current_session_ctx),
            requested_history_session_ctx=list(history_session_ctx),
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
        repo: str | None = None,
        project: str | None = None,
        limit: int = 200,
    ) -> list[TaskRecord]:
        query = select(TaskRecord)

        if agent_instance_id is not None:
            query = query.where(TaskRecord.agent_instance_id == agent_instance_id)
        if status is not None:
            query = query.where(TaskRecord.status == status)
        if repo is not None:
            query = query.where(TaskRecord.repo == repo)
        if project is not None:
            query = query.where(TaskRecord.project == project)

        query = query.order_by(TaskRecord.created_at.desc()).limit(limit)
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
        checkpoint: list[Any] | None,
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
        task.updated_at = now
        task.dispatch_token = None
        task.lease_expires_at = None
        await session.commit()
        await session.refresh(task)
        return task
