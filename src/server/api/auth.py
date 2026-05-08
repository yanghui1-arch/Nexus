"""Authentication utilities: JWT and GitHub OAuth."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
import jwt
from fastapi import HTTPException, Request

from src.server.config import get_settings
from src.server.postgres.database import Database
from src.server.postgres.models import UserRecord
from src.server.postgres.repositories import UserRepository

_GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
_GITHUB_ACCESS_TOKEN_URL = "https://github.com/login/oauth/access_token"
_GITHUB_USER_URL = "https://api.github.com/user"

_AGENT_PRICES: dict[str, Any] = {
    "tela": "5500",
    "sophie": "6000",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(user_id: uuid.UUID) -> str:
    settings = get_settings()
    if not settings.jwt_secret:
        raise RuntimeError("NEXUS_JWT_SECRET is not configured")
    payload = {
        "sub": str(user_id),
        "exp": _now() + timedelta(hours=settings.jwt_expiration_hours),
        "iat": _now(),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def verify_access_token(token: str) -> uuid.UUID | None:
    settings = get_settings()
    if not settings.jwt_secret:
        return None
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        user_id_str = payload.get("sub")
        if not user_id_str:
            return None
        return uuid.UUID(user_id_str)
    except jwt.PyJWTError:
        return None


def build_github_login_url(state: str) -> str:
    settings = get_settings()
    if not settings.github_oauth_client_id:
        raise RuntimeError("NEXUS_GITHUB_OAUTH_CLIENT_ID is not configured")
    params = {
        "client_id": settings.github_oauth_client_id,
        "scope": "read:user user:email",
        "state": state,
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{_GITHUB_AUTHORIZE_URL}?{query}"


async def exchange_code_for_token(code: str) -> str | None:
    settings = get_settings()
    if not settings.github_oauth_client_id or not settings.github_oauth_client_secret:
        return None
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            _GITHUB_ACCESS_TOKEN_URL,
            headers={"Accept": "application/json"},
            data={
                "client_id": settings.github_oauth_client_id,
                "client_secret": settings.github_oauth_client_secret,
                "code": code,
            },
        )
    if resp.status_code != 200:
        return None
    data = resp.json()
    return data.get("access_token")


async def fetch_github_user(token: str) -> dict[str, Any] | None:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            _GITHUB_USER_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
            },
        )
    if resp.status_code != 200:
        return None
    return resp.json()


async def get_current_user(request: Request) -> UserRecord:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
    token = auth_header[7:]
    user_id = verify_access_token(token)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    database: Database = request.app.state.database
    async with database.session() as session:
        user = await UserRepository.get_by_id(session, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def get_agent_price(agent: str) -> Any:
    price = _AGENT_PRICES.get(agent)
    if price is None:
        raise ValueError(f"Unknown agent: {agent}")
    return price
