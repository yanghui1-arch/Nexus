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
from src.server.postgres.repositories import FeatureItemRepository, FeatureRepository, ProductProposalRepository
from src.tools.nexus import NexusTaskContext
from src.tools.product import ProductTools


class FakeDatabase:
    def __init__(self, session_obj="session"):
        """Initialize the test helper."""
        self._session_obj = session_obj

    @asynccontextmanager
    async def session(self):
        """Return a fake database session."""
        yield self._session_obj


class FakeSession:
    def __init__(self, max_order_index: int):
        """Initialize the test helper."""
        self._max_order_index = max_order_index
        self.added = None

    async def execute(self, query):
        """Execute a fake database operation."""
        return SimpleNamespace(scalar_one=lambda: self._max_order_index)

    def add(self, item):
        """Record an added model."""
        self.added = item

    async def flush(self):
        """Flush the fake session."""
        return None

    async def commit(self):
        """Commit the fake session."""
        return None

    async def refresh(self, item):
        """Refresh a fake model."""
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
        """Initialize the test helper."""
        self.feature = feature
        self.proposal = proposal
        self.item_statuses = item_statuses
        self.sibling_feature_statuses = sibling_feature_statuses
        self.execute_call_count = 0

    async def get(self, model, object_id):
        """Return a fake stored value."""
        if model is FeatureRecord and object_id == self.feature.id:
            return self.feature
        if model is ProductProposalRecord and object_id == self.proposal.id:
            return self.proposal
        return None

    async def execute(self, query):
        """Execute a fake database operation."""
        del query
        self.execute_call_count += 1
        if self.execute_call_count == 1:
            return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: list(self.item_statuses)))
        if self.execute_call_count == 2:
            rows = [
                (self.feature.id, self.feature.status),
                *[(uuid.uuid4(), status) for status in self.sibling_feature_statuses],
            ]
            return SimpleNamespace(all=lambda: rows)
        return SimpleNamespace(scalar_one=lambda: len(self.item_statuses))


def _context(*, task_id: uuid.UUID | None = None, user_id: uuid.UUID | None = None) -> NexusTaskContext:
    """Create a Nexus task context for product-tool tests."""
    return NexusTaskContext(
        task_id=task_id or uuid.uuid4(),
        database=FakeDatabase(),
        user_id=user_id or uuid.uuid4(),
        repo="owner/repo",
        project="nexus",
    )


def _proposal(**overrides):
    """Create a product proposal record."""
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
    """Create a feature record."""
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
    """Create a feature item record."""
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


def test_create_proposal_uses_context_task_project_and_repo_default(monkeypatch):
    """Verify create proposal uses the task context repo/project snapshot."""
    task_id = uuid.uuid4()
    captured = {}

    user_id = uuid.uuid4()

    async def fake_create(session, **kwargs):
        """Provide a fake create."""
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
            user_id=kwargs["user_id"],
            source_task_id=kwargs["source_task_id"],
        )

    monkeypatch.setattr(ProductProposalRepository, "create", fake_create)
    context = _context(task_id=task_id, user_id=user_id)
    tools = ProductTools(database=FakeDatabase(), context=context)

    async def run():
        """Run the async test body."""
        return await tools.create_proposal(
            title="Improve onboarding",
            plan_type="growth",
            summary="Help users reach value faster.",
            answer="Create a clearer onboarding flow.",
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
        "user_id": user_id,
        "project": "nexus",
        "repo": "owner/repo",
        "source_task_id": task_id,
    }


def test_create_proposal_uses_context_project_even_when_repo_is_overridden(monkeypatch):
    """Verify create proposal always persists the task project snapshot."""
    captured = {}

    async def fake_create(session, **kwargs):
        """Provide a fake create."""
        captured["session"] = session
        captured.update(kwargs)
        return _proposal(
            project=kwargs["project"],
            repo=kwargs["repo"],
            user_id=kwargs["user_id"],
            source_task_id=kwargs["source_task_id"],
        )

    monkeypatch.setattr(ProductProposalRepository, "create", fake_create)
    context = _context()
    tools = ProductTools(database=FakeDatabase(), context=context)

    async def run():
        """Run the async test body."""
        return await tools.create_proposal(
            title="Improve onboarding",
            plan_type="growth",
            summary="Help users reach value faster.",
            answer="Create a clearer onboarding flow.",
            repo="owner/override",
        )

    result = anyio.run(run)

    assert result["success"] is True
    assert result["project"] == "nexus"
    assert result["repo"] == "owner/override"
    assert captured["project"] == "nexus"


def test_create_proposal_without_context_has_no_source_task(monkeypatch):
    """Verify create proposal requires Nexus task context."""
    tools = ProductTools(database=FakeDatabase())

    async def run():
        """Run the async test body."""
        return await tools.create_proposal(
            title="Title",
            plan_type="feature",
            summary="Summary",
            answer="Answer",
            repo="owner/default",
        )

    result = anyio.run(run)

    assert result == {
        "success": False,
        "message": "Nexus task context is not available.",
    }


def test_create_feature_for_product_proposal_requires_approved_proposal(monkeypatch):
    """Verify create feature for product proposal requires approved proposal."""
    proposal_id = uuid.uuid4()

    async def fake_get(session, pid):
        """Provide a fake get."""
        return _proposal(id=pid, user_id=context.user_id, status=ProductProposalStatus.proposed)

    monkeypatch.setattr(ProductProposalRepository, "get", fake_get)
    context = _context()
    tools = ProductTools(database=FakeDatabase(), context=context)

    async def run():
        """Run the async test body."""
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
    """Verify create feature for product proposal from approved proposal."""
    proposal_id = uuid.uuid4()
    feature = _feature(id=uuid.uuid4(), proposal_id=proposal_id)
    captured = {}
    context = _context()

    async def fake_get(session, pid):
        """Provide a fake get."""
        return _proposal(id=pid, user_id=context.user_id, status=ProductProposalStatus.approved)

    async def fake_create(session, **kwargs):
        """Provide a fake create."""
        captured.update(kwargs)
        return feature

    monkeypatch.setattr(ProductProposalRepository, "get", fake_get)
    monkeypatch.setattr(FeatureRepository, "create", fake_create)
    tools = ProductTools(database=FakeDatabase(), context=context)

    async def run():
        """Run the async test body."""
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


def test_create_feature_for_product_proposal_from_planned_proposal(monkeypatch):
    """Verify create feature for product proposal from planned proposal."""
    proposal_id = uuid.uuid4()
    feature = _feature(id=uuid.uuid4(), proposal_id=proposal_id)
    context = _context()

    async def fake_get(session, pid):
        """Provide a fake get."""
        return _proposal(id=pid, user_id=context.user_id, status=ProductProposalStatus.planned)

    async def fake_create(session, **kwargs):
        """Provide a fake create."""
        return feature

    monkeypatch.setattr(ProductProposalRepository, "get", fake_get)
    monkeypatch.setattr(FeatureRepository, "create", fake_create)
    tools = ProductTools(database=FakeDatabase(), context=context)

    async def run():
        """Run the async test body."""
        return await tools.create_feature_for_product_proposal(
            proposal_id=proposal_id,
            title="Follow-up slice",
            description="Add a follow-up feature.",
        )

    result = anyio.run(run)

    assert result["success"] is True
    assert result["proposal_id"] == str(proposal_id)


def test_create_feature_item_requires_existing_feature(monkeypatch):
    """Verify create feature item requires existing feature."""
    feature_id = uuid.uuid4()

    async def fake_get(session, fid):
        """Provide a fake get."""
        return None

    monkeypatch.setattr(FeatureRepository, "get", fake_get)
    tools = ProductTools(database=FakeDatabase(), context=_context())

    async def run():
        """Run the async test body."""
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
    """Verify create feature item from feature."""
    feature_id = uuid.uuid4()
    feature = _feature(id=feature_id)
    item = _feature_item(feature_id=feature_id, order_index=2)
    captured = {}
    context = _context()

    async def fake_get(session, fid):
        """Provide a fake get."""
        return feature

    async def fake_get_proposal(session, proposal_id):
        """Provide a fake proposal lookup."""
        return _proposal(id=proposal_id, user_id=context.user_id)

    async def fake_create(session, **kwargs):
        """Provide a fake create."""
        captured.update(kwargs)
        return item

    monkeypatch.setattr(FeatureRepository, "get", fake_get)
    monkeypatch.setattr(ProductProposalRepository, "get", fake_get_proposal)
    monkeypatch.setattr(FeatureItemRepository, "create", fake_create)
    tools = ProductTools(database=FakeDatabase(), context=context)

    async def run():
        """Run the async test body."""
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


def test_create_feature_for_product_proposal_rejects_cross_user_proposal(monkeypatch):
    """Verify product tool refuses proposals owned by another user."""
    proposal_id = uuid.uuid4()
    context = _context()

    async def fake_get(session, pid):
        """Provide a fake get."""
        return _proposal(id=pid, user_id=uuid.uuid4(), status=ProductProposalStatus.approved)

    monkeypatch.setattr(ProductProposalRepository, "get", fake_get)
    tools = ProductTools(database=FakeDatabase(), context=context)

    async def run():
        """Run the async test body."""
        return await tools.create_feature_for_product_proposal(
            proposal_id=proposal_id,
            title="RAG",
            description="Add RAG capability.",
        )

    result = anyio.run(run)

    assert result == {
        "success": False,
        "message": "Proposal is not available in this task context.",
    }


def test_create_feature_item_rejects_cross_user_feature(monkeypatch):
    """Verify product tool refuses features owned by another user."""
    feature_id = uuid.uuid4()
    feature = _feature(id=feature_id)
    context = _context()

    async def fake_get(session, fid):
        """Provide a fake get."""
        return feature

    async def fake_get_proposal(session, proposal_id):
        """Provide a fake proposal lookup."""
        return _proposal(id=proposal_id, user_id=uuid.uuid4())

    monkeypatch.setattr(FeatureRepository, "get", fake_get)
    monkeypatch.setattr(ProductProposalRepository, "get", fake_get_proposal)
    tools = ProductTools(database=FakeDatabase(), context=context)

    async def run():
        """Run the async test body."""
        return await tools.create_feature_item(
            feature_id=feature_id,
            title="Knowledge base",
            description="Add a searchable knowledge base.",
        )

    result = anyio.run(run)

    assert result == {
        "success": False,
        "message": "Feature is not available in this task context.",
    }


def test_feature_item_repository_create_assigns_next_order_index(monkeypatch):
    """Verify feature item repository create assigns next order index."""
    session = FakeSession(max_order_index=3)
    feature_id = uuid.uuid4()
    captured = {}

    async def fake_sync_status_from_items(current_session, current_feature_id):
        """Provide a fake sync status from items."""
        captured["session"] = current_session
        captured["feature_id"] = current_feature_id
        return None

    monkeypatch.setattr(FeatureRepository, "sync_status_from_items", fake_sync_status_from_items)

    async def run():
        """Run the async test body."""
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
    """Verify feature repository sync status from items marks linked proposal completed."""
    proposal = _proposal(status=ProductProposalStatus.planned)
    feature = _feature(proposal_id=proposal.id, status=FeatureStatus.in_progress)
    session = FakeFeatureItemSyncSession(
        feature=feature,
        proposal=proposal,
        item_statuses=[FeatureItemStatus.completed, FeatureItemStatus.closed],
        sibling_feature_statuses=[FeatureStatus.closed],
    )

    async def run():
        """Run the async test body."""
        return await FeatureRepository.sync_status_from_items(session, feature.id)

    updated = anyio.run(run)

    assert updated.status == FeatureStatus.completed
    assert proposal.status == ProductProposalStatus.completed


def test_feature_repository_sync_status_from_items_reopens_linked_proposal_when_work_remains():
    """Verify feature repository sync status from items reopens linked proposal when work remains."""
    proposal = _proposal(status=ProductProposalStatus.completed)
    feature = _feature(proposal_id=proposal.id, status=FeatureStatus.completed)
    session = FakeFeatureItemSyncSession(
        feature=feature,
        proposal=proposal,
        item_statuses=[FeatureItemStatus.pending, FeatureItemStatus.closed],
        sibling_feature_statuses=[FeatureStatus.closed],
    )

    async def run():
        """Run the async test body."""
        return await FeatureRepository.sync_status_from_items(session, feature.id)

    updated = anyio.run(run)

    assert updated.status == FeatureStatus.planned
    assert proposal.status == ProductProposalStatus.planned


def test_proposal_create_and_response_allow_optional_structured_fields() -> None:
    """Verify optional structured proposal fields do not break legacy persistence."""
    from src.server.schemas import ProductProposalCreateRequest, ProductProposalResponse

    payload = ProductProposalCreateRequest(
        title=" Improve onboarding ",
        plan_type="growth",
        summary=" Help users reach value faster. ",
        answer="Legacy answer remains available.",
        problem_opportunity=" Users drop off. ",
        open_questions="   ",
    )

    assert payload.title == "Improve onboarding"
    assert payload.problem_opportunity == "Users drop off."
    assert payload.open_questions is None

    proposal = _proposal(
        problem_opportunity="Users drop off.",
        suggested_small_feature_breakdown="Ship the smallest walkthrough first.",
    )
    response = ProductProposalResponse.from_record(proposal)

    assert response.answer == "Create a clearer onboarding flow."
    assert response.problem_opportunity == "Users drop off."
    assert response.open_questions is None
    assert response.suggested_small_feature_breakdown == "Ship the smallest walkthrough first."
