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

from src.server.postgres.models import AgentName, TaskCategory, TaskStatus
from src.server.postgres.repositories import AgentInstanceRepository, TaskRepository, WorkspaceRepository
from src.server.runner import AgentTaskRunner


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
    request = SimpleNamespace(
        agent_instance_id=agent_instance_id,
        agent=SimpleNamespace(value="sophie"),
        question="implement the change",
        external_issue_url="https://github.com/owner/repo/issues/1",
    )

    task = asyncio.run(runner._create_task_record(object(), request))

    assert task.id is not None
    assert captured["agent"] == AgentName.sophie
    assert captured["agent_instance_id"] == agent_instance_id
    assert captured["category"] == TaskCategory.coding
    assert captured["question"] == "implement the change"
    assert captured["repo"] == "owner/repo"
    assert captured["project"] == "nexus"
    assert captured["external_issue_url"] == "https://github.com/owner/repo/issues/1"


@pytest.mark.parametrize(
    ("agent_name", "github_repo", "project"),
    [
        ("sophie", "owner/repo", None),
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
    request = SimpleNamespace(
        agent_instance_id=agent_instance_id,
        agent=SimpleNamespace(value=agent_name),
        question="implement the change",
        external_issue_url=None,
    )

    with pytest.raises(ValueError, match="workspace repo and project are required for task submission"):
        asyncio.run(runner._create_task_record(object(), request))


def test_retry_failed_task_clones_required_fields(monkeypatch) -> None:
    """Verify failed task retry creates a fresh queued task from the source."""
    source_task_id = uuid.uuid4()
    retry_task_id = uuid.uuid4()
    agent_instance_id = uuid.uuid4()
    source_task = SimpleNamespace(
        id=source_task_id,
        agent=AgentName.tela,
        agent_instance_id=agent_instance_id,
        category=TaskCategory.coding,
        question="fix retry semantics",
        repo="owner/repo",
        project="nexus",
        external_issue_url="https://github.com/owner/repo/issues/9",
        status=TaskStatus.failed,
    )
    retry_task = SimpleNamespace(id=retry_task_id)
    session = SimpleNamespace(
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )

    class FakeDatabase:
        def session(self):
            class Context:
                async def __aenter__(self_inner):
                    return session

                async def __aexit__(self_inner, exc_type, exc, tb):
                    return None

            return Context()

    captured: dict[str, object] = {}

    async def fake_get(session_arg, task_id):
        """Provide the failed source task."""
        assert session_arg is session
        assert task_id == source_task_id
        return source_task

    async def fake_create_pending(session_arg, **kwargs):
        """Capture cloned task fields."""
        assert session_arg is session
        captured.update(kwargs)
        return retry_task

    async def fake_dispatch_existing_task(task_id, **kwargs):
        """Capture dispatch arguments."""
        captured["dispatch_task_id"] = task_id
        captured["dispatch_kwargs"] = kwargs
        return True

    monkeypatch.setattr(TaskRepository, "get", fake_get)
    monkeypatch.setattr(TaskRepository, "create_pending", fake_create_pending)

    runner = AgentTaskRunner(
        settings=SimpleNamespace(),
        database=FakeDatabase(),
    )
    monkeypatch.setattr(runner, "dispatch_existing_task", fake_dispatch_existing_task)

    new_task_id = asyncio.run(runner.retry_failed_task(source_task_id))

    assert new_task_id == retry_task_id
    assert captured == {
        "agent": AgentName.tela,
        "agent_instance_id": agent_instance_id,
        "category": TaskCategory.coding,
        "question": "fix retry semantics",
        "repo": "owner/repo",
        "project": "nexus",
        "external_issue_url": "https://github.com/owner/repo/issues/9",
        "dispatch_task_id": retry_task_id,
        "dispatch_kwargs": {
            "recovered": False,
            "fail_task_on_dispatch_error": True,
        },
    }
    session.commit.assert_awaited_once()
    session.refresh.assert_awaited_once_with(retry_task)
