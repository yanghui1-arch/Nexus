"""GitHub OAuth, bearer-token sessions, and current-user dependency."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import HTTPException, Request

from src.server.config import get_settings
from src.server.postgres.database import Database
from src.server.postgres.models import UserRecord
from src.server.postgres.repositories import UserRepository, UserSessionRepository

_GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
_GITHUB_ACCESS_TOKEN_URL = "https://github.com/login/oauth/access_token"
_GITHUB_USER_URL = "https://api.github.com/user"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _decode_token(token: str) -> dict[str, Any] | None:
    settings = get_settings()
    if not settings.jwt_secret:
        return None
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError:
        return None


def create_access_token(user_id: uuid.UUID, session_hash: str) -> str:
    settings = get_settings()
    if not settings.jwt_secret:
        raise RuntimeError("NEXUS_JWT_SECRET is not configured")
    return jwt.encode(
        {
            "sub": str(user_id),
            "sid": session_hash,
            "iat": _now(),
            "exp": _now() + timedelta(hours=settings.jwt_expiration_hours),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


async def create_user_session(session: Any, user_id: uuid.UUID) -> str:
    settings = get_settings()
    session_hash = hash_session_token(secrets.token_urlsafe(32))
    await UserSessionRepository.create(
        session,
        user_id=user_id,
        token_hash=session_hash,
        expires_at=_now() + timedelta(hours=settings.jwt_expiration_hours),
    )
    return create_access_token(user_id, session_hash)


def get_token_claims(token: str) -> tuple[uuid.UUID, str] | None:
    payload = _decode_token(token)
    if payload is None or not payload.get("sub") or not payload.get("sid"):
        return None
    try:
        return uuid.UUID(str(payload["sub"])), str(payload["sid"])
    except ValueError:
        return None


def build_github_login_url(state: str, redirect_uri: str | None = None) -> str:
    settings = get_settings()
    if not settings.github_oauth_client_id:
        raise RuntimeError("NEXUS_GITHUB_OAUTH_CLIENT_ID is not configured")
    params = {"client_id": settings.github_oauth_client_id, "scope": "read:user user:email", "state": state}
    if redirect_uri:
        params["redirect_uri"] = redirect_uri
    query = urlencode(params)
    return f"{_GITHUB_AUTHORIZE_URL}?{query}"


async def get_current_user(request: Request) -> UserRecord:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
    claims = get_token_claims(auth_header[7:])
    if claims is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user_id, session_hash = claims
    database: Database = request.app.state.database
    async with database.session() as session:
        active_session = await UserSessionRepository.get_active(session, session_hash)
        if active_session is None or active_session.user_id != user_id:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        user = await UserRepository.get_by_id(session, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user

async def exchange_code_for_token(code: str) -> str | None:
    settings = get_settings()
    if not settings.github_oauth_client_id or not settings.github_oauth_client_secret:
        return None
    async with httpx.AsyncClient() as client:
        response = await client.post(
            _GITHUB_ACCESS_TOKEN_URL,
            headers={"Accept": "application/json"},
            data={"client_id": settings.github_oauth_client_id, "client_secret": settings.github_oauth_client_secret, "code": code},
        )
    return response.json().get("access_token") if response.status_code == 200 else None


async def fetch_github_user(token: str) -> dict[str, Any] | None:
    async with httpx.AsyncClient() as client:
        response = await client.get(_GITHUB_USER_URL, headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"})
    return response.json() if response.status_code == 200 else None
