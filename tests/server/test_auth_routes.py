from __future__ import annotations

import asyncio
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import httpx
from fastapi import FastAPI

import src.server.api.auth as auth_module
import src.server.api.routes.auth as auth_routes
from src.server.api.routes.auth import auth_router, users_router
from src.server.postgres.models import AgentName
from src.server.postgres.repositories import UserAgentSubscriptionRepository, UserRepository, UserSessionRepository


class FakeSession:
    async def commit(self) -> None:
        return None

    async def refresh(self, item: Any) -> None:
        return None


class FakeDatabase:
    @asynccontextmanager
    async def session(self):
        yield FakeSession()


def build_app() -> FastAPI:
    app = FastAPI()
    app.state.database = FakeDatabase()
    app.include_router(auth_router)
    app.include_router(users_router)
    return app


def user(balance: Decimal = Decimal("10000.00")) -> Any:
    return SimpleNamespace(
        id=uuid.uuid4(),
        github_id="123",
        github_login="octo",
        email="octo@example.com",
        balance=balance,
    )


def settings(**kwargs: Any) -> Any:
    values = dict(
        jwt_secret="a" * 32,
        jwt_algorithm="HS256",
        jwt_expiration_hours=168,
        github_oauth_client_id="client-id",
        github_oauth_client_secret="client-secret",
    )
    values.update(kwargs)
    return SimpleNamespace(**values)


def test_github_login_url(monkeypatch) -> None:
    monkeypatch.setattr(auth_module, "get_settings", settings)

    async def run() -> httpx.Response:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=build_app()), base_url="http://test") as client:
            return await client.get("/v1/auth/github/login", params={"state": "abc"})

    response = asyncio.run(run())
    assert response.status_code == 200
    assert "client_id=client-id" in response.json()["authorization_url"]
    assert "state=abc" in response.json()["authorization_url"]


def test_github_callback_creates_user_and_session(monkeypatch) -> None:
    monkeypatch.setattr(auth_module, "get_settings", settings)
    created_user = user()

    async def exchange(code: str) -> str | None:
        return "github-token"

    async def fetch(token: str) -> dict[str, Any] | None:
        return {"id": 123, "login": "octo", "email": "octo@example.com"}

    async def get_by_github_id(session, github_id: str) -> Any | None:
        return None

    async def create(session, **kwargs) -> Any:
        return created_user

    async def create_session(session, user_id: uuid.UUID) -> str:
        return auth_module.create_access_token(user_id, "session-hash")

    monkeypatch.setattr(auth_routes, "exchange_code_for_token", exchange)
    monkeypatch.setattr(auth_routes, "fetch_github_user", fetch)
    monkeypatch.setattr(UserRepository, "get_by_github_id", get_by_github_id)
    monkeypatch.setattr(UserRepository, "create", create)
    monkeypatch.setattr(auth_routes, "create_user_session", create_session)

    async def run() -> httpx.Response:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=build_app()), base_url="http://test") as client:
            return await client.get("/v1/auth/github/callback", params={"code": "code"})

    response = asyncio.run(run())
    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"


def patch_current_user(monkeypatch, current_user: Any) -> None:
    async def get_active(session, token_hash: str) -> Any | None:
        return SimpleNamespace(user_id=current_user.id)

    async def get_by_id(session, user_id: uuid.UUID) -> Any | None:
        return current_user

    monkeypatch.setattr(auth_module, "get_token_claims", lambda token: (current_user.id, "session-hash"))
    monkeypatch.setattr(UserSessionRepository, "get_active", get_active)
    monkeypatch.setattr(UserRepository, "get_by_id", get_by_id)


def test_users_me_returns_profile(monkeypatch) -> None:
    current_user = user()
    patch_current_user(monkeypatch, current_user)

    async def run() -> httpx.Response:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=build_app()), base_url="http://test") as client:
            return await client.get("/v1/users/me", headers={"Authorization": "Bearer token"})

    response = asyncio.run(run())
    assert response.status_code == 200
    assert response.json()["github_login"] == "octo"
    assert response.json()["currency"] == "CNY"


def test_recharge_rejects_extra_precision(monkeypatch) -> None:
    patch_current_user(monkeypatch, user())

    async def run() -> httpx.Response:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=build_app()), base_url="http://test") as client:
            return await client.post("/v1/users/me/balance/recharge", headers={"Authorization": "Bearer token"}, json={"amount": "1.001"})

    assert asyncio.run(run()).status_code == 422


def test_buy_agent_deducts_and_creates_subscription(monkeypatch) -> None:
    current_user = user()
    patch_current_user(monkeypatch, current_user)
    calls: list[tuple[str, Any]] = []
    subscription = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=current_user.id,
        agent=AgentName.tela,
        started_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        created_at=datetime.now(timezone.utc),
    )

    async def deduct(session, user_id: uuid.UUID, amount: Decimal, *, commit: bool = True) -> Any | None:
        calls.append(("deduct", amount, commit))
        return current_user

    async def create_subscription(session, **kwargs) -> Any:
        calls.append(("create", kwargs["commit"]))
        return subscription

    monkeypatch.setattr(UserRepository, "deduct_balance", deduct)
    monkeypatch.setattr(UserAgentSubscriptionRepository, "create", create_subscription)

    async def run() -> httpx.Response:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=build_app()), base_url="http://test") as client:
            return await client.post("/v1/users/me/agents/purchase", headers={"Authorization": "Bearer token"}, json={"agent": "tela", "months": 1})

    response = asyncio.run(run())
    assert response.status_code == 200
    assert calls == [("deduct", Decimal("5500.00"), False), ("create", False)]
