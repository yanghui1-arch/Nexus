from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any

import httpx
from fastapi import FastAPI

from src.server.api.routes.account import router as account_router
from src.server.postgres.models import AgentName
from src.server.postgres.repositories import AccountRepository


class FakeDatabase:
    @asynccontextmanager
    async def session(self):
        yield object()


def _build_app() -> FastAPI:
    app = FastAPI()
    app.state.database = FakeDatabase()
    app.include_router(account_router)
    return app


def _get(path: str, *, headers: dict[str, str] | None = None) -> httpx.Response:
    async def run_request() -> httpx.Response:
        transport = httpx.ASGITransport(app=_build_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.get(path, headers=headers)

    return asyncio.run(run_request())


def test_account_overview_returns_identity_balance_and_entitlements(monkeypatch) -> None:
    now = datetime.now(timezone.utc)
    account = SimpleNamespace(
        github_id=42,
        github_login="octocat",
        github_name="Mona Lisa",
        github_avatar_url="https://avatars.githubusercontent.com/u/42?v=4",
        github_html_url="https://github.com/octocat",
        balance_cents=12345,
    )
    entitlements = [
        SimpleNamespace(agent=AgentName.tela, purchased_at=now - timedelta(days=1), expires_at=now + timedelta(days=29)),
        SimpleNamespace(agent=AgentName.sophie, purchased_at=now - timedelta(days=40), expires_at=now - timedelta(days=10)),
    ]

    async def fake_get_by_github_id(session: object, github_id: int) -> Any:
        assert github_id == 42
        return account

    async def fake_list_entitlements(session: object, github_id: int) -> list[Any]:
        assert github_id == 42
        return entitlements

    monkeypatch.setattr(AccountRepository, "get_by_github_id", fake_get_by_github_id)
    monkeypatch.setattr(AccountRepository, "list_entitlements", fake_list_entitlements)

    response = _get("/v1/account/overview", headers={"X-GitHub-User-Id": "42"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["github_id"] == 42
    assert payload["github_login"] == "octocat"
    assert payload["github_name"] == "Mona Lisa"
    assert payload["balance_cents"] == 12345
    assert [item["agent"] for item in payload["entitlements"]] == ["tela", "sophie"]
    assert [item["status"] for item in payload["entitlements"]] == ["active", "expired"]
    assert payload["entitlements"][0]["purchased_at"]
    assert payload["entitlements"][0]["expires_at"]


def test_account_overview_requires_auth_header() -> None:
    response = _get("/v1/account/overview")

    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication required"


def test_account_overview_returns_404_for_unknown_account(monkeypatch) -> None:
    async def fake_get_by_github_id(session: object, github_id: int) -> None:
        return None

    monkeypatch.setattr(AccountRepository, "get_by_github_id", fake_get_by_github_id)

    response = _get("/v1/account/overview", headers={"X-GitHub-User-Id": "42"})

    assert response.status_code == 404
    assert response.json()["detail"] == "Account not found"
