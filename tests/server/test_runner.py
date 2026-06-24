from __future__ import annotations

import asyncio
import sys
import types
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


class _FakeCelery:
    def __init__(self, *args, **kwargs) -> None:
        """Initialize the test helper."""
        self.conf: dict[str, object] = {}

    def autodiscover_tasks(self, *args, **kwargs) -> None:
        """Ignore Celery autodiscovery in tests."""
        return None

    def send_task(self, *args, **kwargs) -> None:
        """Ignore broker dispatch in tests."""
        return None


fake_celery_module = types.ModuleType("celery")
fake_celery_module.Celery = _FakeCelery
sys.modules.setdefault("celery", fake_celery_module)

from src.server.postgres.models import AgentName, FeatureItemStatus, TaskCategory, TaskStatus
from src.server.postgres.repositories import (
    AgentInstanceRepository,
    FeatureItemRepository,
    TaskRepository,
    WorkspaceRepository,
)
from src.server.runner import AgentTaskRunner, TaskDispatchError, TaskSubmission


class FakeDatabase:
    def __init__(self) -> None:
        """Initialize the test helper."""
        self._session = object()

    def session(self):
        """Return a fake database session."""
        return self

    async def __aenter__(self):
        """Enter the fake database session."""
        return self._session

    async def __aexit__(self, *args) -> None:
        """Exit the fake database session."""
        return None


def test_create_task_record_snapshots_workspace_repo_project(monkeypatch) -> None:
    """Verify submitted tasks persist the workspace repo/project snapshot."""
    agent_instance_id = uuid.uuid4()
    instance = SimpleNamespace(
        id=agent_instance_id,
        is_active=True,
        agent=AgentName.sophie,
    )
    workspace = SimpleNamespace(
        workspace_key=f"agent-instance:{agent_instance_id}",
        github_repo="owner/repo",
        project="nexus",
    )
    captured: dict[str, object] = {}

    async def fake_get(session, requested_agent_instance_id):
        """Provide a fake agent instance lookup."""
        assert requested_agent_instance_id == agent_instance_id
        return instance

    async def fake_ensure(session, agent_instance):
        """Provide a fake workspace lookup."""
        assert agent_instance is instance
        return workspace

    async def fake_create_pending(session, **kwargs):
        """Capture task creation arguments."""
        captured.update(kwargs)
        return SimpleNamespace(id=uuid.uuid4())

    monkeypatch.setattr(AgentInstanceRepository, "get", fake_get)
    monkeypatch.setattr(WorkspaceRepository, "ensure_for_agent_instance", fake_ensure)
    monkeypatch.setattr(TaskRepository, "create_pending", fake_create_pending)

    runner = AgentTaskRunner(
        settings=SimpleNamespace(),
        database=SimpleNamespace(),
    )
    submission = TaskSubmission(
        agent_instance_id=agent_instance_id,
        agent=AgentName.sophie,
        question="implement the change",
        external_issue_url="https://github.com/owner/repo/issues/1",
    )

    task = asyncio.run(runner._create_task_record(object(), submission))

    assert task.id is not None
    assert captured["agent"] == AgentName.sophie
    assert captured["agent_instance_id"] == agent_instance_id
    assert captured["category"] == TaskCategory.coding
    assert captured["question"] == "implement the change"
    assert captured["repo"] == "owner/repo"
    assert captured["project"] == "nexus"
    assert captured["external_issue_url"] == "https://github.com/owner/repo/issues/1"
    assert captured["external_pull_request_url"] is None


def test_create_task_record_uses_review_category_for_assistant(monkeypatch) -> None:
    """Verify assistant tasks are persisted as review tasks."""
    agent_instance_id = uuid.uuid4()
    instance = SimpleNamespace(
        id=agent_instance_id,
        is_active=True,
        agent=AgentName.assistant,
    )
    workspace = SimpleNamespace(
        workspace_key=f"agent-instance:{agent_instance_id}",
        github_repo="owner/repo",
        project="nexus",
    )
    captured: dict[str, object] = {}

    async def fake_get(session, requested_agent_instance_id):
        assert requested_agent_instance_id == agent_instance_id
        return instance

    async def fake_ensure(session, agent_instance):
        assert agent_instance is instance
        return workspace

    async def fake_create_pending(session, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(id=uuid.uuid4())

    monkeypatch.setattr(AgentInstanceRepository, "get", fake_get)
    monkeypatch.setattr(WorkspaceRepository, "ensure_for_agent_instance", fake_ensure)
    monkeypatch.setattr(TaskRepository, "create_pending", fake_create_pending)

    runner = AgentTaskRunner(
        settings=SimpleNamespace(),
        database=SimpleNamespace(),
    )
    request = SimpleNamespace(
        agent_instance_id=agent_instance_id,
        agent=AgentName.assistant,
        question="review owner/repo#12",
        external_issue_url=None,
        external_pull_request_url="https://github.com/owner/repo/pull/12",
    )

    task = asyncio.run(runner._create_task_record(object(), request))

    assert task.id is not None
    assert captured["agent"] == AgentName.assistant
    assert captured["category"] == TaskCategory.review
    assert captured["external_pull_request_url"] == "https://github.com/owner/repo/pull/12"


@pytest.mark.parametrize(
    ("agent_name", "github_repo", "project"),
    [
        ("sophie", "owner/repo", None),
        ("jules", "owner/repo", None),
        ("marc", None, "nexus"),
    ],
)
def test_create_task_record_requires_workspace_repo_and_project(
    monkeypatch,
    agent_name: str,
    github_repo: str | None,
    project: str | None,
) -> None:
    """Verify every task submission requires both workspace repo and project."""
    agent_instance_id = uuid.uuid4()
    instance = SimpleNamespace(
        id=agent_instance_id,
        is_active=True,
        agent=AgentName(agent_name),
    )
    workspace = SimpleNamespace(
        workspace_key=f"agent-instance:{agent_instance_id}",
        github_repo=github_repo,
        project=project,
    )

    async def fake_get(session, requested_agent_instance_id):
        """Provide a fake agent instance lookup."""
        assert requested_agent_instance_id == agent_instance_id
        return instance

    async def fake_ensure(session, agent_instance):
        """Provide a fake workspace lookup."""
        assert agent_instance is instance
        return workspace

    monkeypatch.setattr(AgentInstanceRepository, "get", fake_get)
    monkeypatch.setattr(WorkspaceRepository, "ensure_for_agent_instance", fake_ensure)

    runner = AgentTaskRunner(
        settings=SimpleNamespace(),
        database=SimpleNamespace(),
    )
    submission = TaskSubmission(
        agent_instance_id=agent_instance_id,
        agent=AgentName(agent_name),
        question="implement the change",
        external_issue_url=None,
    )

    with pytest.raises(ValueError, match="workspace repo and project are required for task submission"):
        asyncio.run(runner._create_task_record(object(), submission))


def test_dispatch_or_fail_marks_task_failed_when_publish_raises(monkeypatch) -> None:
    """Verify broker publish errors do not leave tasks queued."""
    task_id = uuid.uuid4()
    task = SimpleNamespace(id=task_id, status=TaskStatus.queued)
    captured = {}

    async def fake_get(session, requested_task_id):
        """Return a queued task."""
        assert requested_task_id == task_id
        return task

    def fail_send_task(*args, **kwargs):
        """Simulate broker publish failure."""
        raise RuntimeError("broker unavailable")

    monkeypatch.setattr(TaskRepository, "get", fake_get)
    monkeypatch.setattr("src.server.runner.celery_app.send_task", fail_send_task)

    runner = AgentTaskRunner(
        settings=SimpleNamespace(celery_queue="test-queue"),
        database=FakeDatabase(),
    )

    async def fake_mark_dispatch_failed(requested_task_id, *, error):
        """Capture dispatch failure state."""
        captured["task_id"] = requested_task_id
        captured["error"] = error

    runner._mark_dispatch_failed = AsyncMock(side_effect=fake_mark_dispatch_failed)

    with pytest.raises(TaskDispatchError, match="broker unavailable"):
        asyncio.run(runner._dispatch_or_fail(task_id))

    runner._mark_dispatch_failed.assert_awaited_once()
    assert captured["task_id"] == task_id
    assert "broker unavailable" in captured["error"]


def test_mark_dispatch_failed_syncs_coding_feature_item(monkeypatch) -> None:
    """Verify dispatch failure marks linked feature items failed for coding tasks."""
    task_id = uuid.uuid4()
    task = SimpleNamespace(id=task_id, category=TaskCategory.coding, finished_at=object())
    captured = {}

    async def fake_set_failed(session, requested_task_id, *, error):
        """Return the failed coding task."""
        captured["task_failed"] = (requested_task_id, error)
        return task

    async def fake_set_status_by_task_id(session, requested_task_id, *, status, updated_at):
        """Capture linked feature item failure state."""
        captured["feature_item_failed"] = (requested_task_id, status, updated_at)
        return []

    monkeypatch.setattr(TaskRepository, "set_failed", fake_set_failed)
    monkeypatch.setattr(FeatureItemRepository, "set_status_by_task_id", fake_set_status_by_task_id)

    runner = AgentTaskRunner(
        settings=SimpleNamespace(),
        database=FakeDatabase(),
    )

    asyncio.run(runner._mark_dispatch_failed(task_id, error="Dispatch failed: broker unavailable"))

    assert captured == {
        "task_failed": (task_id, "Dispatch failed: broker unavailable"),
        "feature_item_failed": (task_id, FeatureItemStatus.failed, task.finished_at),
    }
