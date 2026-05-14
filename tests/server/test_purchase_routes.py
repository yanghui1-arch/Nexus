from __future__ import annotations

import asyncio
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import httpx
from fastapi import FastAPI

from src.server.api.routes.purchases import router as purchases_router
from src.server.postgres.models import AgentName
from src.server.postgres.repositories import AgentPurchaseRepository


class FakeDatabase:
    @asynccontextmanager
    async def session(self):
        yield object()


def _build_app() -> FastAPI:
    app = FastAPI()
    app.state.database = FakeDatabase()
    app.include_router(purchases_router)
    return app


def _purchase(**overrides):
    now = datetime.now(timezone.utc)
    values = {
        "id": uuid.uuid4(),
        "client_id": "client-1",
        "agent": AgentName.tela,
        "price_cents": 2999,
        "purchased_at": now,
        "expires_at": now + timedelta(days=30),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_list_current_user_purchases_returns_recent_records(monkeypatch) -> None:
    now = datetime.now(timezone.utc)
    active = _purchase(purchased_at=now, expires_at=now + timedelta(days=1))
    expired = _purchase(
        agent=AgentName.marc,
        price_cents=1999,
        purchased_at=now - timedelta(days=40),
        expires_at=now - timedelta(days=1),
    )
    captured = {}

    async def fake_list_by_client_id(session, *, client_id, limit):
        captured["client_id"] = client_id
        captured["limit"] = limit
        return [active, expired]

    monkeypatch.setattr(AgentPurchaseRepository, "list_by_client_id", fake_list_by_client_id)

    async def run_request() -> httpx.Response:
        transport = httpx.ASGITransport(app=_build_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.get("/v1/me/purchases", params={"client_id": "client-1", "limit": 10})

    response = asyncio.run(run_request())

    assert response.status_code == 200
    assert captured == {"client_id": "client-1", "limit": 10}
    body = response.json()
    assert [item["agent"] for item in body] == ["tela", "marc"]
    assert [item["price_cents"] for item in body] == [2999, 1999]
    assert body[0]["status"] == "active"
    assert body[1]["status"] == "expired"
    assert body[0]["purchased_at"]
    assert body[0]["expires_at"]


def test_list_current_user_purchases_requires_client_id() -> None:
    async def run_request() -> httpx.Response:
        transport = httpx.ASGITransport(app=_build_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.get("/v1/me/purchases")

    response = asyncio.run(run_request())

    assert response.status_code == 422
