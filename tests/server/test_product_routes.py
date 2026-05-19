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

from src.server.api.routes.product import router as product_router
from src.server.postgres.models import (
    AgentName,
    ProductProposalStatus,
)
from src.server.postgres.repositories import (
    AgentInstanceRepository,
    ProductProposalRepository,
)


class FakeDatabase:
    def __init__(self, session_obj: object | None = None) -> None:
        self._session_obj = session_obj if session_obj is not None else object()

    @asynccontextmanager
    async def session(self):
        yield self._session_obj


def _build_app(session_obj: object | None = None, runner: object | None = None) -> FastAPI:
    app = FastAPI()
    app.state.database = FakeDatabase(session_obj)
    app.state.runner = runner or SimpleNamespace()
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
        "source_task_id": None,
        "created_at": now,
        "updated_at": now,
    }
    values.update(overrides)
    return SimpleNamespace(**values)
def test_approve_proposal_dispatches_planning_task(monkeypatch) -> None:
    proposal_id = uuid.uuid4()
    marc_instance_id = uuid.uuid4()
    approved = _proposal(id=proposal_id, status=ProductProposalStatus.approved)
    captured = {}
    runner = SimpleNamespace(submit_task=AsyncMock(return_value=uuid.uuid4()))

    async def fake_get(session, pid):
        return _proposal(id=pid, status=ProductProposalStatus.proposed)

    async def fake_set_status(session, pid, status):
        captured["proposal_id"] = pid
        captured["status"] = status
        return approved

    async def fake_list_marc(session, *, agent, limit):
        captured["agent"] = agent
        captured["limit"] = limit
        return [SimpleNamespace(id=marc_instance_id)]

    monkeypatch.setattr(ProductProposalRepository, "get", fake_get)
    monkeypatch.setattr(ProductProposalRepository, "set_status", fake_set_status)
    monkeypatch.setattr(AgentInstanceRepository, "list_by_active_task_load", fake_list_marc)

    async def run_request() -> httpx.Response:
        transport = httpx.ASGITransport(app=_build_app(runner=runner))
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
