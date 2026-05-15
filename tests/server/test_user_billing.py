from __future__ import annotations

import hashlib
import uuid
from decimal import Decimal
from datetime import timedelta
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI

from src.server.api.routes.auth import get_current_user, router as auth_router
from src.server.postgres.models import AgentName
from src.server.postgres.repositories import (
    AgentPurchaseRepository,
    AuthSessionRepository,
    UserRepository,
    utc_now,
)

AGENT_PRICES = {"tela": Decimal("5500.00"), "sophie": Decimal("6000.00")}


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@pytest.mark.asyncio
async def test_session_lookup_recharge_and_purchase(db_session):
    user = await UserRepository.upsert_github_user(
        db_session,
        github_id="123",
        github_login="octocat",
        email="octo@example.com",
    )
    token_hash = _hash_token("session-token")
    await AuthSessionRepository.create(
        db_session,
        token_hash=token_hash,
        user_id=user.id,
        expires_at=utc_now() + timedelta(days=1),
    )

    session_user = await AuthSessionRepository.get_user_by_token_hash(db_session, token_hash)
    assert session_user is not None
    assert session_user.github_login == "octocat"

    recharged = await UserRepository.add_balance(db_session, user.id, Decimal("6000.00"))
    assert recharged is not None
    assert recharged.balance == Decimal("6000.00")

    purchase = await AgentPurchaseRepository.create_purchase(
        db_session,
        user_id=user.id,
        agent=AgentName.tela,
        price=AGENT_PRICES["tela"],
        expires_at=utc_now() + timedelta(days=30),
    )
    assert purchase.price == Decimal("5500.00")
    updated = await UserRepository.get(db_session, user.id)
    assert updated is not None
    assert updated.balance == Decimal("500.00")


@pytest.mark.asyncio
async def test_purchase_rejects_insufficient_balance(db_session):
    user = await UserRepository.upsert_github_user(
        db_session,
        github_id="456",
        github_login="low-balance",
        email=None,
    )

    with pytest.raises(ValueError, match="Insufficient balance"):
        await AgentPurchaseRepository.create_purchase(
            db_session,
            user_id=user.id,
            agent=AgentName.sophie,
            price=AGENT_PRICES["sophie"],
            expires_at=utc_now() + timedelta(days=30),
        )


class _AsyncSessionContext:
    async def __aenter__(self):
        return SimpleNamespace()

    async def __aexit__(self, exc_type, exc, tb):
        return None


class _FakeDatabase:
    def session(self):
        return _AsyncSessionContext()


@pytest.mark.asyncio
async def test_purchase_route_hides_repository_error(monkeypatch):
    app = FastAPI()
    app.include_router(auth_router)
    app.state.database = _FakeDatabase()
    user = SimpleNamespace(id=uuid.uuid4(), balance=0)

    app.dependency_overrides[get_current_user] = lambda: user

    async def fake_create_purchase(*args, **kwargs):
        raise ValueError("Insufficient balance")

    monkeypatch.setattr(AgentPurchaseRepository, "create_purchase", fake_create_purchase)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/v1/billing/purchases", json={"agent": "tela"})

    assert response.status_code == 400
    assert response.json() == {"detail": "Purchase failed"}

    app.dependency_overrides.clear()
