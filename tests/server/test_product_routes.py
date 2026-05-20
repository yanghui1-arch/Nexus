from __future__ import annotations

import asyncio
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import httpx
from fastapi import FastAPI

from src.server.api.dependencies import get_current_user
from src.server.api.routes.product import router as product_router
from src.server.postgres.models import AgentName, ProductProposalStatus
from src.server.postgres.repositories import AgentInstanceRepository, ProductProposalRepository, TaskRepository


class FakeDatabase:
    def __init__(self, session_obj: object | None = None) -> None:
        self._session_obj = session_obj if session_obj is not None else object()

    @asynccontextmanager
    async def session(self):
        yield self._session_obj


def _build_app(
    session_obj: object | None = None,
    runner: object | None = None,
    user_id: uuid.UUID | None = None,
) -> FastAPI:
    app = FastAPI()
    app.state.database = FakeDatabase(session_obj)
    app.state.runner = runner or SimpleNamespace()
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=user_id or uuid.uuid4())
    app.include_router(product_router)
    return app


def _proposal(**overrides: Any) -> Any:
    now = datetime.now(timezone.utc)
    values = {
        "id": uuid.uuid4(),
        "title": "Add RAG capability",
        "plan_type": "feature",
        "summary": "Improve answer quality with retrieval.",
        "answer": "Build RAG in small slices.",
        "project": "nexus",
        "repo": "owner/repo",
        "status": ProductProposalStatus.proposed,
        "user_id": uuid.uuid4(),
        "source_task_id": None,
        "created_at": now,
        "updated_at": now,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_approve_proposal_dispatches_planning_task(monkeypatch) -> None:
    proposal_id = uuid.uuid4()
    user_id = uuid.uuid4()
    marc_instance_id = uuid.uuid4()
    approved = _proposal(id=proposal_id, user_id=user_id, status=ProductProposalStatus.approved)
    captured = {}
    runner = SimpleNamespace(submit_task=AsyncMock(return_value=uuid.uuid4()))

    async def fake_get(session, pid):
        return _proposal(id=pid, user_id=user_id, status=ProductProposalStatus.proposed)

    async def fake_set_status(session, pid, status):
        captured["proposal_id"] = pid
        captured["status"] = status
        return approved

    async def fake_list_marc(session, *, agent, user_id, limit):
        captured["agent"] = agent
        captured["user_id"] = user_id
        captured["limit"] = limit
        return [SimpleNamespace(id=marc_instance_id)]

    monkeypatch.setattr(ProductProposalRepository, "get", fake_get)
    monkeypatch.setattr(ProductProposalRepository, "set_status", fake_set_status)
    monkeypatch.setattr(AgentInstanceRepository, "list_by_active_task_load", fake_list_marc)

    async def run_request() -> httpx.Response:
        transport = httpx.ASGITransport(app=_build_app(runner=runner, user_id=user_id))
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.patch(
                f"/v1/product/proposals/{proposal_id}/status",
                json={"status": "approved"},
            )

    response = asyncio.run(run_request())

    assert response.status_code == 200
    assert response.json()["status"] == "approved"
    assert captured == {
        "proposal_id": proposal_id,
        "status": ProductProposalStatus.approved,
        "agent": AgentName.marc,
        "user_id": user_id,
        "limit": 1,
    }
    payload = runner.submit_task.await_args.args[0]
    assert payload.agent_instance_id == marc_instance_id
    assert payload.agent.value == "marc"
    assert f"Proposal ID: {proposal_id}" in payload.question
    assert "Title: Add RAG capability" in payload.question
    assert "Summary: Improve answer quality with retrieval." in payload.question
    assert "Answer: Build RAG in small slices." in payload.question
    assert payload.repo == "owner/repo"
    assert payload.project == "nexus"


def test_approve_proposal_marks_source_pm_task_merged(monkeypatch) -> None:
    proposal_id = uuid.uuid4()
    user_id = uuid.uuid4()
    source_task_id = uuid.uuid4()
    approved = _proposal(
        id=proposal_id,
        user_id=user_id,
        status=ProductProposalStatus.approved,
        source_task_id=source_task_id,
    )
    captured = {}
    runner = SimpleNamespace(submit_task=AsyncMock(return_value=uuid.uuid4()))

    async def fake_get(session, pid):
        return _proposal(id=pid, user_id=user_id, status=ProductProposalStatus.proposed)

    async def fake_set_status(session, pid, status):
        return approved

    async def fake_set_merged(session, task_id):
        captured["merged_task_id"] = task_id
        return SimpleNamespace(id=task_id)

    async def fake_list_marc(session, *, agent, user_id, limit):
        return [SimpleNamespace(id=uuid.uuid4())]

    monkeypatch.setattr(ProductProposalRepository, "get", fake_get)
    monkeypatch.setattr(ProductProposalRepository, "set_status", fake_set_status)
    monkeypatch.setattr(TaskRepository, "set_merged", fake_set_merged)
    monkeypatch.setattr(AgentInstanceRepository, "list_by_active_task_load", fake_list_marc)

    async def run_request() -> httpx.Response:
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
    runner = SimpleNamespace(submit_task=AsyncMock(return_value=uuid.uuid4()))

    async def fake_get(session, pid):
        return _proposal(id=pid, user_id=user_id, status=ProductProposalStatus.proposed)

    async def fake_set_status(session, pid, status):
        return rejected

    async def fake_set_closed(session, task_id):
        captured["closed_task_id"] = task_id
        return SimpleNamespace(id=task_id)

    monkeypatch.setattr(ProductProposalRepository, "get", fake_get)
    monkeypatch.setattr(ProductProposalRepository, "set_status", fake_set_status)
    monkeypatch.setattr(TaskRepository, "set_closed", fake_set_closed)

    async def run_request() -> httpx.Response:
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
    user_id = uuid.uuid4()
    captured = {}

    async def fake_list(session, **kwargs):
        captured.update(kwargs)
        return [_proposal(user_id=user_id)]

    monkeypatch.setattr(ProductProposalRepository, "list", fake_list)

    async def run_request() -> httpx.Response:
        transport = httpx.ASGITransport(app=_build_app(user_id=user_id))
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.get("/v1/product/proposals")

    response = asyncio.run(run_request())

    assert response.status_code == 200
    assert captured["user_id"] == user_id


def test_get_proposal_hides_other_user_record(monkeypatch) -> None:
    proposal_id = uuid.uuid4()

    async def fake_get(session, pid):
        return _proposal(id=pid, user_id=uuid.uuid4())

    monkeypatch.setattr(ProductProposalRepository, "get", fake_get)

    async def run_request() -> httpx.Response:
        transport = httpx.ASGITransport(app=_build_app(user_id=uuid.uuid4()))
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.get(f"/v1/product/proposals/{proposal_id}")

    response = asyncio.run(run_request())

    assert response.status_code == 404
