from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from types import SimpleNamespace

import anyio

from src.server.postgres.models import FeatureItemStatus, FeatureStatus, ProductProposalStatus
from src.server.postgres.repositories import FeatureItemRepository, FeatureRepository, ProductProposalRepository
from src.tools.nexus import NexusTaskContext
from src.tools.product import ProductTools


class FakeDatabase:
    @asynccontextmanager
    async def session(self):
        yield "session"


class FakeSession:
    def __init__(self, max_order_index: int):
        self._max_order_index = max_order_index
        self.added = None

    async def execute(self, query):
        return SimpleNamespace(scalar_one=lambda: self._max_order_index)

    def add(self, item):
        self.added = item

    async def commit(self):
        return None

    async def refresh(self, item):
        return None


def _proposal(**overrides):
    now = datetime.now(timezone.utc)
    values = {
        "id": uuid.uuid4(),
        "title": "Improve onboarding",
        "plan_type": "growth",
        "summary": "Help users reach value faster.",
        "answer": "Create a clearer onboarding flow.",
        "project": "nexus",
        "repo": "owner/repo",
        "status": ProductProposalStatus.proposed,
        "source_task_id": uuid.uuid4(),
        "created_at": now,
        "updated_at": now,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _feature(**overrides):
    now = datetime.now(timezone.utc)
    values = {
        "id": uuid.uuid4(),
        "proposal_id": uuid.uuid4(),
        "title": "RAG",
        "description": "Add RAG capability.",
        "project": "nexus",
        "status": FeatureStatus.planned,
        "created_at": now,
        "updated_at": now,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _feature_item(**overrides):
    values = {
        "id": uuid.uuid4(),
        "feature_id": uuid.uuid4(),
        "order_index": 1,
        "title": "Knowledge base",
        "description": "Add a searchable knowledge base.",
        "status": FeatureItemStatus.pending,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_create_proposal_uses_context_task_id_and_repo_default(monkeypatch):
    task_id = uuid.uuid4()
    captured = {}

    async def fake_create(session, **kwargs):
        captured["session"] = session
        captured.update(kwargs)
        return _proposal(
            id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            title=kwargs["title"],
            plan_type=kwargs["plan_type"],
            summary=kwargs["summary"],
            answer=kwargs["answer"],
            project=kwargs["project"],
            repo=kwargs["repo"],
            source_task_id=kwargs["source_task_id"],
        )

    monkeypatch.setattr(ProductProposalRepository, "create", fake_create)
    context = NexusTaskContext(task_id=task_id, database=FakeDatabase(), repo="owner/repo")
    tools = ProductTools(database=FakeDatabase(), context=context)

    async def run():
        return await tools.create_proposal(
            title="Improve onboarding",
            plan_type="growth",
            summary="Help users reach value faster.",
            answer="Create a clearer onboarding flow.",
            project="nexus",
        )

    result = anyio.run(run)

    assert result == {
        "success": True,
        "proposal_id": "00000000-0000-0000-0000-000000000001",
        "status": "proposed",
        "title": "Improve onboarding",
        "project": "nexus",
        "repo": "owner/repo",
        "message": "Product proposal was created for human review.",
    }
    assert captured == {
        "session": "session",
        "title": "Improve onboarding",
        "plan_type": "growth",
        "summary": "Help users reach value faster.",
        "answer": "Create a clearer onboarding flow.",
        "project": "nexus",
        "repo": "owner/repo",
        "source_task_id": task_id,
    }


def test_create_proposal_without_context_has_no_source_task(monkeypatch):
    captured = {}

    async def fake_create(session, **kwargs):
        captured.update(kwargs)
        return _proposal(source_task_id=kwargs["source_task_id"], repo=kwargs["repo"])

    monkeypatch.setattr(ProductProposalRepository, "create", fake_create)
    tools = ProductTools(database=FakeDatabase())

    async def run():
        return await tools.create_proposal(
            title="Title",
            plan_type="feature",
            summary="Summary",
            answer="Answer",
            repo="owner/default",
        )

    result = anyio.run(run)

    assert result["success"] is True
    assert captured["source_task_id"] is None
    assert captured["repo"] == "owner/default"


def test_create_feature_for_product_proposal_requires_approved_proposal(monkeypatch):
    proposal_id = uuid.uuid4()

    async def fake_get(session, pid):
        return _proposal(id=pid, status=ProductProposalStatus.proposed)

    monkeypatch.setattr(ProductProposalRepository, "get", fake_get)
    tools = ProductTools(database=FakeDatabase())

    async def run():
        return await tools.create_feature_for_product_proposal(
            proposal_id=proposal_id,
            title="RAG",
            description="Add RAG capability.",
        )

    result = anyio.run(run)

    assert result == {
        "success": False,
        "message": "Only approved proposals can become features.",
    }


def test_create_feature_for_product_proposal_from_approved_proposal(monkeypatch):
    proposal_id = uuid.uuid4()
    feature = _feature(id=uuid.uuid4(), proposal_id=proposal_id)
    captured = {}

    async def fake_get(session, pid):
        return _proposal(id=pid, status=ProductProposalStatus.approved)

    async def fake_create(session, **kwargs):
        captured.update(kwargs)
        return feature

    monkeypatch.setattr(ProductProposalRepository, "get", fake_get)
    monkeypatch.setattr(FeatureRepository, "create", fake_create)
    tools = ProductTools(database=FakeDatabase())

    async def run():
        return await tools.create_feature_for_product_proposal(
            proposal_id=proposal_id,
            title="RAG",
            description="Add RAG capability.",
        )

    result = anyio.run(run)

    assert result == {
        "success": True,
        "feature_id": str(feature.id),
        "proposal_id": str(proposal_id),
        "status": "planned",
        "title": "RAG",
        "project": "nexus",
        "message": "Feature was created for planning.",
    }
    assert captured == {
        "proposal_id": proposal_id,
        "title": "RAG",
        "description": "Add RAG capability.",
        "project": "nexus",
    }


def test_create_feature_item_requires_existing_feature(monkeypatch):
    feature_id = uuid.uuid4()

    async def fake_get(session, fid):
        return None

    monkeypatch.setattr(FeatureRepository, "get", fake_get)
    tools = ProductTools(database=FakeDatabase())

    async def run():
        return await tools.create_feature_item(
            feature_id=feature_id,
            title="Knowledge base",
            description="Add a searchable knowledge base.",
        )

    result = anyio.run(run)

    assert result == {
        "success": False,
        "message": "Feature not found.",
    }


def test_create_feature_item_from_feature(monkeypatch):
    feature_id = uuid.uuid4()
    feature = _feature(id=feature_id)
    item = _feature_item(feature_id=feature_id, order_index=2)
    captured = {}

    async def fake_get(session, fid):
        return feature

    async def fake_create(session, **kwargs):
        captured.update(kwargs)
        return item

    monkeypatch.setattr(FeatureRepository, "get", fake_get)
    monkeypatch.setattr(FeatureItemRepository, "create", fake_create)
    tools = ProductTools(database=FakeDatabase())

    async def run():
        return await tools.create_feature_item(
            feature_id=feature_id,
            title="Knowledge base",
            description="Add a searchable knowledge base.",
        )

    result = anyio.run(run)

    assert result == {
        "success": True,
        "feature_item_id": str(item.id),
        "feature_id": str(feature_id),
        "order_index": 2,
        "title": "Knowledge base",
        "description": "Add a searchable knowledge base.",
        "status": "pending",
    }
    assert captured == {
        "feature_id": feature_id,
        "title": "Knowledge base",
        "description": "Add a searchable knowledge base.",
    }


def test_feature_item_repository_create_assigns_next_order_index():
    session = FakeSession(max_order_index=3)
    feature_id = uuid.uuid4()

    async def run():
        return await FeatureItemRepository.create(
            session,
            feature_id=feature_id,
            title="Knowledge base",
            description="Add a searchable knowledge base.",
        )

    item = anyio.run(run)

    assert session.added is item
    assert item.feature_id == feature_id
    assert item.order_index == 4
    assert item.status == FeatureItemStatus.pending
