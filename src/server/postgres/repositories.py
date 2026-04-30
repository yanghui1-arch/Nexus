from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, cast

from openai.types.chat.chat_completion_message_param import ChatCompletionMessageParam
from sqlalchemy import and_, or_, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.server.postgres.models import (
    AgentInstanceRecord,
    AgentName,
    TaskRecord,
    TaskStatus,
    TaskWorkItemRecord,
    TaskWorkItemStatus,
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
        external_issue_url: str | None,
        current_session_ctx: list[dict[str, Any]],
        history_session_ctx: list[dict[str, Any]],
    ) -> TaskRecord:
        task = TaskRecord(
            agent=agent,
            agent_instance_id=agent_instance_id,
            question=question,
            repo=repo,
            project=project,
            external_issue_url=external_issue_url,
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
    async def list_review_queue(
        session: AsyncSession,
        *,
        limit: int = 200,
    ) -> list[TaskRecord]:
        query = (
            select(TaskRecord)
            .where(
                TaskRecord.status.in_(
                    [
                        TaskStatus.waiting_for_review,
                        TaskStatus.waiting_for_merge,
                        TaskStatus.merged,
                        TaskStatus.closed,
                    ]
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
