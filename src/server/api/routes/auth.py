"""Authentication and user billing API routes."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from src.server.api.auth import (
    build_github_login_url,
    create_user_session,
    exchange_code_for_token,
    fetch_github_user,
    get_current_user,
    get_token_claims,
)
from src.server.postgres.database import Database
from src.server.postgres.models import AgentName, UserRecord
from src.server.postgres.repositories import (
    AGENT_MONTHLY_PRICES_CNY,
    UserAgentSubscriptionRepository,
    UserRepository,
    UserSessionRepository,
)
from src.server.schemas import (
    AuthTokenResponse,
    BuyAgentRequest,
    RechargeRequest,
    UserAgentSubscriptionResponse,
    UserResponse,
)

auth_router = APIRouter(prefix="/v1/auth", tags=["auth"])
users_router = APIRouter(prefix="/v1/users", tags=["users"])


@auth_router.get("/github/login")
async def github_login(state: str = Query(default="")) -> dict[str, str]:
    try:
        return {"authorization_url": build_github_login_url(state)}
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@auth_router.get("/github/callback", response_model=AuthTokenResponse)
async def github_callback(request: Request, code: str = Query(...)) -> AuthTokenResponse:
    access_token = await exchange_code_for_token(code)
    if access_token is None:
        raise HTTPException(status_code=400, detail="Failed to exchange code for token")
    github_user = await fetch_github_user(access_token)
    if github_user is None:
        raise HTTPException(status_code=400, detail="Failed to fetch GitHub user")

    github_id = str(github_user.get("id", ""))
    github_login = str(github_user.get("login", ""))
    if not github_id or not github_login:
        raise HTTPException(status_code=400, detail="Invalid GitHub user data")

    database: Database = request.app.state.database
    async with database.session() as session:
        user = await UserRepository.get_by_github_id(session, github_id)
        if user is None:
            user = await UserRepository.create(
                session,
                github_id=github_id,
                github_login=github_login,
                email=github_user.get("email") or None,
            )
        token = await create_user_session(session, user.id)
    return AuthTokenResponse(access_token=token)


@auth_router.post("/logout")
async def logout(request: Request) -> dict[str, str]:
    auth_header = request.headers.get("Authorization", "")
    claims = get_token_claims(auth_header[7:]) if auth_header.startswith("Bearer ") else None
    if claims is None:
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
    database: Database = request.app.state.database
    async with database.session() as session:
        await UserSessionRepository.revoke(session, claims[1])
    return {"message": "Logged out successfully"}


async def me(current_user: UserRecord = Depends(get_current_user)) -> UserResponse:
    return UserResponse.from_record(current_user)


async def recharge(
    request: Request,
    payload: RechargeRequest,
    current_user: UserRecord = Depends(get_current_user),
) -> UserResponse:
    database: Database = request.app.state.database
    async with database.session() as session:
        user = await UserRepository.add_balance(session, current_user.id, Decimal(payload.amount))
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse.from_record(user)


auth_router.add_api_route("/me", me, methods=["GET"], response_model=UserResponse)
auth_router.add_api_route("/recharge", recharge, methods=["POST"], response_model=UserResponse)
users_router.add_api_route("/me", me, methods=["GET"], response_model=UserResponse)
users_router.add_api_route("/me/balance/recharge", recharge, methods=["POST"], response_model=UserResponse)

router = auth_router
