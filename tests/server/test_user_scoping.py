from __future__ import annotations

from decimal import Decimal
from datetime import timedelta

import pytest
from sqlalchemy import select

from src.server.postgres.models import AgentInstanceRecord, AgentName, TaskCategory, TaskStatus
from src.server.postgres.repositories import AgentPurchaseRepository, TaskRepository, UserRepository, utc_now


@pytest.mark.asyncio
async def test_purchase_stores_user_on_agent_instance(db_session):
    """Verify purchase stores user on agent instance."""
    user = await UserRepository.upsert_github_user(
        db_session,
        github_id="scope-1",
        github_login="owner",
        email=None,
    )
    await UserRepository.add_balance(db_session, user.id, Decimal("6000.00"))

    purchase = await AgentPurchaseRepository.create_purchase(
        db_session,
        user_id=user.id,
        agent=AgentName.tela,
        price=Decimal("5500.00"),
        expires_at=utc_now() + timedelta(days=30),
    )

    instance = await db_session.get(AgentInstanceRecord, purchase.agent_instance_id)
    assert instance is not None
    assert instance.user_id == user.id


@pytest.mark.asyncio
async def test_task_repository_filters_by_agent_instance_user(db_session):
    """Verify task repository filters by agent instance user."""
    owner = await UserRepository.upsert_github_user(db_session, github_id="scope-2", github_login="owner", email=None)
    other = await UserRepository.upsert_github_user(db_session, github_id="scope-3", github_login="other", email=None)
    owner_instance = AgentInstanceRecord(user_id=owner.id, agent=AgentName.tela, client_id="owner", is_active=True)
    other_instance = AgentInstanceRecord(user_id=other.id, agent=AgentName.tela, client_id="other", is_active=True)
    db_session.add_all([owner_instance, other_instance])
    await db_session.commit()
    await db_session.refresh(owner_instance)
    await db_session.refresh(other_instance)

    owner_task = await TaskRepository.create(
        db_session,
        agent=AgentName.tela,
        agent_instance_id=owner_instance.id,
        category=TaskCategory.coding,
        question="owner task",
        repo=None,
        project=None,
        external_issue_url=None,
    )
    await TaskRepository.create(
        db_session,
        agent=AgentName.tela,
        agent_instance_id=other_instance.id,
        category=TaskCategory.coding,
        question="other task",
        repo=None,
        project=None,
        external_issue_url=None,
    )

    tasks = await TaskRepository.list(db_session, user_id=owner.id)
    assert [task.id for task in tasks] == [owner_task.id]
    assert await TaskRepository.get(db_session, owner_task.id) == owner_task


@pytest.mark.asyncio
async def test_task_repository_get_for_user_allows_inactive_expired_agent_instances(db_session):
    """Verify historical task lookup is not gated on active agent entitlements."""
    owner = await UserRepository.upsert_github_user(db_session, github_id="scope-4", github_login="expired", email=None)
    other = await UserRepository.upsert_github_user(db_session, github_id="scope-5", github_login="other-expired", email=None)
    expired_instance = AgentInstanceRecord(
        user_id=owner.id,
        agent=AgentName.tela,
        client_id="expired-owner",
        is_active=False,
        expires_at=utc_now() - timedelta(days=1),
    )
    db_session.add(expired_instance)
    await db_session.commit()
    await db_session.refresh(expired_instance)

    task = await TaskRepository.create(
        db_session,
        agent=AgentName.tela,
        agent_instance_id=expired_instance.id,
        category=TaskCategory.coding,
        question="historical task",
        repo=None,
        project=None,
        external_issue_url=None,
    )

    assert await TaskRepository.get_for_user(db_session, task.id, user_id=owner.id) == task
    assert await TaskRepository.get_for_user(db_session, task.id, user_id=other.id) is None
