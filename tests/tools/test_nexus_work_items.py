from __future__ import annotations

import uuid
import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from src.server.postgres.models import TaskWorkItemStatus
from src.server.postgres.repositories import (
    TaskWorkItemRepository,
)
from src.tools.nexus.client import NexusReviewTools, NexusTaskContext


class FakeDatabase:
    @asynccontextmanager
    async def session(self):
        """Return a fake database session."""
        yield object()


def make_context(*, current_work_item_id: uuid.UUID | None = None) -> NexusTaskContext:
    """Create a Nexus task context."""
    return NexusTaskContext(
        task_id=uuid.uuid4(),
        database=FakeDatabase(),
        repo="owner/repo",
        current_work_item_id=current_work_item_id,
    )


def test_create_task_work_items_uses_hidden_task_context(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify create task work items uses hidden task context."""
    context = make_context()
    captured: dict[str, Any] = {}

    async def fake_create_many(session, *, task_id, items):
        """Provide a fake create many."""
        captured["task_id"] = task_id
        captured["items"] = items
        return [
            SimpleNamespace(
                order_index=1,
                title="First",
                description="Do the first scoped change.",
                status=TaskWorkItemStatus.pending,
            )
        ]

    monkeypatch.setattr(TaskWorkItemRepository, "create_many", fake_create_many)

    result = asyncio.run(
        NexusReviewTools(AsyncMock(), context).create_task_work_items(
            [{"title": "First", "description": "Do the first scoped change."}]
        )
    )

    assert result["success"] is True
    assert captured == {
        "task_id": context.task_id,
        "items": [{"title": "First", "description": "Do the first scoped change."}],
    }


def test_finish_current_task_work_item_infers_base_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify finish current task work item infers base commit."""
    work_item_id = uuid.uuid4()
    context = make_context(current_work_item_id=work_item_id)
    sandbox = AsyncMock()

    async def fake_run_shell(cmd: str) -> dict[str, Any]:
        """Provide a fake run shell."""
        if "status --porcelain" in cmd:
            return {"success": True, "stdout": "", "stderr": ""}
        if "rev-parse HEAD" in cmd:
            return {"success": True, "stdout": "head123\n", "stderr": ""}
        if "merge-base" in cmd:
            return {"success": True, "stdout": "base123\n", "stderr": ""}
        if "--numstat" in cmd:
            return {"success": True, "stdout": "", "stderr": ""}
        return {"success": True, "stdout": "", "stderr": ""}

    sandbox.run_shell = fake_run_shell
    captured: dict[str, Any] = {}

    async def fake_get(session, requested_id):
        """Provide a fake get."""
        assert requested_id == work_item_id
        return SimpleNamespace(
            id=work_item_id,
            task_id=context.task_id,
            status=TaskWorkItemStatus.running,
            base_commit=None,
            order_index=1,
            local_path="/workspace/repo",
        )

    async def fake_mark_ready(session, requested_id, *, summary, base_commit, head_commit, local_path):
        """Provide a fake mark ready."""
        captured["ready"] = {
            "work_item_id": requested_id,
            "summary": summary,
            "base_commit": base_commit,
            "head_commit": head_commit,
            "local_path": local_path,
        }
        return None

    monkeypatch.setattr(TaskWorkItemRepository, "get", fake_get)
    monkeypatch.setattr(TaskWorkItemRepository, "mark_ready_for_review", fake_mark_ready)

    result = asyncio.run(
        NexusReviewTools(sandbox, context).finish_current_task_work_item(
            summary="Finished scoped change.",
        )
    )

    assert result["success"] is True
    assert captured["ready"]["base_commit"] == "base123"
    assert captured["ready"]["head_commit"] == "head123"

def test_finish_current_task_work_item_marks_ready_for_review(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify finish current task work item marks ready for review."""
    work_item_id = uuid.uuid4()
    context = make_context(current_work_item_id=work_item_id)
    sandbox = AsyncMock()

    async def fake_run_shell(cmd: str) -> dict[str, Any]:
        """Provide a fake run shell."""
        if "status --porcelain" in cmd:
            return {"success": True, "stdout": "", "stderr": ""}
        if "rev-parse" in cmd:
            return {"success": True, "stdout": "head123\n", "stderr": ""}
        return {"success": True, "stdout": "", "stderr": ""}

    sandbox.run_shell = fake_run_shell
    captured: dict[str, Any] = {}

    async def fake_get(session, requested_id):
        """Provide a fake get."""
        assert requested_id == work_item_id
        return SimpleNamespace(
            id=work_item_id,
            task_id=context.task_id,
            order_index=1,
            status=TaskWorkItemStatus.running,
            base_commit="base123",
            local_path="/workspace/repo",
        )

    async def fake_mark_ready(session, requested_id, *, summary, base_commit, head_commit, local_path):
        """Provide a fake mark ready."""
        captured["ready"] = {
            "work_item_id": requested_id,
            "summary": summary,
            "base_commit": base_commit,
            "head_commit": head_commit,
            "local_path": local_path,
        }
        return None

    monkeypatch.setattr(TaskWorkItemRepository, "get", fake_get)
    monkeypatch.setattr(TaskWorkItemRepository, "mark_ready_for_review", fake_mark_ready)

    result = asyncio.run(
        NexusReviewTools(sandbox, context).finish_current_task_work_item(
            summary="Finished scoped change.",
        )
    )

    assert result["success"] is True
    assert captured["ready"]["summary"] == "Finished scoped change."
    assert captured["ready"]["base_commit"] == "base123"
    assert captured["ready"]["head_commit"] == "head123"
    assert captured["ready"]["local_path"] == "/workspace/repo"
