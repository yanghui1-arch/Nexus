from __future__ import annotations

from datetime import timedelta

import pytest

import hashlib

AGENT_PRICES_CENTS = {"tela": 550_000, "sophie": 600_000}

def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
from src.server.postgres.models import AgentName
from src.server.postgres.repositories import (
    AgentPurchaseRepository,
    AuthSessionRepository,
    UserRepository,
    utc_now,
)


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

    recharged = await UserRepository.add_balance(db_session, user.id, 600_000)
    assert recharged is not None
    assert recharged.balance_cents == 600_000

    purchase = await AgentPurchaseRepository.create_purchase(
        db_session,
        user_id=user.id,
        agent=AgentName.tela,
        price_cents=AGENT_PRICES_CENTS["tela"],
        expires_at=utc_now() + timedelta(days=30),
    )
    assert purchase.price_cents == 550_000
    updated = await UserRepository.get(db_session, user.id)
    assert updated is not None
    assert updated.balance_cents == 50_000


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
            price_cents=AGENT_PRICES_CENTS["sophie"],
            expires_at=utc_now() + timedelta(days=30),
        )
