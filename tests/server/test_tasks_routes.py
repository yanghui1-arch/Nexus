from __future__ import annotations

import asyncio
import sys
import types
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI


class _FakeCelery:
    def __init__(self, *args, **kwargs) -> None:
        """Initialize the test helper."""
        self.conf: dict[str, Any] = {}

    def autodiscover_tasks(self, *args, **kwargs) -> None:
        """Ignore Celery autodiscovery in tests."""
        return None


fake_celery_module = types.ModuleType('celery')
fake_celery_module.Celery = _FakeCelery
sys.modules.setdefault('celery', fake_celery_module)

import src.server.api.routes.tasks as tasks_routes
from src.server.api.dependencies import get_current_user
from src.server.api.routes.tasks import router as tasks_router
from src.server.postgres.models import (
    AgentName,
    TaskCategory,
    TaskStatus,
    TaskWorkItemStatus,
)
from src.server.postgres.repositories import (
    AgentInstanceRepository,
    TaskExecutionEventRepository,
    TaskRepository,
    TaskWorkItemRepository,
    WorkspaceRepository,
)


class FakeDatabase:
    def __init__(self, session_obj: object | None = None) -> None:
        """Initialize the test helper."""
        self._session_obj = session_obj if session_obj is not None else object()

    @asynccontextmanager
    async def session(self):
        """Return a fake database session."""
        yield self._session_obj


def _build_app(session_obj: object | None = None, runner_obj: object | None = None) -> FastAPI:
    """Build a FastAPI app for route tests."""
    app = FastAPI()
    app.state.database = FakeDatabase(session_obj)
    if runner_obj is not None:
        app.state.runner = runner_obj
    app.include_router(tasks_router)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=uuid.UUID("00000000-0000-0000-0000-000000000001"))
    return app


async def _fake_get_current_user_instance(session, agent_instance_id):
    """Return fake authenticated user and instance records."""
    return SimpleNamespace(
        id=agent_instance_id,
        user_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
    )


def _make_task(
    *,
    question: str,
    status: TaskStatus,
    created_at: datetime,
    category: TaskCategory = TaskCategory.coding,
    repo: str = 'owner/repo',
    project: str | None = 'workspace',
    agent: AgentName = AgentName.sophie,
    agent_instance_id: uuid.UUID | None = None,
    checkpoint: list[dict[str, Any] | str] | None = None,
    error: str | None = None,
) -> Any:
    """Create a task route record."""
    started_at = created_at + timedelta(minutes=1)
    finished_at = (
        None
        if status in {TaskStatus.queued, TaskStatus.running, TaskStatus.waiting_for_review}
        else created_at + timedelta(minutes=4)
    )
    return SimpleNamespace(
        id=uuid.uuid4(),
        agent=agent,
        agent_instance_id=agent_instance_id or uuid.uuid4(),
        category=category,
        question=question,
        repo=repo,
        project=project,
        external_issue_url=None,
        external_pull_request_url=None,
        status=status,
        result=None,
        error=error,
        checkpoint=checkpoint,
        created_at=created_at,
        updated_at=created_at + timedelta(minutes=2),
        started_at=started_at,
        finished_at=finished_at,
    )


def _make_settings() -> Any:
    """Create test server settings."""
    return SimpleNamespace(
        api_key='test-api-key',
        base_url='https://api.example.com/v1',
        model='gpt-test',
        max_context=4096,
        max_attempts=8,
        github_tokens={
            'sophie': 'sophie-token',
            'tela': 'tela-token',
        },
    )


def test_list_tasks_returns_newest_first(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify list tasks returns newest first."""
    now = datetime.now(timezone.utc)
    older_task = _make_task(
        question='older task',
        status=TaskStatus.queued,
        created_at=now - timedelta(hours=2),
    )
    newer_task = _make_task(
        question='newer task',
        status=TaskStatus.running,
        created_at=now - timedelta(minutes=10),
    )

    async def fake_list(session, **kwargs):
        """Provide a fake list."""
        return [older_task, newer_task]

    monkeypatch.setattr(TaskRepository, 'list', fake_list)
    monkeypatch.setattr(WorkspaceRepository, 'list_for_user', AsyncMock(return_value=[]))

    async def run_request() -> httpx.Response:
        """Run the request test body."""
        transport = httpx.ASGITransport(app=_build_app())
        async with httpx.AsyncClient(transport=transport, base_url='http://testserver') as client:
            return await client.get('/v1/tasks')

    response = asyncio.run(run_request())

    assert response.status_code == 200
    payload = response.json()
    assert [item['id'] for item in payload] == [str(newer_task.id), str(older_task.id)]
    assert set(payload[0]) == {
        'id',
        'agent',
        'agent_instance_id',
        'category',
        'question',
        'repo',
        'project',
        'external_issue_url',
        'external_pull_request_url',
        'status',
        'result',
        'error',
        'created_at',
        'updated_at',
        'started_at',
        'finished_at',
    }


def test_create_task_returns_category_from_persisted_task(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify create task returns category from persisted task."""
    now = datetime.now(timezone.utc)
    created_task = _make_task(
        question='ship a coding task',
        status=TaskStatus.queued,
        category=TaskCategory.coding,
        created_at=now,
    )
    runner = SimpleNamespace(submit_task=AsyncMock(return_value=created_task.id))

    async def fake_get(session, task_id, **kwargs):
        """Provide a fake get."""
        assert task_id == created_task.id
        return created_task

    async def fake_get_instance(session, agent_instance_id, **kwargs):
        """Provide a fake get instance."""
        assert agent_instance_id == created_task.agent_instance_id
        return SimpleNamespace(
            id=agent_instance_id,
            user_id=uuid.UUID('00000000-0000-0000-0000-000000000001'),
        )

    monkeypatch.setattr(TaskRepository, 'get', fake_get)
    monkeypatch.setattr(AgentInstanceRepository, 'get', fake_get_instance)

    async def run_request() -> httpx.Response:
        """Run the request test body."""
        transport = httpx.ASGITransport(app=_build_app(runner_obj=runner))
        async with httpx.AsyncClient(transport=transport, base_url='http://testserver') as client:
            return await client.post(
                '/v1/tasks',
                json={
                    'agent_instance_id': str(created_task.agent_instance_id),
                    'agent': created_task.agent.value,
                    'question': created_task.question,
                    'repo': created_task.repo,
                    'project': created_task.project,
                    'external_issue_url': None,
                },
            )

    response = asyncio.run(run_request())

    assert response.status_code == 202
    assert response.json() == {
        'task_id': str(created_task.id),
        'agent_instance_id': str(created_task.agent_instance_id),
        'category': created_task.category.value,
        'status': TaskStatus.queued.value,
    }
    runner.submit_task.assert_awaited_once()
    submission = runner.submit_task.await_args.args[0]
    assert submission.agent_instance_id == created_task.agent_instance_id
    assert submission.agent == AgentName(created_task.agent.value)
    assert submission.question == created_task.question
    assert submission.external_issue_url is None


def test_create_task_accepts_assistant_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify assistant instances can enter the normal review task runner."""
    now = datetime.now(timezone.utc)
    created_task = _make_task(
        question='review owner/repo#12',
        status=TaskStatus.queued,
        category=TaskCategory.review,
        created_at=now,
        agent=AgentName.assistant,
    )
    runner = SimpleNamespace(submit_task=AsyncMock(return_value=created_task.id))

    async def fake_get(session, task_id, **kwargs):
        """Provide fake repository lookups for instance and task records."""
        if task_id == created_task.id:
            return created_task
        return SimpleNamespace(
            id=created_task.agent_instance_id,
            user_id=uuid.UUID('00000000-0000-0000-0000-000000000001'),
        )

    monkeypatch.setattr(TaskRepository, 'get', fake_get)
    monkeypatch.setattr(AgentInstanceRepository, 'get', fake_get)

    async def run_request() -> httpx.Response:
        """Run the request test body."""
        transport = httpx.ASGITransport(app=_build_app(runner_obj=runner))
        async with httpx.AsyncClient(transport=transport, base_url='http://testserver') as client:
            return await client.post(
                '/v1/tasks',
                json={
                    'agent_instance_id': str(created_task.agent_instance_id),
                    'agent': 'assistant',
                    'question': created_task.question,
                    'external_issue_url': None,
                    'external_pull_request_url': 'https://github.com/owner/repo/pull/12',
                },
            )

    response = asyncio.run(run_request())

    assert response.status_code == 202
    assert response.json() == {
        'task_id': str(created_task.id),
        'agent_instance_id': str(created_task.agent_instance_id),
        'category': TaskCategory.review.value,
        'status': TaskStatus.queued.value,
    }
    runner.submit_task.assert_awaited_once()


def test_list_tasks_passes_filters_to_repository(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify list tasks passes filters to repository."""
    session_obj = object()
    app = _build_app(session_obj)
    now = datetime.now(timezone.utc)
    agent_instance_id = uuid.uuid4()
    expected_task = _make_task(
        question='filtered task',
        status=TaskStatus.waiting_for_review,
        created_at=now,
        repo='owner/nexus',
        project='web',
        agent_instance_id=agent_instance_id,
    )
    captured: dict[str, Any] = {}

    async def fake_list(session, **kwargs):
        """Provide a fake list."""
        captured['session'] = session
        captured.update(kwargs)
        return [expected_task]

    monkeypatch.setattr(TaskRepository, 'list', fake_list)
    monkeypatch.setattr(WorkspaceRepository, 'list_for_user', AsyncMock(return_value=[]))

    async def run_request() -> httpx.Response:
        """Run the request test body."""
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url='http://testserver') as client:
            return await client.get(
                '/v1/tasks',
                params={
                    'agent_instance_id': str(agent_instance_id),
                    'status': 'waiting_for_review',
                    'category': 'coding',
                    'repo': 'owner/nexus',
                    'project': 'web',
                    'limit': '10',
                },
            )

    response = asyncio.run(run_request())

    assert response.status_code == 200
    assert response.json() == [
        {
            'id': str(expected_task.id),
            'agent': expected_task.agent.value,
            'agent_instance_id': str(expected_task.agent_instance_id),
            'category': expected_task.category.value,
            'question': expected_task.question,
            'repo': expected_task.repo,
            'project': expected_task.project,
            'external_issue_url': None,
            'external_pull_request_url': None,
            'status': expected_task.status.value,
            'result': None,
            'error': None,
            'created_at': expected_task.created_at.isoformat().replace('+00:00', 'Z'),
            'updated_at': expected_task.updated_at.isoformat().replace('+00:00', 'Z'),
            'started_at': expected_task.started_at.isoformat().replace('+00:00', 'Z'),
            'finished_at': None,
        }
    ]
    assert captured == {
        'session': session_obj,
        'agent_instance_id': agent_instance_id,
        'status': TaskStatus.waiting_for_review,
        'category': TaskCategory.coding,
        'repo': 'owner/nexus',
        'project': 'web',
        'user_id': uuid.UUID('00000000-0000-0000-0000-000000000001'),
        'limit': 10,
    }


def test_list_task_events_returns_timeline(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify list task events returns execution events for an owned task."""
    now = datetime.now(timezone.utc)
    task = _make_task(question="events", status=TaskStatus.running, created_at=now)
    events = [
        SimpleNamespace(
            id=uuid.uuid4(),
            task_id=task.id,
            event_type="task_started",
            agent=AgentName.sophie,
            message="started",
            safe_metadata={"phase": "setup"},
            tokens=None,
            model=None,
            created_at=now,
        ),
        SimpleNamespace(
            id=uuid.uuid4(),
            task_id=task.id,
            event_type="model_usage",
            agent=None,
            message=None,
            safe_metadata=None,
            tokens=42,
            model="gpt-test",
            created_at=now + timedelta(seconds=1),
        ),
    ]
    captured: dict[str, Any] = {}

    async def fake_get_for_user(session, task_id, **kwargs):
        assert task_id == task.id
        return task

    async def fake_list_by_task(session, task_id, **kwargs):
        captured["task_id"] = task_id
        captured.update(kwargs)
        return events

    monkeypatch.setattr(TaskRepository, "get_for_user", fake_get_for_user)
    monkeypatch.setattr(TaskExecutionEventRepository, "list_by_task", fake_list_by_task)

    async def run_request() -> httpx.Response:
        transport = httpx.ASGITransport(app=_build_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.get(f"/v1/tasks/{task.id}/events", params={"limit": "2"})

    response = asyncio.run(run_request())

    assert response.status_code == 200
    payload = response.json()
    assert [item["event_type"] for item in payload] == ["task_started", "model_usage"]
    assert payload[0]["agent"] == "sophie"
    assert payload[0]["safe_metadata"] == {"phase": "setup"}
    assert payload[1]["tokens"] == 42
    assert payload[1]["model"] == "gpt-test"
    assert captured == {"task_id": task.id, "limit": 2}


def test_list_task_events_hides_unowned_task(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify task event access follows task ownership checks."""
    now = datetime.now(timezone.utc)
    task = _make_task(question="foreign events", status=TaskStatus.running, created_at=now)

    async def fake_get_for_user(session, task_id, **kwargs):
        return None

    list_mock = AsyncMock(return_value=[])
    monkeypatch.setattr(TaskRepository, "get_for_user", fake_get_for_user)
    monkeypatch.setattr(TaskExecutionEventRepository, "list_by_task", list_mock)

    async def run_request() -> httpx.Response:
        transport = httpx.ASGITransport(app=_build_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.get(f"/v1/tasks/{task.id}/events")

    response = asyncio.run(run_request())

    assert response.status_code == 404
    list_mock.assert_not_awaited()


def test_list_task_work_items(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify list task work items."""
    now = datetime.now(timezone.utc)
    task = _make_task(question='large task', status=TaskStatus.waiting_for_review, created_at=now)
    work_item = SimpleNamespace(
        id=uuid.uuid4(),
        task_id=task.id,
        order_index=1,
        title='Scoped change',
        description='Implement a review-sized slice.',
        status=TaskWorkItemStatus.ready_for_review,
        summary='Implemented slice.',
        base_commit='base',
        head_commit='head',
        local_path='/workspace/repo',
        created_at=now,
        updated_at=now,
        started_at=now,
        finished_at=None,
    )

    async def fake_get(session, task_id, **kwargs):
        """Provide a fake get."""
        assert task_id == task.id
        return task

    async def fake_list_by_task(session, task_id):
        """Provide a fake list by task."""
        assert task_id == task.id
        return [work_item]

    monkeypatch.setattr(TaskRepository, 'get', fake_get)
    monkeypatch.setattr(TaskWorkItemRepository, 'list_by_task', fake_list_by_task)
    monkeypatch.setattr(AgentInstanceRepository, 'get', _fake_get_current_user_instance)

    async def run_request() -> httpx.Response:
        """Run the request test body."""
        transport = httpx.ASGITransport(app=_build_app())
        async with httpx.AsyncClient(transport=transport, base_url='http://testserver') as client:
            return await client.get(f'/v1/tasks/{task.id}/work-items')

    response = asyncio.run(run_request())

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]['title'] == 'Scoped change'
    assert payload[0]['status'] == 'ready_for_review'


def test_update_task_status_closes_reviewable_task(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify update task status closes reviewable task."""
    now = datetime.now(timezone.utc)
    task = _make_task(question='close task', status=TaskStatus.waiting_for_review, created_at=now)
    closed_task = _make_task(question='close task', status=TaskStatus.closed, created_at=now)
    closed_task.id = task.id
    captured: dict[str, Any] = {}

    async def fake_get_task(session, task_id, **kwargs):
        """Provide a fake get task."""
        assert task_id == task.id
        return task

    async def fake_set_closed(session, task_id):
        """Provide a fake set closed."""
        captured['closed_task_id'] = task_id
        return closed_task

    monkeypatch.setattr(TaskRepository, 'get', fake_get_task)
    monkeypatch.setattr(TaskRepository, 'set_closed', fake_set_closed)
    monkeypatch.setattr(AgentInstanceRepository, 'get', _fake_get_current_user_instance)

    async def run_request() -> httpx.Response:
        """Run the request test body."""
        transport = httpx.ASGITransport(app=_build_app())
        async with httpx.AsyncClient(transport=transport, base_url='http://testserver') as client:
            return await client.patch(
                f'/v1/tasks/{task.id}/status',
                json={'status': 'closed'},
            )

    response = asyncio.run(run_request())

    assert response.status_code == 200
    assert response.json()['status'] == 'closed'
    assert captured['closed_task_id'] == task.id


def test_update_task_status_reopens_closed_task_for_review(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify update task status reopens closed task for review."""
    now = datetime.now(timezone.utc)
    task = _make_task(question='reopen task', status=TaskStatus.closed, created_at=now)
    reopened_task = _make_task(
        question='reopen task',
        status=TaskStatus.waiting_for_review,
        created_at=now,
    )
    reopened_task.id = task.id
    captured: dict[str, Any] = {}

    async def fake_get_task(session, task_id, **kwargs):
        """Provide a fake get task."""
        assert task_id == task.id
        return task

    async def fake_list_work_items(session, task_id):
        """Provide a fake list work items."""
        assert task_id == task.id
        return [
            SimpleNamespace(id=uuid.uuid4(), status=TaskWorkItemStatus.approved),
            SimpleNamespace(id=uuid.uuid4(), status=TaskWorkItemStatus.ready_for_review),
        ]

    async def fake_set_waiting_for_review(session, task_id, **kwargs):
        """Provide a fake set waiting for review."""
        captured['waiting_for_review_task_id'] = task_id
        captured['waiting_for_review_result'] = kwargs.get('result')
        return reopened_task

    monkeypatch.setattr(TaskRepository, 'get', fake_get_task)
    monkeypatch.setattr(TaskWorkItemRepository, 'list_by_task', fake_list_work_items)
    monkeypatch.setattr(TaskRepository, 'set_waiting_for_review', fake_set_waiting_for_review)
    monkeypatch.setattr(AgentInstanceRepository, 'get', _fake_get_current_user_instance)

    async def run_request() -> httpx.Response:
        """Run the request test body."""
        transport = httpx.ASGITransport(app=_build_app())
        async with httpx.AsyncClient(transport=transport, base_url='http://testserver') as client:
            return await client.patch(
                f'/v1/tasks/{task.id}/status',
                json={'status': 'waiting_for_review'},
            )

    response = asyncio.run(run_request())

    assert response.status_code == 200
    assert response.json()['status'] == 'waiting_for_review'
    assert captured['waiting_for_review_task_id'] == task.id
    assert captured['waiting_for_review_result'] is None


def test_update_task_status_reopens_closed_task_for_review_when_work_items_are_all_approved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify update task status reopens closed task for review when work items are all approved."""
    now = datetime.now(timezone.utc)
    task = _make_task(question='reopen merge task', status=TaskStatus.closed, created_at=now)
    reopened_task = _make_task(
        question='reopen merge task',
        status=TaskStatus.waiting_for_review,
        created_at=now,
    )
    reopened_task.id = task.id
    captured: dict[str, Any] = {}

    async def fake_get_task(session, task_id, **kwargs):
        """Provide a fake get task."""
        assert task_id == task.id
        return task

    async def fake_list_work_items(session, task_id):
        """Provide a fake list work items."""
        assert task_id == task.id
        return [
            SimpleNamespace(id=uuid.uuid4(), status=TaskWorkItemStatus.approved),
            SimpleNamespace(id=uuid.uuid4(), status=TaskWorkItemStatus.approved),
        ]

    async def fake_set_waiting_for_review(session, task_id, **kwargs):
        """Provide a fake set waiting for review."""
        captured['waiting_for_review_task_id'] = task_id
        captured['waiting_for_review_result'] = kwargs.get('result')
        return reopened_task

    monkeypatch.setattr(TaskRepository, 'get', fake_get_task)
    monkeypatch.setattr(TaskWorkItemRepository, 'list_by_task', fake_list_work_items)
    monkeypatch.setattr(TaskRepository, 'set_waiting_for_review', fake_set_waiting_for_review)
    monkeypatch.setattr(AgentInstanceRepository, 'get', _fake_get_current_user_instance)

    async def run_request() -> httpx.Response:
        """Run the request test body."""
        transport = httpx.ASGITransport(app=_build_app())
        async with httpx.AsyncClient(transport=transport, base_url='http://testserver') as client:
            return await client.patch(
                f'/v1/tasks/{task.id}/status',
                json={'status': 'waiting_for_review'},
            )

    response = asyncio.run(run_request())

    assert response.status_code == 200
    assert response.json()['status'] == 'waiting_for_review'
    assert captured['waiting_for_review_task_id'] == task.id
    assert captured['waiting_for_review_result'] is None


def test_consult_task_returns_process_reply(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify consult task returns process reply."""
    now = datetime.now(timezone.utc)
    task = _make_task(
        question='stabilize process tracking',
        status=TaskStatus.running,
        created_at=now - timedelta(minutes=20),
        repo='owner/nexus',
        project='web',
        checkpoint=[
            {'role': 'system', 'content': 'System prompt'},
            {'role': 'user', 'content': 'Original task request'},
            {'role': 'assistant', 'content': 'Checkpointed progress'},
        ],
    )

    async def fake_get(session, task_id, **kwargs):
        """Provide a fake get."""
        assert task_id == task.id
        return task

    class FakeAgent:
        def __init__(self) -> None:
            """Initialize the test helper."""
            self.checkpoint = None
            self.user_message = None
            self.closed = False

        async def report_current_process(self, *, checkpoint, user_message):
            """Return a fake progress report."""
            self.checkpoint = checkpoint
            self.user_message = user_message
            return 'Agent consult reply'

        async def close(self) -> None:
            """Close a fake service."""
            self.closed = True

    fake_agent = FakeAgent()

    def fake_create(**kwargs):
        """Provide a fake create."""
        assert kwargs == {
            'base_url': 'https://api.example.com/v1',
            'api_key': 'test-api-key',
            'model': 'gpt-test',
            'max_context': 4096,
            'github_repo': 'owner/nexus',
            'max_attempts': 8,
            'github_token': 'sophie-token',
        }
        return fake_agent

    monkeypatch.setattr(TaskRepository, 'get', fake_get)
    monkeypatch.setattr(tasks_routes, 'get_settings', _make_settings)
    monkeypatch.setattr(AgentInstanceRepository, 'get', _fake_get_current_user_instance)
    monkeypatch.setattr(WorkspaceRepository, 'get_by_agent_instance_id', AsyncMock(return_value=None))
    monkeypatch.setattr(tasks_routes.Sophie, 'create', fake_create)

    async def run_request() -> httpx.Response:
        """Run the request test body."""
        transport = httpx.ASGITransport(app=_build_app())
        async with httpx.AsyncClient(transport=transport, base_url='http://testserver') as client:
            return await client.post(
                f'/v1/tasks/{task.id}/consult',
                json={'message': 'What is the latest process update?'},
            )

    response = asyncio.run(run_request())

    assert response.status_code == 200
    payload = response.json()
    assert payload['task_id'] == str(task.id)
    assert payload['status'] == 'running'
    assert payload['reply'] == 'Agent consult reply'
    assert fake_agent.user_message == 'What is the latest process update?'
    assert fake_agent.closed is True
    assert fake_agent.checkpoint == [
        {'role': 'system', 'content': 'System prompt'},
        {'role': 'user', 'content': 'Original task request'},
        {'role': 'assistant', 'content': 'Checkpointed progress'},
    ]


def test_task_stats_return_unknown_empty_state_for_existing_task_without_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify tasks with no execution events return zero/unknown statistics."""
    now = datetime.now(timezone.utc)
    task = _make_task(question='empty stats', status=TaskStatus.queued, created_at=now)

    async def fake_get_for_user(session, task_id, **kwargs):
        """Provide a fake owned task."""
        assert task_id == task.id
        assert kwargs == {'user_id': uuid.UUID('00000000-0000-0000-0000-000000000001')}
        return task

    async def fake_list_events(session, task_id, **kwargs):
        """Provide no execution events."""
        assert task_id == task.id
        return []

    monkeypatch.setattr(TaskRepository, 'get_for_user', fake_get_for_user)
    monkeypatch.setattr(TaskExecutionEventRepository, 'list_by_task', fake_list_events)

    async def run_request() -> httpx.Response:
        """Run the request test body."""
        transport = httpx.ASGITransport(app=_build_app())
        async with httpx.AsyncClient(transport=transport, base_url='http://testserver') as client:
            return await client.get(f'/v1/tasks/{task.id}/stats')

    response = asyncio.run(run_request())

    assert response.status_code == 200
    assert response.json() == {
        'event_count': 0,
        'total_tokens': 0,
        'first_event_at': None,
        'last_event_at': None,
        'duration_seconds': None,
        'tool_call_count': 0,
        'last_checkpoint_at': None,
        'latest_error': None,
        'model': 'unknown',
    }


def test_task_stats_include_tool_checkpoint_and_error_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify task stats include requested observability aggregate fields."""
    now = datetime.now(timezone.utc)
    task = _make_task(
        question='observe stats',
        status=TaskStatus.failed,
        created_at=now - timedelta(minutes=10),
        checkpoint=[{'role': 'assistant', 'content': 'checkpoint'}],
        error='task failed',
    )
    task.updated_at = now - timedelta(minutes=1)
    events = [
        SimpleNamespace(
            event_type='llm_response',
            message='model replied',
            tokens=10,
            model='gpt-test',
            created_at=now - timedelta(minutes=4),
        ),
        SimpleNamespace(
            event_type='tool_call',
            message='ran tool',
            tokens=2,
            model='gpt-test',
            created_at=now - timedelta(minutes=3),
        ),
        SimpleNamespace(
            event_type='error',
            message='latest event error',
            tokens=None,
            model='gpt-test',
            created_at=now - timedelta(minutes=2),
        ),
    ]

    async def fake_get_for_user(session, task_id, **kwargs):
        """Provide a fake owned task."""
        assert task_id == task.id
        return task

    async def fake_list_events(session, task_id, **kwargs):
        """Provide execution events."""
        assert task_id == task.id
        return events

    monkeypatch.setattr(TaskRepository, 'get_for_user', fake_get_for_user)
    monkeypatch.setattr(TaskExecutionEventRepository, 'list_by_task', fake_list_events)

    async def run_request() -> httpx.Response:
        """Run the request test body."""
        transport = httpx.ASGITransport(app=_build_app())
        async with httpx.AsyncClient(transport=transport, base_url='http://testserver') as client:
            return await client.get(f'/v1/tasks/{task.id}/stats')

    response = asyncio.run(run_request())

    assert response.status_code == 200
    assert response.json() == {
        'event_count': 3,
        'total_tokens': 12,
        'first_event_at': events[0].created_at.isoformat().replace('+00:00', 'Z'),
        'last_event_at': events[-1].created_at.isoformat().replace('+00:00', 'Z'),
        'duration_seconds': 120.0,
        'tool_call_count': 1,
        'last_checkpoint_at': task.updated_at.isoformat().replace('+00:00', 'Z'),
        'latest_error': 'latest event error',
        'model': 'gpt-test',
    }

def test_retry_task_from_checkpoint_dispatches_same_task(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify checkpoint retry queues and dispatches the existing task."""
    now = datetime.now(timezone.utc)
    task = _make_task(
        question="retry me",
        status=TaskStatus.failed,
        created_at=now,
        checkpoint=[{"role": "assistant", "content": "progress"}],
    )
    runner = SimpleNamespace(dispatch_task=AsyncMock(return_value=True))
    captured: dict[str, Any] = {}

    async def fake_get_for_user(session, task_id, **kwargs):
        captured["user_id"] = kwargs["user_id"]
        return task

    async def fake_no_running(session, agent_instance_id, **kwargs):
        captured["agent_instance_id"] = agent_instance_id
        captured["exclude_task_id"] = kwargs["exclude_task_id"]
        return None

    async def fake_queue(session, task_id):
        captured["queued_task_id"] = task_id
        task.started_at = None
        return task

    async def fake_event(session, **kwargs):
        captured["event"] = kwargs
        return SimpleNamespace(id=uuid.uuid4())

    monkeypatch.setattr(TaskRepository, "get_for_user", fake_get_for_user)
    monkeypatch.setattr(TaskRepository, "get_running_for_agent_instance", fake_no_running)
    monkeypatch.setattr(TaskRepository, "queue_checkpoint_retry", fake_queue)
    monkeypatch.setattr(TaskRepository, "create_execution_event", fake_event)

    async def run_request() -> httpx.Response:
        transport = httpx.ASGITransport(app=_build_app(runner_obj=runner))
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.post(f"/v1/tasks/{task.id}/retry-from-checkpoint")

    response = asyncio.run(run_request())

    assert response.status_code == 202
    assert response.json() == {
        "task_id": str(task.id),
        "agent_instance_id": str(task.agent_instance_id),
        "category": task.category.value,
        "status": TaskStatus.queued.value,
    }
    assert captured["queued_task_id"] == task.id
    assert captured["exclude_task_id"] == task.id
    assert task.started_at is None
    assert captured["event"]["event_type"] == "PROCESS"
    assert captured["event"]["safe_metadata"] == {"source": "retry_from_checkpoint"}
    runner.dispatch_task.assert_awaited_once_with(task.id)


def test_retry_task_from_checkpoint_hides_unowned_task(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify retry access follows task ownership."""
    task_id = uuid.uuid4()
    runner = SimpleNamespace(dispatch_task=AsyncMock(return_value=True))
    monkeypatch.setattr(TaskRepository, "get_for_user", AsyncMock(return_value=None))
    queue_mock = AsyncMock()
    monkeypatch.setattr(TaskRepository, "queue_checkpoint_retry", queue_mock)

    async def run_request() -> httpx.Response:
        transport = httpx.ASGITransport(app=_build_app(runner_obj=runner))
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.post(f"/v1/tasks/{task_id}/retry-from-checkpoint")

    response = asyncio.run(run_request())

    assert response.status_code == 404
    queue_mock.assert_not_awaited()
    runner.dispatch_task.assert_not_awaited()


def test_retry_task_from_checkpoint_rejects_non_failed_task(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify only failed tasks can be retried."""
    task = _make_task(
        question="running",
        status=TaskStatus.running,
        created_at=datetime.now(timezone.utc),
        checkpoint=[{"role": "assistant", "content": "progress"}],
    )
    runner = SimpleNamespace(dispatch_task=AsyncMock(return_value=True))
    monkeypatch.setattr(TaskRepository, "get_for_user", AsyncMock(return_value=task))

    async def run_request() -> httpx.Response:
        transport = httpx.ASGITransport(app=_build_app(runner_obj=runner))
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.post(f"/v1/tasks/{task.id}/retry-from-checkpoint")

    response = asyncio.run(run_request())

    assert response.status_code == 409
    assert response.json()["detail"] == "Only failed tasks can be retried from checkpoint"
    runner.dispatch_task.assert_not_awaited()

def test_retry_task_from_checkpoint_rejects_missing_checkpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify failed tasks need a saved checkpoint for retry."""
    task = _make_task(question="no checkpoint", status=TaskStatus.failed, created_at=datetime.now(timezone.utc))
    runner = SimpleNamespace(dispatch_task=AsyncMock(return_value=True))
    monkeypatch.setattr(TaskRepository, "get_for_user", AsyncMock(return_value=task))

    async def run_request() -> httpx.Response:
        transport = httpx.ASGITransport(app=_build_app(runner_obj=runner))
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.post(f"/v1/tasks/{task.id}/retry-from-checkpoint")

    response = asyncio.run(run_request())

    assert response.status_code == 409
    assert response.json()["detail"] == "Task has no checkpoint to retry from"
    runner.dispatch_task.assert_not_awaited()


def test_retry_task_from_checkpoint_conflicts_with_running_task(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify retry is blocked when the agent instance is occupied."""
    now = datetime.now(timezone.utc)
    task = _make_task(
        question="retry me",
        status=TaskStatus.failed,
        created_at=now,
        checkpoint=[{"role": "assistant", "content": "progress"}],
    )
    running_task = _make_task(question="busy", status=TaskStatus.running, created_at=now)
    runner = SimpleNamespace(dispatch_task=AsyncMock(return_value=True))
    monkeypatch.setattr(TaskRepository, "get_for_user", AsyncMock(return_value=task))
    monkeypatch.setattr(TaskRepository, "get_running_for_agent_instance", AsyncMock(return_value=running_task))
    queue_mock = AsyncMock()
    monkeypatch.setattr(TaskRepository, "queue_checkpoint_retry", queue_mock)

    async def run_request() -> httpx.Response:
        transport = httpx.ASGITransport(app=_build_app(runner_obj=runner))
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.post(f"/v1/tasks/{task.id}/retry-from-checkpoint")

    response = asyncio.run(run_request())

    assert response.status_code == 409
    assert response.json()["detail"] == "Agent instance already has a running task"
    queue_mock.assert_not_awaited()
    runner.dispatch_task.assert_not_awaited()


def test_retry_task_from_checkpoint_returns_dispatch_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify broker failures are returned to the user."""
    task = _make_task(
        question="retry me",
        status=TaskStatus.failed,
        created_at=datetime.now(timezone.utc),
        checkpoint=[{"role": "assistant", "content": "progress"}],
    )
    runner = SimpleNamespace(dispatch_task=AsyncMock(side_effect=tasks_routes.TaskDispatchError("Dispatch failed: broker")))
    monkeypatch.setattr(TaskRepository, "get_for_user", AsyncMock(return_value=task))
    monkeypatch.setattr(TaskRepository, "get_running_for_agent_instance", AsyncMock(return_value=None))
    monkeypatch.setattr(TaskRepository, "queue_checkpoint_retry", AsyncMock(return_value=task))
    monkeypatch.setattr(TaskRepository, "create_execution_event", AsyncMock(return_value=SimpleNamespace(id=uuid.uuid4())))

    async def run_request() -> httpx.Response:
        transport = httpx.ASGITransport(app=_build_app(runner_obj=runner))
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.post(f"/v1/tasks/{task.id}/retry-from-checkpoint")

    response = asyncio.run(run_request())

    assert response.status_code == 503
    assert response.json()["detail"] == "Dispatch failed: broker"
    runner.dispatch_task.assert_awaited_once_with(task.id)


def test_get_task_includes_recovery_for_failed_checkpointed_task(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify task detail includes recovery guidance for failed checkpointed tasks."""
    now = datetime.now(timezone.utc)
    task = _make_task(
        question="recover failed task",
        status=TaskStatus.failed,
        created_at=now,
        checkpoint=[{"role": "assistant", "content": "progress"}],
        error="Tool timeout",
    )

    async def fake_get_for_user(session, task_id, **kwargs):
        """Provide a fake owned task."""
        assert task_id == task.id
        return task

    monkeypatch.setattr(TaskRepository, "get_for_user", fake_get_for_user)
    monkeypatch.setattr(WorkspaceRepository, "get_by_agent_instance_id", AsyncMock(return_value=None))

    async def run_request() -> httpx.Response:
        """Run the request test body."""
        transport = httpx.ASGITransport(app=_build_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.get(f"/v1/tasks/{task.id}")

    response = asyncio.run(run_request())

    assert response.status_code == 200
    recovery = response.json()["recovery"]
    assert recovery["visible"] is True
    assert recovery["has_checkpoint"] is True
    assert recovery["failure_summary"] == "Tool timeout"
    assert recovery["can_retry_from_checkpoint"] is False
    assert recovery["duplicate_side_effects_confirmation_required"] is True


def test_retry_task_requires_confirmation_and_submits_fresh_task(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify generic retry task confirmation and fresh task submission."""
    now = datetime.now(timezone.utc)
    task = _make_task(
        question="retry me",
        status=TaskStatus.failed,
        created_at=now,
        checkpoint=[{"role": "assistant", "content": "progress"}],
        error="failed",
    )
    retried_task = _make_task(question=task.question, status=TaskStatus.queued, created_at=now)
    retried_task.id = uuid.uuid4()
    retried_task.agent_instance_id = task.agent_instance_id
    captured: dict[str, Any] = {}

    async def fake_get_for_user(session, task_id, **kwargs):
        """Provide a fake owned task."""
        assert task_id == task.id
        return task

    async def fake_create_task_record(submission, **kwargs):
        """Capture retry task creation."""
        captured["submission"] = submission
        captured["create_session"] = kwargs["session"]
        return retried_task

    async def fake_dispatch_task(task_id):
        """Capture retry dispatch."""
        captured["dispatch_task_id"] = task_id
        return True

    runner = SimpleNamespace(
        create_task_record=AsyncMock(side_effect=fake_create_task_record),
        dispatch_task=AsyncMock(side_effect=fake_dispatch_task),
    )
    session_obj = SimpleNamespace(commit=AsyncMock(), refresh=AsyncMock())
    monkeypatch.setattr(TaskRepository, "get_for_user", fake_get_for_user)

    async def run_request(payload: dict[str, Any]) -> httpx.Response:
        """Run the request test body."""
        transport = httpx.ASGITransport(app=_build_app(session_obj=session_obj, runner_obj=runner))
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.post(f"/v1/tasks/{task.id}/retry", json=payload)

    rejected = asyncio.run(run_request({}))
    accepted = asyncio.run(run_request({"confirm_duplicate_side_effects": True}))

    assert rejected.status_code == 409
    assert accepted.status_code == 202
    assert accepted.json()["task_id"] == str(retried_task.id)
    submission = captured["submission"]
    assert submission.question == task.question
    assert not hasattr(submission, "checkpoint")
    assert captured["create_session"] is session_obj
    assert retried_task.checkpoint is None
    assert captured["dispatch_task_id"] == retried_task.id
    session_obj.commit.assert_awaited_once()
    session_obj.refresh.assert_awaited_once_with(retried_task)

