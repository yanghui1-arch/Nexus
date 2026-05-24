from __future__ import annotations

import asyncio
import sys
import types
import uuid
from types import SimpleNamespace

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

from src.server.postgres.models import AgentName, TaskCategory
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
