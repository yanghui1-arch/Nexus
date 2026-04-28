from __future__ import annotations

import asyncio
import json
import sys
import types
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from fastapi import FastAPI


class _FakeCelery:
    def __init__(self, *args, **kwargs) -> None:
        self.conf: dict[str, Any] = {}

    def autodiscover_tasks(self, *args, **kwargs) -> None:
        return None


fake_celery_module = types.ModuleType('celery')
fake_celery_module.Celery = _FakeCelery
sys.modules.setdefault('celery', fake_celery_module)

import src.server.api.routes.tasks as tasks_routes
from src.server.api.routes.tasks import router as tasks_router
from src.server.postgres.models import AgentName, TaskStatus
from src.server.postgres.repositories import TaskRepository


class FakeDatabase:
    def __init__(self, session_obj: object | None = None) -> None:
        self._session_obj = session_obj if session_obj is not None else object()

    @asynccontextmanager
    async def session(self):
        yield self._session_obj


def _build_app(session_obj: object | None = None) -> FastAPI:
    app = FastAPI()
    app.state.database = FakeDatabase(session_obj)
    app.include_router(tasks_router)
    return app


def _make_task(
    *,
    question: str,
    status: TaskStatus,
    created_at: datetime,
    repo: str = 'owner/repo',
    project: str | None = 'workspace',
    agent: AgentName = AgentName.sophie,
    agent_instance_id: uuid.UUID | None = None,
    checkpoint: list[dict[str, Any] | str] | None = None,
) -> Any:
    started_at = created_at + timedelta(minutes=1)
    finished_at = (
        None
        if status in {TaskStatus.queued, TaskStatus.running, TaskStatus.waiting_for_merge}
        else created_at + timedelta(minutes=4)
    )
    return SimpleNamespace(
        id=uuid.uuid4(),
        agent=agent,
        agent_instance_id=agent_instance_id or uuid.uuid4(),
        question=question,
        repo=repo,
        project=project,
        status=status,
        result=None,
        error=None,
        checkpoint=checkpoint,
        created_at=created_at,
        updated_at=created_at + timedelta(minutes=2),
        started_at=started_at,
        finished_at=finished_at,
    )


def _make_settings() -> Any:
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
        return [older_task, newer_task]

    monkeypatch.setattr(TaskRepository, 'list', fake_list)

    async def run_request() -> httpx.Response:
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
        'question',
        'repo',
        'project',
        'status',
        'result',
        'error',
        'created_at',
        'updated_at',
        'started_at',
        'finished_at',
    }


def test_list_tasks_passes_filters_to_repository(monkeypatch: pytest.MonkeyPatch) -> None:
    session_obj = object()
    app = _build_app(session_obj)
    now = datetime.now(timezone.utc)
    agent_instance_id = uuid.uuid4()
    expected_task = _make_task(
        question='filtered task',
        status=TaskStatus.waiting_for_merge,
        created_at=now,
        repo='owner/nexus',
        project='web',
        agent_instance_id=agent_instance_id,
    )
    captured: dict[str, Any] = {}

    async def fake_list(session, **kwargs):
        captured['session'] = session
        captured.update(kwargs)
        return [expected_task]

    monkeypatch.setattr(TaskRepository, 'list', fake_list)

    async def run_request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url='http://testserver') as client:
            return await client.get(
                '/v1/tasks',
                params={
                    'agent_instance_id': str(agent_instance_id),
                    'status': 'waiting_for_merge',
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
            'question': expected_task.question,
            'repo': expected_task.repo,
            'project': expected_task.project,
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
        'status': TaskStatus.waiting_for_merge,
        'repo': 'owner/nexus',
        'project': 'web',
        'limit': 10,
    }


def test_consult_task_returns_process_reply(monkeypatch: pytest.MonkeyPatch) -> None:
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

    async def fake_get(session, task_id):
        assert task_id == task.id
        return task

    class FakeAgent:
        def __init__(self) -> None:
            self.checkpoint = None
            self.user_message = None
            self.closed = False

        async def report_current_process(self, *, checkpoint, user_message):
            self.checkpoint = checkpoint
            self.user_message = user_message
            return 'Agent consult reply'

        async def close(self) -> None:
            self.closed = True

    fake_agent = FakeAgent()

    def fake_create(**kwargs):
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
    monkeypatch.setattr(tasks_routes.Sophie, 'create', fake_create)

    async def run_request() -> httpx.Response:
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


def test_consult_task_uses_tela_agent_factory(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime.now(timezone.utc)
    task = _make_task(
        question='stabilize process tracking',
        status=TaskStatus.running,
        created_at=now - timedelta(minutes=20),
        repo='owner/nexus',
        project='web',
        agent=AgentName.tela,
        checkpoint=[
            {'role': 'system', 'content': 'System prompt'},
            {'role': 'user', 'content': 'Original task request'},
            {'role': 'assistant', 'content': 'Checkpointed progress'},
        ],
    )

    async def fake_get(session, task_id):
        assert task_id == task.id
        return task

    class FakeAgent:
        def __init__(self) -> None:
            self.checkpoint = None
            self.user_message = None
            self.closed = False

        async def report_current_process(self, *, checkpoint, user_message):
            self.checkpoint = checkpoint
            self.user_message = user_message
            return 'Agent consult reply'

        async def close(self) -> None:
            self.closed = True

    fake_agent = FakeAgent()

    def fake_create(**kwargs):
        assert kwargs == {
            'base_url': 'https://api.example.com/v1',
            'api_key': 'test-api-key',
            'model': 'gpt-test',
            'max_context': 4096,
            'github_repo': 'owner/nexus',
            'max_attempts': 8,
            'github_token': 'tela-token',
        }
        return fake_agent

    monkeypatch.setattr(TaskRepository, 'get', fake_get)
    monkeypatch.setattr(tasks_routes, 'get_settings', _make_settings)
    monkeypatch.setattr(tasks_routes.Tela, 'create', fake_create)

    async def run_request() -> httpx.Response:
        transport = httpx.ASGITransport(app=_build_app())
        async with httpx.AsyncClient(transport=transport, base_url='http://testserver') as client:
            return await client.post(
                f'/v1/tasks/{task.id}/consult',
                json={'message': 'What is the current progress?'},
            )

    response = asyncio.run(run_request())

    assert response.status_code == 200
    payload = response.json()
    assert payload['reply'] == 'Agent consult reply'
    assert payload['status'] == 'running'
    assert fake_agent.user_message == 'What is the current progress?'
    assert fake_agent.closed is True
    assert fake_agent.checkpoint == [
        {'role': 'system', 'content': 'System prompt'},
        {'role': 'user', 'content': 'Original task request'},
        {'role': 'assistant', 'content': 'Checkpointed progress'},
    ]
