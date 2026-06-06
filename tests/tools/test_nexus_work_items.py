from __future__ import annotations

import uuid
import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.server.postgres.models import TaskWorkItemStatus
from src.server.postgres.repositories import (
    TaskRepository,
    TaskWorkItemRepository,
)
from src.tools.nexus import NEXUS_TOOL_DEFINITIONS
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
        user_id=uuid.uuid4(),
        repo="owner/repo",
        project="nexus",
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


def test_nexus_toolkit_exposes_bind_pr_to_task() -> None:
    """Verify bind_pr_to_task is part of Nexus internal tools."""
    tools = NexusReviewTools(AsyncMock(), make_context()).all_tools
    assert "bind_pr_to_task" in tools
    assert any(tool["function"]["name"] == "bind_pr_to_task" for tool in NEXUS_TOOL_DEFINITIONS)


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


def test_bind_pr_to_task_persists_verified_pr(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify bind_pr_to_task checks GitHub then persists the PR URL."""
    context = make_context()
    captured: dict[str, Any] = {}

    async def fake_get_task(session, task_id):
        """Provide a fake task lookup."""
        assert task_id == context.task_id
        return SimpleNamespace(
            id=context.task_id,
            external_pull_request_url=None,
        )

    async def fake_set_external_pull_request_url(session, task_id, *, external_pull_request_url):
        """Provide a fake PR URL persistence call."""
        captured["task_id"] = task_id
        captured["pr_url"] = external_pull_request_url
        return object()

    monkeypatch.setattr(TaskRepository, "get", fake_get_task)
    monkeypatch.setattr(TaskRepository, "set_external_pull_request_url", fake_set_external_pull_request_url)

    mock_response = MagicMock()
    mock_response.json.return_value = {"html_url": "https://github.com/owner/repo/pull/12"}
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        result = asyncio.run(
            NexusReviewTools(AsyncMock(), context).bind_pr_to_task(
                token="test-token",
                pull_request_url="https://github.com/owner/repo/pull/12/files",
            )
        )

    assert result["success"] is True
    assert result["pr_url"] == "https://github.com/owner/repo/pull/12"
    assert captured == {
        "task_id": context.task_id,
        "pr_url": "https://github.com/owner/repo/pull/12",
    }
    assert mock_get.await_count == 1


def test_bind_pr_to_task_rejects_repo_mismatch() -> None:
    """Verify bind_pr_to_task rejects PRs from another repository."""
    context = make_context()

    async def fake_get_task(session, task_id):
        """Provide a fake task lookup."""
        assert task_id == context.task_id
        return SimpleNamespace(
            id=context.task_id,
            external_pull_request_url=None,
        )

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(TaskRepository, "get", fake_get_task)
        result = asyncio.run(
            NexusReviewTools(AsyncMock(), context).bind_pr_to_task(
                token="test-token",
                pull_request_url="https://github.com/other/repo/pull/12",
            )
        )

    assert result["success"] is False
    assert "does not match current task repo" in result["message"]


def test_bind_pr_to_task_rejects_when_task_already_has_pr(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify bind_pr_to_task refuses to rebind a task that already has a PR."""
    context = make_context()
    existing_pr_url = "https://github.com/owner/repo/pull/99"

    async def fake_get_task(session, task_id):
        """Provide a fake task lookup."""
        assert task_id == context.task_id
        return SimpleNamespace(
            id=context.task_id,
            external_pull_request_url=existing_pr_url,
        )

    monkeypatch.setattr(TaskRepository, "get", fake_get_task)

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        result = asyncio.run(
            NexusReviewTools(AsyncMock(), context).bind_pr_to_task(
                token="test-token",
                pull_request_url="https://github.com/owner/repo/pull/12",
            )
        )

    assert result["success"] is False
    assert result["pr_url"] == existing_pr_url
    assert "already bound" in result["message"]
    assert mock_get.await_count == 0


def test_bind_pr_to_task_surfaces_github_api_errors() -> None:
    """Verify bind_pr_to_task reports GitHub lookup failures."""
    context = make_context()

    async def fake_get_task(session, task_id):
        """Provide a fake task lookup."""
        assert task_id == context.task_id
        return SimpleNamespace(
            id=context.task_id,
            external_pull_request_url=None,
        )

    mock_response = MagicMock()
    mock_response.json.return_value = {"message": "Not Found"}
    mock_response.text = "Not Found"
    mock_response.status_code = 404
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Not Found",
        request=MagicMock(),
        response=mock_response,
    )

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(TaskRepository, "get", fake_get_task)
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            result = asyncio.run(
                NexusReviewTools(AsyncMock(), context).bind_pr_to_task(
                    token="test-token",
                    pull_request_url="https://github.com/owner/repo/pull/12",
                )
            )

    assert result["success"] is False
    assert "GitHub API error 404" in result["message"]
