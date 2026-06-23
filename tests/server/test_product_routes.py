from __future__ import annotations

import asyncio
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI

from src.server.api.dependencies import get_current_user
from src.server.api.routes.product import router as product_router
from src.server.postgres.models import AgentName, ProductProposalStatus
from src.server.runner import TaskDispatchError
from src.server.postgres.repositories import (
    AgentInstanceRepository,
    FeatureItemRepository,
    ProductProposalRepository,
    ProposalPlanningRunRepository,
    TaskRepository,
    WorkspaceRepository,
)


class FakeDatabase:
    def __init__(self, session_obj: object | None = None) -> None:
        """Initialize the test helper."""
        self._session_obj = session_obj if session_obj is not None else SimpleNamespace(
            commit=AsyncMock(),
            get=AsyncMock(return_value=SimpleNamespace(id=uuid.uuid4())),
        )

    @asynccontextmanager
    async def session(self):
        """Return a fake database session."""
        yield self._session_obj


def _build_app(
    session_obj: object | None = None,
    runner: object | None = None,
    user_id: uuid.UUID | None = None,
) -> FastAPI:
    """Build a FastAPI app for route tests."""
    app = FastAPI()
    app.state.database = FakeDatabase(session_obj)
    app.state.runner = runner or SimpleNamespace()
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=user_id or uuid.uuid4())
    app.include_router(product_router)
    return app


def _proposal(**overrides: Any) -> Any:
    """Create a product proposal record."""
    now = datetime.now(timezone.utc)
    values = {
        "id": uuid.uuid4(),
        "title": "Add RAG capability",
        "plan_type": "feature",
        "summary": "Improve answer quality with retrieval.",
        "answer": "Build RAG in small slices.",
        "project": "nexus",
        "repo": "owner/repo",
        "user_id": uuid.uuid4(),
        "status": ProductProposalStatus.proposed,
        "source_task_id": None,
        "latest_planning_task_exists": None,
        "created_at": now,
        "updated_at": now,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _planning_run(**overrides: Any) -> Any:
    """Create a proposal planning run record."""
    now = datetime.now(timezone.utc)
    values = {
        "id": uuid.uuid4(),
        "proposal_id": uuid.uuid4(),
        "task_id": uuid.uuid4(),
        "attempt": 1,
        "status": "queued",
        "error": None,
        "created_at": now,
        "updated_at": now,
        "started_at": None,
        "finished_at": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


async def _fake_user_workspaces(session, *, user_id):
    """Return fake workspaces for the current user."""
    return [SimpleNamespace(github_repo="owner/repo", project="nexus")]


async def _post_retry_planning(app: FastAPI, proposal_id: uuid.UUID) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.post(f"/v1/product/proposals/{proposal_id}/retry-planning")


def test_create_proposal_persists_owner(monkeypatch) -> None:
    """Verify proposal creation persists the authenticated owner id."""
    user_id = uuid.uuid4()
    captured = {}

    async def fake_create(session, **kwargs):
        """Provide a fake create."""
        captured.update(kwargs)
        return _proposal(id=uuid.UUID("00000000-0000-0000-0000-000000000010"), **kwargs)

    monkeypatch.setattr(WorkspaceRepository, "list_for_user", _fake_user_workspaces)
    monkeypatch.setattr(ProductProposalRepository, "create", fake_create)
    monkeypatch.setattr(ProposalPlanningRunRepository, "get_latest_by_proposal", AsyncMock(return_value=None))

    async def run_request() -> httpx.Response:
        """Run the request test body."""
        transport = httpx.ASGITransport(app=_build_app(user_id=user_id))
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.post(
                "/v1/product/proposals",
                json={
                    "title": "Add RAG capability",
                    "plan_type": "feature",
                    "summary": "Improve answer quality with retrieval.",
                    "answer": "Build RAG in small slices.",
                    "project": "nexus",
                    "repo": "owner/repo",
                },
            )

    response = asyncio.run(run_request())

    assert response.status_code == 201
    assert captured["user_id"] == user_id
    assert response.json()["id"] == "00000000-0000-0000-0000-000000000010"


def test_approve_proposal_dispatches_planning_task(monkeypatch) -> None:
    """Verify approve proposal dispatches planning task."""
    proposal_id = uuid.uuid4()
    user_id = uuid.uuid4()
    marc_instance_id = uuid.uuid4()
    planning_task_id = uuid.uuid4()
    approved = _proposal(id=proposal_id, user_id=user_id, status=ProductProposalStatus.approved)
    latest_run = _planning_run(
        proposal_id=proposal_id,
        task_id=planning_task_id,
        status="queued",
    )
    captured = {}
    runner = SimpleNamespace(
        create_task_record=AsyncMock(return_value=SimpleNamespace(id=planning_task_id)),
        dispatch_task=AsyncMock(return_value=True),
    )
    state = {"get_calls": 0}

    async def fake_get(session, pid):
        """Provide a fake get."""
        state["get_calls"] += 1
        if state["get_calls"] == 1:
            return _proposal(id=pid, user_id=user_id, status=ProductProposalStatus.proposed)
        return approved

    async def fake_set_status(session, pid, status):
        """Provide a fake set status."""
        captured["proposal_id"] = pid
        captured["status"] = status
        return approved

    async def fake_list_marc(session, *, agent, user_id=None, github_repo=None, project=None, limit):
        """Provide a fake list marc."""
        captured["agent"] = agent
        captured["user_id"] = user_id
        captured["github_repo"] = github_repo
        captured["project"] = project
        captured["limit"] = limit
        return [SimpleNamespace(id=marc_instance_id)]

    async def fake_create_pending(session, *, proposal_id, task_id):
        """Provide a fake create pending."""
        captured["planning_run_proposal_id"] = proposal_id
        captured["planning_run_task_id"] = task_id
        return latest_run

    async def fake_get_latest_by_proposal(session, proposal_id):
        """Provide a fake get latest by proposal."""
        return latest_run

    monkeypatch.setattr(ProductProposalRepository, "get", fake_get)
    monkeypatch.setattr(ProductProposalRepository, "set_status", fake_set_status)
    monkeypatch.setattr(AgentInstanceRepository, "list_by_active_task_load", fake_list_marc)
    monkeypatch.setattr(ProposalPlanningRunRepository, "create_pending", fake_create_pending)
    monkeypatch.setattr(ProposalPlanningRunRepository, "get_latest_by_proposal", fake_get_latest_by_proposal)
    monkeypatch.setattr(WorkspaceRepository, "list_for_user", _fake_user_workspaces)

    async def run_request() -> httpx.Response:
        """Run the request test body."""
        transport = httpx.ASGITransport(app=_build_app(runner=runner, user_id=user_id))
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.patch(
                f"/v1/product/proposals/{proposal_id}/status",
                json={"status": "approved"},
            )

    response = asyncio.run(run_request())

    assert response.status_code == 200
    assert response.json()["status"] == "approved"
    assert response.json()["latest_planning_task_exists"] is True
    assert captured == {
        "proposal_id": proposal_id,
        "status": ProductProposalStatus.approved,
        "agent": AgentName.marc,
        "user_id": user_id,
        "github_repo": "owner/repo",
        "project": "nexus",
        "limit": 1,
        "planning_run_proposal_id": proposal_id,
        "planning_run_task_id": planning_task_id,
    }
    payload = runner.create_task_record.await_args.args[0]
    assert payload.agent_instance_id == marc_instance_id
    assert payload.agent == AgentName.marc
    assert f"Proposal ID: {proposal_id}" in payload.question
    assert "Title: Add RAG capability" in payload.question
    assert "Summary: Improve answer quality with retrieval." in payload.question
    assert "Answer: Build RAG in small slices." in payload.question
    runner.dispatch_task.assert_awaited_once_with(planning_task_id)
    assert response.json()["latest_planning_run"]["task_id"] == str(planning_task_id)


def test_approve_proposal_marks_source_pm_task_merged(monkeypatch) -> None:
    """Verify approve proposal marks source pm task merged."""
    proposal_id = uuid.uuid4()
    user_id = uuid.uuid4()
    source_task_id = uuid.uuid4()
    planning_task_id = uuid.uuid4()
    approved = _proposal(
        id=proposal_id,
        user_id=user_id,
        status=ProductProposalStatus.approved,
        source_task_id=source_task_id,
    )
    captured = {}
    runner = SimpleNamespace(
        create_task_record=AsyncMock(return_value=SimpleNamespace(id=planning_task_id)),
        dispatch_task=AsyncMock(return_value=True),
    )
    state = {"get_calls": 0}

    async def fake_get(session, pid):
        """Provide a fake get."""
        state["get_calls"] += 1
        if state["get_calls"] == 1:
            return _proposal(id=pid, user_id=user_id, status=ProductProposalStatus.proposed)
        return approved

    async def fake_set_status(session, pid, status):
        """Provide a fake set status."""
        return approved

    async def fake_set_merged(session, task_id):
        """Provide a fake set merged."""
        captured["merged_task_id"] = task_id
        return SimpleNamespace(id=task_id)

    async def fake_list_marc(session, *, agent, user_id=None, github_repo=None, project=None, limit):
        """Provide a fake list marc."""
        return [SimpleNamespace(id=uuid.uuid4())]

    async def fake_create_pending(session, *, proposal_id, task_id):
        """Provide a fake create pending."""
        return _planning_run(proposal_id=proposal_id, task_id=task_id)

    async def fake_get_latest_by_proposal(session, proposal_id):
        """Provide a fake get latest by proposal."""
        return _planning_run(proposal_id=proposal_id, task_id=planning_task_id)

    monkeypatch.setattr(ProductProposalRepository, "get", fake_get)
    monkeypatch.setattr(ProductProposalRepository, "set_status", fake_set_status)
    monkeypatch.setattr(TaskRepository, "set_merged", fake_set_merged)
    monkeypatch.setattr(AgentInstanceRepository, "list_by_active_task_load", fake_list_marc)
    monkeypatch.setattr(ProposalPlanningRunRepository, "create_pending", fake_create_pending)
    monkeypatch.setattr(ProposalPlanningRunRepository, "get_latest_by_proposal", fake_get_latest_by_proposal)
    monkeypatch.setattr(WorkspaceRepository, "list_for_user", _fake_user_workspaces)

    async def run_request() -> httpx.Response:
        """Run the request test body."""
        transport = httpx.ASGITransport(app=_build_app(runner=runner, user_id=user_id))
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.patch(
                f"/v1/product/proposals/{proposal_id}/status",
                json={"status": "approved"},
            )

    response = asyncio.run(run_request())

    assert response.status_code == 200
    assert captured["merged_task_id"] == source_task_id


def test_reject_proposal_marks_source_pm_task_closed(monkeypatch) -> None:
    """Verify reject proposal marks source pm task closed."""
    proposal_id = uuid.uuid4()
    user_id = uuid.uuid4()
    source_task_id = uuid.uuid4()
    rejected = _proposal(
        id=proposal_id,
        user_id=user_id,
        status=ProductProposalStatus.rejected,
        source_task_id=source_task_id,
    )
    captured = {}
    runner = SimpleNamespace()

    async def fake_get(session, pid):
        """Provide a fake get."""
        return _proposal(id=pid, user_id=user_id, status=ProductProposalStatus.proposed)

    async def fake_set_status(session, pid, status):
        """Provide a fake set status."""
        return rejected

    async def fake_set_closed(session, task_id):
        """Provide a fake set closed."""
        captured["closed_task_id"] = task_id
        return SimpleNamespace(id=task_id)

    async def fake_get_latest_by_proposal(session, proposal_id):
        """Provide a fake get latest by proposal."""
        return None

    monkeypatch.setattr(ProductProposalRepository, "get", fake_get)
    monkeypatch.setattr(ProductProposalRepository, "set_status", fake_set_status)
    monkeypatch.setattr(TaskRepository, "set_closed", fake_set_closed)
    monkeypatch.setattr(ProposalPlanningRunRepository, "get_latest_by_proposal", fake_get_latest_by_proposal)
    monkeypatch.setattr(WorkspaceRepository, "list_for_user", _fake_user_workspaces)

    async def run_request() -> httpx.Response:
        """Run the request test body."""
        transport = httpx.ASGITransport(app=_build_app(runner=runner, user_id=user_id))
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.patch(
                f"/v1/product/proposals/{proposal_id}/status",
                json={"status": "rejected"},
            )

    response = asyncio.run(run_request())

    assert response.status_code == 200
    assert captured["closed_task_id"] == source_task_id


def test_list_proposals_filters_current_user(monkeypatch) -> None:
    """Verify list proposals filters current user."""
    user_id = uuid.uuid4()
    captured = {}

    async def fake_list(session, **kwargs):
        """Provide a fake list."""
        captured.update(kwargs)
        return [_proposal(user_id=user_id)]

    monkeypatch.setattr(ProductProposalRepository, "list", fake_list)
    monkeypatch.setattr(ProposalPlanningRunRepository, "get_latest_by_proposal_ids", AsyncMock(return_value={}))

    async def run_request() -> httpx.Response:
        """Run the request test body."""
        transport = httpx.ASGITransport(app=_build_app(user_id=user_id))
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.get("/v1/product/proposals")

    response = asyncio.run(run_request())

    assert response.status_code == 200
    assert captured["user_id"] == user_id


def test_get_proposal_hides_unscoped_record(monkeypatch) -> None:
    """Verify get proposal hides unscoped record."""
    proposal_id = uuid.uuid4()

    async def fake_get(session, pid):
        """Provide a fake get."""
        return _proposal(id=pid, user_id=uuid.uuid4(), repo="owner/repo", project="nexus")

    monkeypatch.setattr(ProductProposalRepository, "get", fake_get)
    monkeypatch.setattr(ProposalPlanningRunRepository, "get_latest_by_proposal", AsyncMock(return_value=None))

    async def run_request() -> httpx.Response:
        """Run the request test body."""
        transport = httpx.ASGITransport(app=_build_app(user_id=uuid.uuid4()))
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.get(f"/v1/product/proposals/{proposal_id}")

    response = asyncio.run(run_request())

    assert response.status_code == 404


@pytest.mark.parametrize(
    ("proposal_status", "owned", "expected_status", "expected_detail"),
    [
        (ProductProposalStatus.proposed, True, 409, "Only approved proposals can retry planning"),
        (ProductProposalStatus.approved, False, 404, "Proposal not found"),
    ],
)
def test_retry_planning_rejects_unrecoverable_proposals(
    monkeypatch, proposal_status, owned, expected_status, expected_detail
) -> None:
    proposal_id = uuid.uuid4()
    user_id = uuid.uuid4()
    owner_id = user_id if owned else uuid.uuid4()

    monkeypatch.setattr(
        ProductProposalRepository,
        "get",
        AsyncMock(return_value=_proposal(id=proposal_id, user_id=owner_id, status=proposal_status)),
    )
    monkeypatch.setattr(WorkspaceRepository, "list_for_user", _fake_user_workspaces)

    response = asyncio.run(_post_retry_planning(_build_app(user_id=user_id), proposal_id))

    assert response.status_code == expected_status
    assert response.json()["detail"] == expected_detail

def test_retry_planning_dispatches_new_task_for_failed_run(monkeypatch) -> None:
    proposal_id = uuid.uuid4()
    user_id = uuid.uuid4()
    marc_instance_id = uuid.uuid4()
    planning_task_id = uuid.uuid4()
    approved = _proposal(id=proposal_id, user_id=user_id, status=ProductProposalStatus.approved)
    latest_run = _planning_run(
        proposal_id=proposal_id,
        task_id=planning_task_id,
        status="queued",
    )
    captured = {}
    runner = SimpleNamespace(
        create_task_record=AsyncMock(return_value=SimpleNamespace(id=planning_task_id)),
        dispatch_task=AsyncMock(return_value=True),
    )
    state = {"get_calls": 0}

    async def fake_get(session, pid):
        state["get_calls"] += 1
        if state["get_calls"] == 1:
            return approved
        return approved

    async def fake_list_marc(session, *, agent, user_id=None, github_repo=None, project=None, limit=1):
        captured["agent"] = agent
        captured["user_id"] = user_id
        captured["github_repo"] = github_repo
        captured["project"] = project
        captured["limit"] = limit
        return [SimpleNamespace(id=marc_instance_id)]

    async def fake_create_pending(session, *, proposal_id, task_id):
        captured["planning_run_proposal_id"] = proposal_id
        captured["planning_run_task_id"] = task_id
        return latest_run

    async def fake_get_latest_by_proposal(session, proposal_id):
        if captured.get("planning_run_task_id") is None:
            return _planning_run(proposal_id=proposal_id, status="failed")
        return latest_run

    monkeypatch.setattr(ProductProposalRepository, "get", fake_get)
    monkeypatch.setattr(AgentInstanceRepository, "list_by_active_task_load", fake_list_marc)
    monkeypatch.setattr(ProposalPlanningRunRepository, "create_pending", fake_create_pending)
    monkeypatch.setattr(ProposalPlanningRunRepository, "get_latest_by_proposal", fake_get_latest_by_proposal)
    monkeypatch.setattr(WorkspaceRepository, "list_for_user", _fake_user_workspaces)

    response = asyncio.run(_post_retry_planning(_build_app(runner=runner, user_id=user_id), proposal_id))

    assert response.status_code == 200
    assert response.json()["latest_planning_run"]["task_id"] == str(planning_task_id)
    payload = runner.create_task_record.await_args.args[0]
    assert payload.agent_instance_id == marc_instance_id
    assert payload.agent == AgentName.marc
    runner.dispatch_task.assert_awaited_once_with(planning_task_id)


def test_retry_planning_rejects_when_planning_is_already_running(monkeypatch) -> None:
    proposal_id = uuid.uuid4()
    user_id = uuid.uuid4()
    approved = _proposal(id=proposal_id, user_id=user_id, status=ProductProposalStatus.approved)

    async def fake_get(session, pid):
        return approved

    async def fake_get_latest_by_proposal(session, proposal_id):
        return _planning_run(proposal_id=proposal_id, status="running")

    monkeypatch.setattr(ProductProposalRepository, "get", fake_get)
    monkeypatch.setattr(ProposalPlanningRunRepository, "get_latest_by_proposal", fake_get_latest_by_proposal)
    monkeypatch.setattr(WorkspaceRepository, "list_for_user", _fake_user_workspaces)

    response = asyncio.run(_post_retry_planning(_build_app(user_id=user_id), proposal_id))

    assert response.status_code == 409
    assert response.json()["detail"] == "Planning is already in progress"


@pytest.mark.parametrize(
    ("run_status", "marc_instances", "expected_detail"),
    [
        ("completed", [SimpleNamespace(id=uuid.uuid4())], "Planning is already completed"),
    ],
)
def test_retry_planning_rejects_non_dispatchable_recovery(
    monkeypatch, run_status, marc_instances, expected_detail
) -> None:
    proposal_id = uuid.uuid4()
    user_id = uuid.uuid4()

    monkeypatch.setattr(
        ProductProposalRepository,
        "get",
        AsyncMock(return_value=_proposal(id=proposal_id, user_id=user_id, status=ProductProposalStatus.approved)),
    )
    monkeypatch.setattr(
        ProposalPlanningRunRepository,
        "get_latest_by_proposal",
        AsyncMock(return_value=_planning_run(proposal_id=proposal_id, status=run_status)),
    )
    monkeypatch.setattr(TaskRepository, "get", AsyncMock(return_value=SimpleNamespace(id=uuid.uuid4())))
    monkeypatch.setattr(AgentInstanceRepository, "list_by_active_task_load", AsyncMock(return_value=marc_instances))
    monkeypatch.setattr(WorkspaceRepository, "list_for_user", _fake_user_workspaces)

    response = asyncio.run(_post_retry_planning(_build_app(user_id=user_id), proposal_id))

    assert response.status_code == 409
    assert response.json()["detail"] == expected_detail


def test_retry_planning_returns_dispatch_failure(monkeypatch) -> None:
    proposal_id = uuid.uuid4()
    user_id = uuid.uuid4()
    planning_task_id = uuid.uuid4()
    runner = SimpleNamespace(
        create_task_record=AsyncMock(return_value=SimpleNamespace(id=planning_task_id)),
        dispatch_task=AsyncMock(side_effect=TaskDispatchError("broker unavailable")),
    )

    monkeypatch.setattr(
        ProductProposalRepository,
        "get",
        AsyncMock(return_value=_proposal(id=proposal_id, user_id=user_id, status=ProductProposalStatus.approved)),
    )
    monkeypatch.setattr(
        ProposalPlanningRunRepository,
        "get_latest_by_proposal",
        AsyncMock(return_value=_planning_run(proposal_id=proposal_id, status="failed")),
    )
    monkeypatch.setattr(TaskRepository, "get", AsyncMock(return_value=SimpleNamespace(id=uuid.uuid4())))
    monkeypatch.setattr(AgentInstanceRepository, "list_by_active_task_load", AsyncMock(return_value=[SimpleNamespace(id=uuid.uuid4())]))
    monkeypatch.setattr(ProposalPlanningRunRepository, "create_pending", AsyncMock())
    monkeypatch.setattr(WorkspaceRepository, "list_for_user", _fake_user_workspaces)

    response = asyncio.run(_post_retry_planning(_build_app(runner=runner, user_id=user_id), proposal_id))

    assert response.status_code == 503
    assert response.json()["detail"] == "broker unavailable"
    runner.dispatch_task.assert_awaited_once_with(planning_task_id)

def test_retry_planning_dispatches_new_task_when_run_record_is_missing(monkeypatch) -> None:
    proposal_id = uuid.uuid4()
    user_id = uuid.uuid4()
    approved = _proposal(id=proposal_id, user_id=user_id, status=ProductProposalStatus.approved)
    planning_task_id = uuid.uuid4()
    runner = SimpleNamespace(
        create_task_record=AsyncMock(return_value=SimpleNamespace(id=planning_task_id)),
        dispatch_task=AsyncMock(return_value=True),
    )

    async def fake_get(session, pid):
        return approved

    async def fake_get_latest_by_proposal(session, proposal_id):
        if proposal_id == approved.id and getattr(fake_get_latest_by_proposal, "called", False):
            return _planning_run(proposal_id=proposal_id, task_id=planning_task_id, status="queued")
        fake_get_latest_by_proposal.called = True
        return None

    async def fake_list_marc(session, *, agent, user_id=None, github_repo=None, project=None, limit=1):
        return [SimpleNamespace(id=uuid.uuid4())]

    async def fake_create_pending(session, *, proposal_id, task_id):
        return _planning_run(proposal_id=proposal_id, task_id=task_id, status="queued")

    monkeypatch.setattr(ProductProposalRepository, "get", fake_get)
    monkeypatch.setattr(ProposalPlanningRunRepository, "get_latest_by_proposal", fake_get_latest_by_proposal)
    monkeypatch.setattr(AgentInstanceRepository, "list_by_active_task_load", fake_list_marc)
    monkeypatch.setattr(ProposalPlanningRunRepository, "create_pending", fake_create_pending)
    monkeypatch.setattr(WorkspaceRepository, "list_for_user", _fake_user_workspaces)

    response = asyncio.run(_post_retry_planning(_build_app(runner=runner, user_id=user_id), proposal_id))

    assert response.status_code == 200
    runner.dispatch_task.assert_awaited_once_with(planning_task_id)


def test_retry_planning_dispatches_new_task_when_planning_task_is_missing(monkeypatch) -> None:
    proposal_id = uuid.uuid4()
    user_id = uuid.uuid4()
    old_task_id = uuid.uuid4()
    new_task_id = uuid.uuid4()
    approved = _proposal(id=proposal_id, user_id=user_id, status=ProductProposalStatus.approved)
    runner = SimpleNamespace(
        create_task_record=AsyncMock(return_value=SimpleNamespace(id=new_task_id)),
        dispatch_task=AsyncMock(return_value=True),
    )
    state = {"latest_calls": 0}

    async def fake_get_proposal(session, pid):
        return approved

    async def fake_get_latest_by_proposal(session, proposal_id):
        state["latest_calls"] += 1
        if state["latest_calls"] == 1:
            return _planning_run(proposal_id=proposal_id, task_id=old_task_id, status="queued")
        return _planning_run(proposal_id=proposal_id, task_id=new_task_id, status="queued")

    async def fake_get_task(session, task_id):
        if task_id == old_task_id:
            return None
        return SimpleNamespace(id=task_id)

    async def fake_list_marc(session, *, agent, user_id=None, github_repo=None, project=None, limit=1):
        return [SimpleNamespace(id=uuid.uuid4())]

    async def fake_create_pending(session, *, proposal_id, task_id):
        return _planning_run(proposal_id=proposal_id, task_id=task_id, status="queued")

    monkeypatch.setattr(ProductProposalRepository, "get", fake_get_proposal)
    monkeypatch.setattr(ProposalPlanningRunRepository, "get_latest_by_proposal", fake_get_latest_by_proposal)
    monkeypatch.setattr(TaskRepository, "get", fake_get_task)
    monkeypatch.setattr(AgentInstanceRepository, "list_by_active_task_load", fake_list_marc)
    monkeypatch.setattr(ProposalPlanningRunRepository, "create_pending", fake_create_pending)
    monkeypatch.setattr(WorkspaceRepository, "list_for_user", _fake_user_workspaces)

    response = asyncio.run(_post_retry_planning(_build_app(runner=runner, user_id=user_id), proposal_id))

    assert response.status_code == 200
    runner.dispatch_task.assert_awaited_once_with(new_task_id)


def _feature_item(**overrides: Any) -> Any:
    """Create a feature item record."""
    now = datetime.now(timezone.utc)
    values = {
        "id": uuid.uuid4(),
        "feature_id": uuid.uuid4(),
        "order_index": 1,
        "title": "Render failed items",
        "description": "Show failed proposal plan items.",
        "status": "failed",
        "task_id": uuid.uuid4(),
        "created_at": now,
        "updated_at": now,
        "started_at": now,
        "finished_at": now,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_retry_feature_item_task_dispatches_new_task(monkeypatch) -> None:
    user_id = uuid.uuid4()
    feature_id = uuid.uuid4()
    feature_item_id = uuid.uuid4()
    old_task_id = uuid.uuid4()
    new_task_id = uuid.uuid4()
    tela_instance_id = uuid.uuid4()
    item = _feature_item(id=feature_item_id, feature_id=feature_id, task_id=old_task_id)
    feature = SimpleNamespace(id=feature_id)
    proposal = _proposal(user_id=user_id, repo="owner/repo", project="nexus")
    captured = {}
    runner = SimpleNamespace(
        create_task_record=AsyncMock(return_value=SimpleNamespace(id=new_task_id)),
        dispatch_task=AsyncMock(return_value=True),
    )

    async def fake_list_agents(session, *, agent, user_id=None, github_repo=None, project=None, limit=1):
        captured["agent"] = agent
        captured["user_id"] = user_id
        captured["github_repo"] = github_repo
        captured["project"] = project
        captured["limit"] = limit
        if agent == AgentName.tela:
            return [SimpleNamespace(id=tela_instance_id)]
        return []

    async def fake_assign_task(session, item_id, *, task_id, require_unassigned=True):
        captured["item_id"] = item_id
        captured["task_id"] = task_id
        captured["require_unassigned"] = require_unassigned
        return _feature_item(
            id=item_id,
            feature_id=feature_id,
            status="in_progress",
            task_id=task_id,
            finished_at=None,
        )

    monkeypatch.setattr(FeatureItemRepository, "get_feature", AsyncMock(return_value=feature))
    monkeypatch.setattr(FeatureItemRepository, "get_proposal", AsyncMock(return_value=proposal))
    monkeypatch.setattr(FeatureItemRepository, "list_by_feature", AsyncMock(return_value=[item]))
    monkeypatch.setattr(AgentInstanceRepository, "list_by_active_task_load", fake_list_agents)
    monkeypatch.setattr(FeatureItemRepository, "assign_task", fake_assign_task)

    async def run_request() -> httpx.Response:
        transport = httpx.ASGITransport(app=_build_app(runner=runner, user_id=user_id))
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.post(
                f"/v1/product/feature-items/{feature_item_id}/retry-task",
                json={"reason": "User requested retry."},
            )

    response = asyncio.run(run_request())

    assert response.status_code == 200
    data = response.json()
    assert data["feature_item"]["status"] == "in_progress"
    assert data["feature_item"]["task_id"] == str(new_task_id)
    assert data["task"] == {
        "task_id": str(new_task_id),
        "agent_instance_id": str(tela_instance_id),
        "category": "coding",
        "status": "queued",
    }
    assert captured["require_unassigned"] is False
    payload = runner.create_task_record.await_args.args[0]
    assert payload.agent_instance_id == tela_instance_id
    assert payload.agent == AgentName.tela
    assert "Implement product feature item: Render failed items" in payload.question
    runner.dispatch_task.assert_awaited_once_with(new_task_id)


def test_retry_feature_item_task_rejects_non_failed_item(monkeypatch) -> None:
    user_id = uuid.uuid4()
    feature_id = uuid.uuid4()
    feature_item_id = uuid.uuid4()
    item = _feature_item(id=feature_item_id, feature_id=feature_id, status="in_progress")

    monkeypatch.setattr(FeatureItemRepository, "get_feature", AsyncMock(return_value=SimpleNamespace(id=feature_id)))
    monkeypatch.setattr(FeatureItemRepository, "get_proposal", AsyncMock(return_value=_proposal(user_id=user_id)))
    monkeypatch.setattr(FeatureItemRepository, "list_by_feature", AsyncMock(return_value=[item]))

    async def run_request() -> httpx.Response:
        transport = httpx.ASGITransport(app=_build_app(user_id=user_id))
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.post(f"/v1/product/feature-items/{feature_item_id}/retry-task", json={})

    response = asyncio.run(run_request())

    assert response.status_code == 409
    assert response.json()["detail"] == "Only failed feature items can be retried"


def test_retry_feature_item_task_rejects_when_no_coding_agent(monkeypatch) -> None:
    user_id = uuid.uuid4()
    feature_id = uuid.uuid4()
    feature_item_id = uuid.uuid4()
    item = _feature_item(id=feature_item_id, feature_id=feature_id)

    monkeypatch.setattr(FeatureItemRepository, "get_feature", AsyncMock(return_value=SimpleNamespace(id=feature_id)))
    monkeypatch.setattr(FeatureItemRepository, "get_proposal", AsyncMock(return_value=_proposal(user_id=user_id)))
    monkeypatch.setattr(FeatureItemRepository, "list_by_feature", AsyncMock(return_value=[item]))
    monkeypatch.setattr(AgentInstanceRepository, "list_by_active_task_load", AsyncMock(return_value=[]))

    async def run_request() -> httpx.Response:
        transport = httpx.ASGITransport(app=_build_app(user_id=user_id))
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.post(f"/v1/product/feature-items/{feature_item_id}/retry-task", json={})

    response = asyncio.run(run_request())

    assert response.status_code == 409
    assert response.json()["detail"] == "No active coding agent instance is available"
