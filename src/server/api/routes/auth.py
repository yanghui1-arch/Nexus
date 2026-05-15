"""GitHub OAuth and user billing routes."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import timedelta
from decimal import Decimal
from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse

from src.server.config import get_settings
from src.server.postgres.database import Database
from src.server.postgres.models import AgentName, UserRecord
from src.server.postgres.repositories import (
    AgentPurchaseRepository,
    AuthSessionRepository,
    UserRepository,
    utc_now,
)
from src.server.schemas import (
    PurchaseAgentRequest,
    PurchaseAgentResponse,
    RechargeRequest,
    UserResponse,
)

router = APIRouter(prefix="/v1", tags=["auth"])
AGENT_PRICES = {AgentName.tela: Decimal("5500.00"), AgentName.sophie: Decimal("6000.00")}


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def get_current_user(request: Request) -> UserRecord:
    settings = get_settings()
    token = request.cookies.get(settings.auth_session_cookie_name)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    database: Database = request.app.state.database
    async with database.session() as session:
        user = await AuthSessionRepository.get_user_by_token_hash(session, _hash_token(token))
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    return user


@router.get("/auth/github/login")
async def github_login() -> RedirectResponse:
    settings = get_settings()
    if not settings.github_oauth_client_id:
        raise HTTPException(status_code=500, detail="GitHub OAuth client id is not configured")
    query = urlencode(
        {
            "client_id": settings.github_oauth_client_id,
            "redirect_uri": settings.github_oauth_redirect_uri,
            "scope": "read:user user:email",
        }
    )
    return RedirectResponse(f"https://github.com/login/oauth/authorize?{query}")


@router.get("/auth/github/callback")
async def github_callback(request: Request, code: str) -> RedirectResponse:
    settings = get_settings()
    if not settings.github_oauth_client_id or not settings.github_oauth_client_secret:
        raise HTTPException(status_code=500, detail="GitHub OAuth is not configured")
    async with httpx.AsyncClient(timeout=10) as client:
        token_response = await client.post(
            "https://github.com/login/oauth/access_token",
            json={
                "client_id": settings.github_oauth_client_id,
                "client_secret": settings.github_oauth_client_secret,
                "code": code,
                "redirect_uri": settings.github_oauth_redirect_uri,
            },
            headers={"Accept": "application/json"},
        )
        access_token = token_response.json().get("access_token")
        if not access_token:
            raise HTTPException(status_code=400, detail="GitHub authorization failed")
        headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
        github_user = (await client.get("https://api.github.com/user", headers=headers)).json()
        emails: list[dict[str, Any]] = (await client.get("https://api.github.com/user/emails", headers=headers)).json()

    primary_email = next((item.get("email") for item in emails if item.get("primary")), None)
    database: Database = request.app.state.database
    session_token = secrets.token_urlsafe(32)
    expires_at = utc_now() + timedelta(seconds=settings.auth_session_ttl_seconds)
    async with database.session() as session:
        user = await UserRepository.upsert_github_user(
            session,
            github_id=str(github_user["id"]),
            github_login=github_user["login"],
            email=primary_email or github_user.get("email"),
        )
        await AuthSessionRepository.create(
            session,
            token_hash=_hash_token(session_token),
            user_id=user.id,
            expires_at=expires_at,
        )
    response = RedirectResponse("/pricing")
    response.set_cookie(
        settings.auth_session_cookie_name,
        session_token,
        max_age=settings.auth_session_ttl_seconds,
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
    )
    return response


@router.get("/auth/me", response_model=UserResponse)
async def get_me(user: UserRecord = Depends(get_current_user)) -> UserResponse:
    return UserResponse(
        id=user.id,
        github_login=user.github_login,
        email=user.email,
        balance=user.balance,
    )


@router.post("/auth/logout", status_code=204)
async def logout(request: Request, response: Response) -> None:
    settings = get_settings()
    token = request.cookies.get(settings.auth_session_cookie_name)
    if token:
        database: Database = request.app.state.database
        async with database.session() as session:
            await AuthSessionRepository.delete(session, _hash_token(token))
    response.delete_cookie(settings.auth_session_cookie_name)


@router.post("/billing/recharge", response_model=UserResponse)
async def recharge_balance(
    request: Request,
    payload: RechargeRequest,
    user: UserRecord = Depends(get_current_user),
) -> UserResponse:
    database: Database = request.app.state.database
    async with database.session() as session:
        updated = await UserRepository.add_balance(session, user.id, payload.amount)
    if updated is None:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse(
        id=updated.id,
        github_login=updated.github_login,
        email=updated.email,
        balance=updated.balance,
    )


@router.post("/billing/purchases", response_model=PurchaseAgentResponse, status_code=201)
async def purchase_agent(
    request: Request,
    payload: PurchaseAgentRequest,
    user: UserRecord = Depends(get_current_user),
) -> PurchaseAgentResponse:
    agent = AgentName(payload.agent.value)
    price = AGENT_PRICES[agent]
    database: Database = request.app.state.database
    async with database.session() as session:
        try:
            purchase = await AgentPurchaseRepository.create_purchase(
                session,
                user_id=user.id,
                agent=agent,
                price=price,
                expires_at=utc_now() + timedelta(days=30),
            )
        except ValueError:
            raise HTTPException(status_code=400, detail="Purchase failed") from None
        updated_user = await UserRepository.get(session, user.id)
    assert updated_user is not None
    return PurchaseAgentResponse(
        id=purchase.id,
        agent=purchase.agent.value,
        price=purchase.price,
        balance=updated_user.balance,
        purchased_at=purchase.purchased_at,
        expires_at=purchase.expires_at,
    )
