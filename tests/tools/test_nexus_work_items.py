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
    VirtualPullRequestRepository,
)
from src.tools.nexus.context import NexusTaskContext
from src.tools.nexus.git import parse_numstat
from src.tools.nexus.work_items import NexusReviewTools


class FakeDatabase:
    @asynccontextmanager
    async def session(self):
        yield object()


def make_context(*, current_work_item_id: uuid.UUID | None = None) -> NexusTaskContext:
    return NexusTaskContext(
        task_id=uuid.uuid4(),
        database=FakeDatabase(),
        repo="owner/repo",
        current_work_item_id=current_work_item_id,
    )


def test_parse_numstat_sums_text_changes_and_keeps_binary_files() -> None:
    changed_files, additions, deletions = parse_numstat("2\t1\tsrc/a.py\n-\t-\tassets/logo.png\n")

    assert changed_files == ["src/a.py", "assets/logo.png"]
    assert additions == 2
    assert deletions == 1


def test_create_task_work_items_uses_hidden_task_context(monkeypatch: pytest.MonkeyPatch) -> None:
    context = make_context()
    captured: dict[str, Any] = {}

    async def fake_create_many(session, *, task_id, items):
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


def test_finish_current_task_work_item_requires_base_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    work_item_id = uuid.uuid4()
    context = make_context(current_work_item_id=work_item_id)

    async def fake_get(session, requested_id):
        assert requested_id == work_item_id
        return SimpleNamespace(
            id=work_item_id,
            task_id=context.task_id,
            status=TaskWorkItemStatus.running,
            base_commit=None,
            local_path="/workspace/repo",
        )

    monkeypatch.setattr(TaskWorkItemRepository, "get", fake_get)

    result = asyncio.run(
        NexusReviewTools(AsyncMock(), context).finish_current_task_work_item(
            summary="Finished scoped change.",
        )
    )

    assert result["success"] is False
    assert "Missing base_commit" in result["message"]


def test_finish_current_task_work_item_captures_diff_stats(monkeypatch: pytest.MonkeyPatch) -> None:
    work_item_id = uuid.uuid4()
    context = make_context(current_work_item_id=work_item_id)
    sandbox = AsyncMock()

    async def fake_run_shell(cmd: str) -> dict[str, Any]:
        if "status --porcelain" in cmd:
            return {"success": True, "stdout": "", "stderr": ""}
        if "rev-parse" in cmd:
            return {"success": True, "stdout": "head123\n", "stderr": ""}
        if "--numstat" in cmd:
            return {"success": True, "stdout": "2\t1\tsrc/a.py\n3\t0\tsrc/b.py\n", "stderr": ""}
        return {"success": True, "stdout": "diff --git a/src/a.py b/src/a.py\n", "stderr": ""}

    sandbox.run_shell = fake_run_shell
    captured: dict[str, Any] = {}

    async def fake_get(session, requested_id):
        assert requested_id == work_item_id
        return SimpleNamespace(
            id=work_item_id,
            task_id=context.task_id,
            order_index=1,
            status=TaskWorkItemStatus.running,
            base_commit="base123",
            local_path="/workspace/repo",
        )

    async def fake_upsert(session, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(id=uuid.uuid4())

    async def fake_mark_ready(session, requested_id, *, summary, head_commit):
        captured["ready"] = {
            "work_item_id": requested_id,
            "summary": summary,
            "head_commit": head_commit,
        }
        return None

    monkeypatch.setattr(TaskWorkItemRepository, "get", fake_get)
    monkeypatch.setattr(VirtualPullRequestRepository, "upsert_for_work_item", fake_upsert)
    monkeypatch.setattr(TaskWorkItemRepository, "mark_ready_for_review", fake_mark_ready)

    result = asyncio.run(
        NexusReviewTools(sandbox, context).finish_current_task_work_item(
            summary="Finished scoped change.",
        )
    )

    assert result["success"] is True
    assert captured["base_commit"] == "base123"
    assert captured["head_commit"] == "head123"
    assert captured["changed_files"] == ["src/a.py", "src/b.py"]
    assert captured["additions"] == 5
    assert captured["deletions"] == 1
    assert captured["ready"]["summary"] == "Finished scoped change."
