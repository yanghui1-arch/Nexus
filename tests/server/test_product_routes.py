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
    FeatureItemStatus,
    FeatureStatus,
)
from src.server.postgres.repositories import (
    AgentInstanceRepository,
    ProductProposalRepository,
    FeatureItemRepository,
    FeatureRepository,
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


def _feature(**overrides: Any) -> Any:
    now = datetime.now(timezone.utc)
    values = {
        "id": uuid.uuid4(),
        "proposal_id": uuid.uuid4(),
        "title": "RAG",
        "description": "Add RAG capability.",
        "project": "nexus",
        "status": FeatureStatus.planned,
        "created_at": now,
        "updated_at": now,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _feature_item(feature_id: uuid.UUID, order_index: int, title: str) -> Any:
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=uuid.uuid4(),
        feature_id=feature_id,
        order_index=order_index,
        title=title,
        description=f"Implement {title}.",
        status=FeatureItemStatus.pending,
        task_id=None,
        created_at=now,
        updated_at=now,
        started_at=None,
        finished_at=None,
    )


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


def test_create_feature_requires_approved_proposal(monkeypatch) -> None:
    proposal_id = uuid.uuid4()

    async def fake_get(session, pid):
        return _proposal(id=pid, status=ProductProposalStatus.proposed)

    monkeypatch.setattr(ProductProposalRepository, "get", fake_get)

    async def run_request() -> httpx.Response:
        transport = httpx.ASGITransport(app=_build_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.post(
                "/v1/product/features",
                json={
                    "proposal_id": str(proposal_id),
                    "title": "RAG",
                    "description": "Add RAG capability.",
                    "project": "nexus",
                    "items": [{"title": "Knowledge base", "description": "Build knowledge base."}],
                },
            )

    response = asyncio.run(run_request())

    assert response.status_code == 409
    assert response.json()["detail"] == "Only approved proposals can become features"


def test_create_feature_from_approved_proposal(monkeypatch) -> None:
    proposal_id = uuid.uuid4()
    feature = _feature(proposal_id=proposal_id)
    items = [
        _feature_item(feature.id, 1, "Knowledge base"),
        _feature_item(feature.id, 2, "Embedding pipeline"),
    ]
    captured = {}

    async def fake_get(session, pid):
        return _proposal(id=pid, status=ProductProposalStatus.approved)

    async def fake_create_with_items(session, **kwargs):
        captured.update(kwargs)
        return feature, items

    monkeypatch.setattr(ProductProposalRepository, "get", fake_get)
    monkeypatch.setattr(FeatureRepository, "create_with_items", fake_create_with_items)

    async def run_request() -> httpx.Response:
        transport = httpx.ASGITransport(app=_build_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.post(
                "/v1/product/features",
                json={
                    "proposal_id": str(proposal_id),
                    "title": "RAG",
                    "description": "Add RAG capability.",
                    "project": "nexus",
                    "items": [
                        {"title": "Knowledge base", "description": "Build knowledge base."},
                        {"title": "Embedding pipeline", "description": "Build embedding pipeline."},
                    ],
                },
            )

    response = asyncio.run(run_request())

    assert response.status_code == 201
    payload = response.json()
    assert payload["proposal_id"] == str(proposal_id)
    assert [item["title"] for item in payload["items"]] == ["Knowledge base", "Embedding pipeline"]
    assert captured["proposal_id"] == proposal_id
    assert captured["items"] == [
        {"title": "Knowledge base", "description": "Build knowledge base."},
        {"title": "Embedding pipeline", "description": "Build embedding pipeline."},
    ]


def test_update_feature_item_status(monkeypatch) -> None:
    feature_id = uuid.uuid4()
    item_id = uuid.uuid4()
    updated = _feature_item(feature_id, 1, "Knowledge base")
    updated.id = item_id
    updated.status = FeatureItemStatus.in_progress
    captured = {}

    async def fake_set_status(session, iid, status):
        captured["item_id"] = iid
        captured["status"] = status
        return updated

    monkeypatch.setattr(FeatureItemRepository, "set_status", fake_set_status)

    async def run_request() -> httpx.Response:
        transport = httpx.ASGITransport(app=_build_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.patch(
                f"/v1/product/feature-items/{item_id}/status",
                json={"status": "in_progress"},
            )

    response = asyncio.run(run_request())

    assert response.status_code == 200
    assert response.json()["status"] == "in_progress"
    assert captured == {"item_id": item_id, "status": FeatureItemStatus.in_progress}
