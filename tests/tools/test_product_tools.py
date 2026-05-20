from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from types import SimpleNamespace

import anyio

from src.server.postgres.models import (
    FeatureItemStatus,
    FeatureRecord,
    FeatureStatus,
    ProductProposalRecord,
    ProductProposalStatus,
)
from src.server.postgres.repositories import FeatureItemRepository, FeatureRepository, ProductProposalRepository, TaskRepository
from src.tools.nexus import NexusTaskContext
from src.tools.product import ProductTools


class FakeDatabase:
    def __init__(self, session_obj="session"):
        self._session_obj = session_obj

    @asynccontextmanager
    async def session(self):
        yield self._session_obj


class FakeSession:
    def __init__(self, max_order_index: int):
        self._max_order_index = max_order_index
        self.added = None

    async def execute(self, query):
        return SimpleNamespace(scalar_one=lambda: self._max_order_index)

    def add(self, item):
        self.added = item

    async def flush(self):
        return None

    async def commit(self):
        return None

    async def refresh(self, item):
        return None


class FakeFeatureItemSyncSession:
    def __init__(
        self,
        *,
        feature: SimpleNamespace,
        proposal: SimpleNamespace,
        item_statuses: list[FeatureItemStatus],
        sibling_feature_statuses: list[FeatureStatus],
    ) -> None:
        self.feature = feature
        self.proposal = proposal
        self.item_statuses = item_statuses
        self.sibling_feature_statuses = sibling_feature_statuses
        self.execute_call_count = 0

    async def get(self, model, object_id):
        if model is FeatureRecord and object_id == self.feature.id:
            return self.feature
        if model is ProductProposalRecord and object_id == self.proposal.id:
            return self.proposal
        return None

    async def execute(self, query):
        del query
        self.execute_call_count += 1
        statuses = (
            self.item_statuses
            if self.execute_call_count == 1
            else [self.feature.status, *self.sibling_feature_statuses]
        )
        return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: list(statuses)))


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
        "user_id": uuid.uuid4(),
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
    user_id = uuid.uuid4()
    captured = {}

    class SessionWithAgentInstance:
        async def get(self, model, object_id):
            return SimpleNamespace(user_id=user_id)

    async def fake_get_task(session, tid):
        return SimpleNamespace(agent_instance_id=uuid.uuid4())

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
    monkeypatch.setattr(TaskRepository, "get", fake_get_task)
    context = NexusTaskContext(task_id=task_id, database=FakeDatabase(), repo="owner/repo")
    tools = ProductTools(database=FakeDatabase(SessionWithAgentInstance()), context=context)

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
    assert isinstance(captured.pop("session"), SessionWithAgentInstance)
    assert captured == {
        "title": "Improve onboarding",
        "plan_type": "growth",
        "summary": "Help users reach value faster.",
        "answer": "Create a clearer onboarding flow.",
        "project": "nexus",
        "repo": "owner/repo",
        "user_id": user_id,
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

    assert result == {"success": False, "message": "Product proposal requires a task context."}
    assert captured == {}


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
        "message": "Only approved or planned proposals can become features.",
    }


def test_create_feature_for_product_proposal_from_approved_proposal(monkeypatch):
    proposal_id = uuid.uuid4()
    feature_user_id = uuid.uuid4()
    feature = _feature(id=uuid.uuid4(), proposal_id=proposal_id)
    captured = {}

    async def fake_get(session, pid):
        return _proposal(id=pid, user_id=feature_user_id, status=ProductProposalStatus.approved)

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
        "user_id": feature_user_id,
    }


def test_create_feature_for_product_proposal_from_planned_proposal(monkeypatch):
    proposal_id = uuid.uuid4()
    feature = _feature(id=uuid.uuid4(), proposal_id=proposal_id)

    async def fake_get(session, pid):
        return _proposal(id=pid, user_id=uuid.uuid4(), status=ProductProposalStatus.planned)

    async def fake_create(session, **kwargs):
        return feature

    monkeypatch.setattr(ProductProposalRepository, "get", fake_get)
    monkeypatch.setattr(FeatureRepository, "create", fake_create)
    tools = ProductTools(database=FakeDatabase())

    async def run():
        return await tools.create_feature_for_product_proposal(
            proposal_id=proposal_id,
            title="Follow-up slice",
            description="Add a follow-up feature.",
        )

    result = anyio.run(run)

    assert result["success"] is True
    assert result["proposal_id"] == str(proposal_id)


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


def test_feature_item_repository_create_assigns_next_order_index(monkeypatch):
    session = FakeSession(max_order_index=3)
    feature_id = uuid.uuid4()
    captured = {}

    async def fake_sync_status_from_items(current_session, current_feature_id):
        captured["session"] = current_session
        captured["feature_id"] = current_feature_id
        return None

    monkeypatch.setattr(FeatureRepository, "sync_status_from_items", fake_sync_status_from_items)

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
    assert captured == {"session": session, "feature_id": feature_id}


def test_feature_repository_sync_status_from_items_marks_linked_proposal_completed():
    proposal = _proposal(status=ProductProposalStatus.planned)
    feature = _feature(proposal_id=proposal.id, status=FeatureStatus.in_progress)
    session = FakeFeatureItemSyncSession(
        feature=feature,
        proposal=proposal,
        item_statuses=[FeatureItemStatus.completed, FeatureItemStatus.closed],
        sibling_feature_statuses=[FeatureStatus.closed],
    )

    async def run():
        return await FeatureRepository.sync_status_from_items(session, feature.id)

    updated = anyio.run(run)

    assert updated.status == FeatureStatus.completed
    assert proposal.status == ProductProposalStatus.completed


def test_feature_repository_sync_status_from_items_reopens_linked_proposal_when_work_remains():
    proposal = _proposal(status=ProductProposalStatus.completed)
    feature = _feature(proposal_id=proposal.id, status=FeatureStatus.completed)
    session = FakeFeatureItemSyncSession(
        feature=feature,
        proposal=proposal,
        item_statuses=[FeatureItemStatus.pending, FeatureItemStatus.closed],
        sibling_feature_statuses=[FeatureStatus.closed],
    )

    async def run():
        return await FeatureRepository.sync_status_from_items(session, feature.id)

    updated = anyio.run(run)

    assert updated.status == FeatureStatus.planned
    assert proposal.status == ProductProposalStatus.planned
