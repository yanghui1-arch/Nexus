from __future__ import annotations

import asyncio
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import httpx
from fastapi import FastAPI

from src.server.api.dependencies import get_current_user
from src.server.api.routes.agent_instances import router as agent_instances_router
from src.server.postgres.models import AgentName, WorkspaceStatus
from src.server.postgres.repositories import AgentInstanceRepository, WorkspaceRepository


class FakeDatabase:
    def __init__(self, session_obj: object | None = None) -> None:
        """Initialize the test helper."""
        self._session_obj = session_obj if session_obj is not None else object()

    @asynccontextmanager
    async def session(self):
        """Return a fake database session."""
        yield self._session_obj


def _build_app(user_id: uuid.UUID, session_obj: object | None = None) -> FastAPI:
    """Build a FastAPI app for route tests."""
    app = FastAPI()
    app.state.database = FakeDatabase(session_obj)
    app.include_router(agent_instances_router)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=user_id)
    return app


def test_update_workspace_persists_frontend_repo_project(monkeypatch) -> None:
    """Verify update workspace persists frontend repo project."""
    user_id = uuid.uuid4()
    instance_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    instance = SimpleNamespace(
        id=instance_id,
        user_id=user_id,
        agent=AgentName.sophie,
        client_id="client-1",
        display_name="Sophie",
        expires_at=now + timedelta(days=30),
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    captured = {}

    async def fake_get(session, agent_instance_id):
        """Provide a fake get."""
        assert agent_instance_id == instance_id
        return instance

    async def fake_ensure(session, agent_instance):
        """Provide a fake ensure."""
        assert agent_instance is instance
        return None

    async def fake_set_context(session, *, agent_instance_id, github_repo, project):
        """Provide a fake set context."""
        captured["agent_instance_id"] = agent_instance_id
        captured["github_repo"] = github_repo
        captured["project"] = project
        return SimpleNamespace(
            id=uuid.uuid4(),
            agent_instance_id=agent_instance_id,
            workspace_key=f"agent-instance:{agent_instance_id}",
            github_repo=github_repo,
            project=project,
            docker_container_id=None,
            docker_volume_name=None,
            status=WorkspaceStatus.idle,
            last_used_at=now,
            created_at=now,
            updated_at=now,
        )

    monkeypatch.setattr(AgentInstanceRepository, "get", fake_get)
    monkeypatch.setattr(WorkspaceRepository, "ensure_for_agent_instance", fake_ensure)
    monkeypatch.setattr(WorkspaceRepository, "set_context", fake_set_context)

    async def run_request() -> httpx.Response:
        """Run the request test body."""
        transport = httpx.ASGITransport(app=_build_app(user_id))
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.patch(
                f"/v1/agent-instances/{instance_id}/workspace",
                json={"github_repo": "owner/repo", "project": "nexus"},
            )

    response = asyncio.run(run_request())

    assert response.status_code == 200
    assert captured == {
        "agent_instance_id": instance_id,
        "github_repo": "owner/repo",
        "project": "nexus",
    }
    payload = response.json()
    assert payload["id"] == str(instance_id)
    assert payload["expires_at"] == instance.expires_at.isoformat()
    assert payload["workspace"]["github_repo"] == "owner/repo"
    assert payload["workspace"]["project"] == "nexus"


def test_update_agent_instance_display_name(monkeypatch) -> None:
    """Verify display name updates through the metadata route."""
    user_id = uuid.uuid4()
    instance_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    instance = SimpleNamespace(
        id=instance_id,
        user_id=user_id,
        agent=AgentName.sophie,
        client_id="client-1",
        display_name="Sophie",
        expires_at=now + timedelta(days=30),
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    workspace = SimpleNamespace(
        id=uuid.uuid4(),
        agent_instance_id=instance_id,
        workspace_key=f"agent-instance:{instance_id}",
        github_repo="owner/repo",
        project="nexus",
        docker_container_id=None,
        docker_volume_name=None,
        status=WorkspaceStatus.idle,
        last_used_at=now,
        created_at=now,
        updated_at=now,
    )
    captured = {}

    async def fake_get(session, agent_instance_id):
        """Provide a fake get."""
        assert agent_instance_id == instance_id
        return instance

    async def fake_set_display_name(session, agent_instance_id, *, display_name):
        """Provide a fake set display name."""
        captured["agent_instance_id"] = agent_instance_id
        captured["display_name"] = display_name
        return SimpleNamespace(**{**instance.__dict__, "display_name": display_name})

    async def fake_workspace(session, agent_instance_id):
        """Provide a fake workspace lookup."""
        assert agent_instance_id == instance_id
        return workspace

    monkeypatch.setattr(AgentInstanceRepository, "get", fake_get)
    monkeypatch.setattr(AgentInstanceRepository, "set_display_name", fake_set_display_name)
    monkeypatch.setattr(WorkspaceRepository, "get_by_agent_instance_id", fake_workspace)

    async def run_request() -> httpx.Response:
        """Run the request test body."""
        transport = httpx.ASGITransport(app=_build_app(user_id))
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.patch(
                f"/v1/agent-instances/{instance_id}",
                json={"display_name": "Primary Sophie"},
            )

    response = asyncio.run(run_request())

    assert response.status_code == 200
    assert captured == {
        "agent_instance_id": instance_id,
        "display_name": "Primary Sophie",
    }
    assert response.json()["display_name"] == "Primary Sophie"
    assert response.json()["expires_at"] == instance.expires_at.isoformat()
