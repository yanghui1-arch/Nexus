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
from src.server.postgres.models import (
    AgentName,
    TaskStatus,
    TaskWorkItemStatus,
    VirtualPullRequestLineSide,
    VirtualPullRequestReviewDecision,
    VirtualPullRequestStatus,
)
from src.server.postgres.repositories import (
    TaskRepository,
    TaskWorkItemRepository,
    VirtualPullRequestRepository,
    _extract_code_snapshot,
)


class FakeDatabase:
    def __init__(self, session_obj: object | None = None) -> None:
        self._session_obj = session_obj if session_obj is not None else object()

    @asynccontextmanager
    async def session(self):
        yield self._session_obj


def _build_app(session_obj: object | None = None, runner_obj: object | None = None) -> FastAPI:
    app = FastAPI()
    app.state.database = FakeDatabase(session_obj)
    if runner_obj is not None:
        app.state.runner = runner_obj
    app.include_router(tasks_router)
    return app


def test_extract_code_snapshot_from_virtual_pr_diff() -> None:
    raw_diff = (
        'diff --git a/src/file.py b/src/file.py\n'
        '--- a/src/file.py\n'
        '+++ b/src/file.py\n'
        '@@ -1,3 +1,4 @@\n'
        ' keep old\n'
        '-remove me\n'
        '+add me\n'
        '+add also\n'
        ' keep tail\n'
    )

    snapshot = _extract_code_snapshot(
        raw_diff,
        file_path='src/file.py',
        start_line=2,
        end_line=3,
        line_side=VirtualPullRequestLineSide.new,
    )

    assert snapshot == '+add me\n+add also'


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
        if status in {TaskStatus.queued, TaskStatus.running, TaskStatus.waiting_for_review, TaskStatus.waiting_for_merge}
        else created_at + timedelta(minutes=4)
    )
    return SimpleNamespace(
        id=uuid.uuid4(),
        agent=agent,
        agent_instance_id=agent_instance_id or uuid.uuid4(),
        question=question,
        repo=repo,
        project=project,
        external_issue_url=None,
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
        'external_issue_url',
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
            'external_issue_url': None,
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


def test_list_task_work_items(monkeypatch: pytest.MonkeyPatch) -> None:
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

    async def fake_get(session, task_id):
        assert task_id == task.id
        return task

    async def fake_list_by_task(session, task_id):
        assert task_id == task.id
        return [work_item]

    monkeypatch.setattr(TaskRepository, 'get', fake_get)
    monkeypatch.setattr(TaskWorkItemRepository, 'list_by_task', fake_list_by_task)

    async def run_request() -> httpx.Response:
        transport = httpx.ASGITransport(app=_build_app())
        async with httpx.AsyncClient(transport=transport, base_url='http://testserver') as client:
            return await client.get(f'/v1/tasks/{task.id}/work-items')

    response = asyncio.run(run_request())

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]['title'] == 'Scoped change'
    assert payload[0]['status'] == 'ready_for_review'


def test_update_task_status_closes_reviewable_task(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime.now(timezone.utc)
    task = _make_task(question='close task', status=TaskStatus.waiting_for_review, created_at=now)
    closed_task = _make_task(question='close task', status=TaskStatus.closed, created_at=now)
    closed_task.id = task.id
    captured: dict[str, Any] = {}

    async def fake_get_task(session, task_id):
        assert task_id == task.id
        return task

    async def fake_set_closed(session, task_id):
        captured['closed_task_id'] = task_id
        return closed_task

    monkeypatch.setattr(TaskRepository, 'get', fake_get_task)
    monkeypatch.setattr(TaskRepository, 'set_closed', fake_set_closed)

    async def run_request() -> httpx.Response:
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
    now = datetime.now(timezone.utc)
    task = _make_task(question='reopen task', status=TaskStatus.closed, created_at=now)
    reopened_task = _make_task(
        question='reopen task',
        status=TaskStatus.waiting_for_review,
        created_at=now,
    )
    reopened_task.id = task.id
    captured: dict[str, Any] = {}

    async def fake_get_task(session, task_id):
        assert task_id == task.id
        return task

    async def fake_list_work_items(session, task_id):
        assert task_id == task.id
        return [
            SimpleNamespace(id=uuid.uuid4(), status=TaskWorkItemStatus.approved),
            SimpleNamespace(id=uuid.uuid4(), status=TaskWorkItemStatus.ready_for_review),
        ]

    async def fake_set_waiting_for_review(session, task_id, **kwargs):
        captured['waiting_for_review_task_id'] = task_id
        captured['waiting_for_review_result'] = kwargs.get('result')
        return reopened_task

    monkeypatch.setattr(TaskRepository, 'get', fake_get_task)
    monkeypatch.setattr(TaskWorkItemRepository, 'list_by_task', fake_list_work_items)
    monkeypatch.setattr(TaskRepository, 'set_waiting_for_review', fake_set_waiting_for_review)

    async def run_request() -> httpx.Response:
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


def test_update_task_status_reopens_closed_task_for_merge(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime.now(timezone.utc)
    task = _make_task(question='reopen merge task', status=TaskStatus.closed, created_at=now)
    reopened_task = _make_task(
        question='reopen merge task',
        status=TaskStatus.waiting_for_merge,
        created_at=now,
    )
    reopened_task.id = task.id
    captured: dict[str, Any] = {}

    async def fake_get_task(session, task_id):
        assert task_id == task.id
        return task

    async def fake_list_work_items(session, task_id):
        assert task_id == task.id
        return [
            SimpleNamespace(id=uuid.uuid4(), status=TaskWorkItemStatus.approved),
            SimpleNamespace(id=uuid.uuid4(), status=TaskWorkItemStatus.approved),
        ]

    async def fake_set_waiting_for_merge(session, task_id, **kwargs):
        captured['waiting_for_merge_task_id'] = task_id
        captured['waiting_for_merge_result'] = kwargs.get('result')
        return reopened_task

    monkeypatch.setattr(TaskRepository, 'get', fake_get_task)
    monkeypatch.setattr(TaskWorkItemRepository, 'list_by_task', fake_list_work_items)
    monkeypatch.setattr(TaskRepository, 'set_waiting_for_merge', fake_set_waiting_for_merge)

    async def run_request() -> httpx.Response:
        transport = httpx.ASGITransport(app=_build_app())
        async with httpx.AsyncClient(transport=transport, base_url='http://testserver') as client:
            return await client.patch(
                f'/v1/tasks/{task.id}/status',
                json={'status': 'waiting_for_review'},
            )

    response = asyncio.run(run_request())

    assert response.status_code == 200
    assert response.json()['status'] == 'waiting_for_merge'
    assert captured['waiting_for_merge_task_id'] == task.id
    assert captured['waiting_for_merge_result'] is None


def test_get_virtual_pr_diff(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime.now(timezone.utc)
    task = _make_task(question='large task', status=TaskStatus.waiting_for_review, created_at=now)
    virtual_pr = SimpleNamespace(
        id=uuid.uuid4(),
        task_id=task.id,
        work_item_id=uuid.uuid4(),
        base_commit='base',
        head_commit='head',
        diff='diff --git a/file.py b/file.py',
    )

    async def fake_get_task(session, task_id):
        assert task_id == task.id
        return task

    async def fake_get_virtual_pr(session, virtual_pr_id):
        assert virtual_pr_id == virtual_pr.id
        return virtual_pr

    monkeypatch.setattr(TaskRepository, 'get', fake_get_task)
    monkeypatch.setattr(VirtualPullRequestRepository, 'get', fake_get_virtual_pr)

    async def run_request() -> httpx.Response:
        transport = httpx.ASGITransport(app=_build_app())
        async with httpx.AsyncClient(transport=transport, base_url='http://testserver') as client:
            return await client.get(f'/v1/tasks/{task.id}/virtual-prs/{virtual_pr.id}/diff')

    response = asyncio.run(run_request())

    assert response.status_code == 200
    assert response.json()['diff'] == 'diff --git a/file.py b/file.py'


def test_review_virtual_pr_approval_waits_without_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime.now(timezone.utc)
    task = _make_task(question='large task', status=TaskStatus.waiting_for_review, created_at=now)
    virtual_pr = SimpleNamespace(
        id=uuid.uuid4(),
        task_id=task.id,
        work_item_id=uuid.uuid4(),
        status=VirtualPullRequestStatus.ready_for_review,
    )
    review = SimpleNamespace(
        id=uuid.uuid4(),
        task_id=task.id,
        virtual_pr_id=virtual_pr.id,
        decision=VirtualPullRequestReviewDecision.approved,
        reviewer='reviewer',
        comment='looks good',
        created_at=now,
    )
    captured: dict[str, Any] = {}

    async def fake_get_task(session, task_id):
        assert task_id == task.id
        return task

    async def fake_get_virtual_pr(session, virtual_pr_id):
        assert virtual_pr_id == virtual_pr.id
        return virtual_pr

    async def fake_add_review(session, **kwargs):
        captured['review'] = kwargs
        return review

    async def fake_mark_approved(session, work_item_id):
        captured['approved_work_item_id'] = work_item_id
        return None

    async def fake_list_work_items(session, task_id):
        assert task_id == task.id
        return [
            SimpleNamespace(id=virtual_pr.work_item_id, status=TaskWorkItemStatus.approved),
            SimpleNamespace(id=uuid.uuid4(), status=TaskWorkItemStatus.ready_for_review),
        ]

    async def fake_set_waiting_for_review(session, task_id, **kwargs):
        captured['waiting_task_id'] = task_id
        captured['waiting_result'] = kwargs.get('result')
        return task

    class FakeRunner:
        async def dispatch_existing_task(self, task_id, *, recovered=False):
            raise AssertionError('approval should not dispatch execution')

    monkeypatch.setattr(TaskRepository, 'get', fake_get_task)
    monkeypatch.setattr(VirtualPullRequestRepository, 'get', fake_get_virtual_pr)
    monkeypatch.setattr(VirtualPullRequestRepository, 'add_review', fake_add_review)
    monkeypatch.setattr(TaskWorkItemRepository, 'mark_approved', fake_mark_approved)
    monkeypatch.setattr(TaskWorkItemRepository, 'list_by_task', fake_list_work_items)
    monkeypatch.setattr(TaskRepository, 'set_waiting_for_review', fake_set_waiting_for_review)

    async def run_request() -> httpx.Response:
        transport = httpx.ASGITransport(app=_build_app(runner_obj=FakeRunner()))
        async with httpx.AsyncClient(transport=transport, base_url='http://testserver') as client:
            return await client.patch(
                f'/v1/tasks/{task.id}/virtual-prs/{virtual_pr.id}/review',
                json={'decision': 'approved', 'reviewer': 'reviewer', 'comment': 'looks good'},
            )

    response = asyncio.run(run_request())

    assert response.status_code == 200
    assert response.json()['decision'] == 'approved'
    assert captured['review']['decision'] == VirtualPullRequestReviewDecision.approved
    assert captured['approved_work_item_id'] == virtual_pr.work_item_id
    assert captured['waiting_task_id'] == task.id
    assert captured['waiting_result'] is None
    assert 'dispatched' not in captured


def test_review_virtual_pr_marks_waiting_for_merge_when_all_approved(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime.now(timezone.utc)
    task = _make_task(question='large task', status=TaskStatus.waiting_for_review, created_at=now)
    virtual_pr = SimpleNamespace(
        id=uuid.uuid4(),
        task_id=task.id,
        work_item_id=uuid.uuid4(),
        status=VirtualPullRequestStatus.ready_for_review,
    )
    review = SimpleNamespace(
        id=uuid.uuid4(),
        task_id=task.id,
        virtual_pr_id=virtual_pr.id,
        decision=VirtualPullRequestReviewDecision.approved,
        reviewer='reviewer',
        comment='looks good',
        created_at=now,
    )
    captured: dict[str, Any] = {}

    async def fake_get_task(session, task_id):
        assert task_id == task.id
        return task

    async def fake_get_virtual_pr(session, virtual_pr_id):
        assert virtual_pr_id == virtual_pr.id
        return virtual_pr

    async def fake_add_review(session, **kwargs):
        captured['review'] = kwargs
        return review

    async def fake_mark_approved(session, work_item_id):
        captured['approved_work_item_id'] = work_item_id
        return None

    async def fake_list_work_items(session, task_id):
        assert task_id == task.id
        return [
            SimpleNamespace(id=virtual_pr.work_item_id, status=TaskWorkItemStatus.approved),
            SimpleNamespace(id=uuid.uuid4(), status=TaskWorkItemStatus.approved),
        ]

    async def fake_set_waiting_for_merge(session, task_id, **kwargs):
        captured['waiting_for_merge_task_id'] = task_id
        captured['waiting_for_merge_result'] = kwargs.get('result')
        return task

    class FakeRunner:
        async def dispatch_existing_task(self, task_id, *, recovered=False):
            raise AssertionError('approval should not dispatch execution')

    monkeypatch.setattr(TaskRepository, 'get', fake_get_task)
    monkeypatch.setattr(VirtualPullRequestRepository, 'get', fake_get_virtual_pr)
    monkeypatch.setattr(VirtualPullRequestRepository, 'add_review', fake_add_review)
    monkeypatch.setattr(TaskWorkItemRepository, 'mark_approved', fake_mark_approved)
    monkeypatch.setattr(TaskWorkItemRepository, 'list_by_task', fake_list_work_items)
    monkeypatch.setattr(TaskRepository, 'set_waiting_for_merge', fake_set_waiting_for_merge)

    async def run_request() -> httpx.Response:
        transport = httpx.ASGITransport(app=_build_app(runner_obj=FakeRunner()))
        async with httpx.AsyncClient(transport=transport, base_url='http://testserver') as client:
            return await client.patch(
                f'/v1/tasks/{task.id}/virtual-prs/{virtual_pr.id}/review',
                json={'decision': 'approved', 'reviewer': 'reviewer', 'comment': 'looks good'},
            )

    response = asyncio.run(run_request())

    assert response.status_code == 200
    assert response.json()['decision'] == 'approved'
    assert captured['review']['decision'] == VirtualPullRequestReviewDecision.approved
    assert captured['approved_work_item_id'] == virtual_pr.work_item_id
    assert captured['waiting_for_merge_task_id'] == task.id
    assert captured['waiting_for_merge_result'] is None


def test_review_virtual_pr_close_only_closes_small_pr(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime.now(timezone.utc)
    task = _make_task(question='large task', status=TaskStatus.waiting_for_review, created_at=now)
    virtual_pr = SimpleNamespace(
        id=uuid.uuid4(),
        task_id=task.id,
        work_item_id=uuid.uuid4(),
        status=VirtualPullRequestStatus.ready_for_review,
    )
    review = SimpleNamespace(
        id=uuid.uuid4(),
        task_id=task.id,
        virtual_pr_id=virtual_pr.id,
        decision=VirtualPullRequestReviewDecision.closed,
        reviewer='reviewer',
        comment=None,
        created_at=now,
    )
    captured: dict[str, Any] = {}

    async def fake_get_task(session, task_id):
        assert task_id == task.id
        return task

    async def fake_get_virtual_pr(session, virtual_pr_id):
        assert virtual_pr_id == virtual_pr.id
        return virtual_pr

    async def fake_add_review(session, **kwargs):
        captured['review'] = kwargs
        return review

    async def fake_mark_closed(session, work_item_id):
        captured['closed_work_item_id'] = work_item_id
        return None

    async def fake_list_work_items(session, task_id):
        assert task_id == task.id
        return [
            SimpleNamespace(id=virtual_pr.work_item_id, status=TaskWorkItemStatus.closed),
            SimpleNamespace(id=uuid.uuid4(), status=TaskWorkItemStatus.ready_for_review),
        ]

    async def fake_set_waiting_for_review(session, task_id, **kwargs):
        captured['waiting_for_review_task_id'] = task_id
        return task

    async def fail_set_closed(session, task_id):
        raise AssertionError('closing a virtual PR should not close the parent task')

    monkeypatch.setattr(TaskRepository, 'get', fake_get_task)
    monkeypatch.setattr(VirtualPullRequestRepository, 'get', fake_get_virtual_pr)
    monkeypatch.setattr(VirtualPullRequestRepository, 'add_review', fake_add_review)
    monkeypatch.setattr(TaskWorkItemRepository, 'mark_closed', fake_mark_closed)
    monkeypatch.setattr(TaskWorkItemRepository, 'list_by_task', fake_list_work_items)
    monkeypatch.setattr(TaskRepository, 'set_waiting_for_review', fake_set_waiting_for_review)
    monkeypatch.setattr(TaskRepository, 'set_closed', fail_set_closed)

    async def run_request() -> httpx.Response:
        transport = httpx.ASGITransport(app=_build_app())
        async with httpx.AsyncClient(transport=transport, base_url='http://testserver') as client:
            return await client.patch(
                f'/v1/tasks/{task.id}/virtual-prs/{virtual_pr.id}/review',
                json={'decision': 'closed', 'reviewer': 'reviewer'},
            )

    response = asyncio.run(run_request())

    assert response.status_code == 200
    assert response.json()['decision'] == 'closed'
    assert captured['review']['decision'] == VirtualPullRequestReviewDecision.closed
    assert captured['closed_work_item_id'] == virtual_pr.work_item_id
    assert captured['waiting_for_review_task_id'] == task.id


def test_review_virtual_pr_reopen_records_activity_and_reopens_small_pr(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime.now(timezone.utc)
    task = _make_task(question='large task', status=TaskStatus.closed, created_at=now)
    virtual_pr = SimpleNamespace(
        id=uuid.uuid4(),
        task_id=task.id,
        work_item_id=uuid.uuid4(),
        status=VirtualPullRequestStatus.closed,
    )
    review = SimpleNamespace(
        id=uuid.uuid4(),
        task_id=task.id,
        virtual_pr_id=virtual_pr.id,
        decision=VirtualPullRequestReviewDecision.reopened,
        reviewer='reviewer',
        comment=None,
        created_at=now,
    )
    captured: dict[str, Any] = {}

    async def fake_get_task(session, task_id):
        assert task_id == task.id
        return task

    async def fake_get_virtual_pr(session, virtual_pr_id):
        assert virtual_pr_id == virtual_pr.id
        return virtual_pr

    async def fake_add_review(session, **kwargs):
        captured['review'] = kwargs
        return review

    async def fake_reopen_for_review(session, work_item_id):
        captured['reopened_work_item_id'] = work_item_id
        return None

    async def fake_list_work_items(session, task_id):
        assert task_id == task.id
        return [
            SimpleNamespace(id=virtual_pr.work_item_id, status=TaskWorkItemStatus.ready_for_review),
            SimpleNamespace(id=uuid.uuid4(), status=TaskWorkItemStatus.closed),
        ]

    async def fake_set_waiting_for_review(session, task_id, **kwargs):
        captured['waiting_for_review_task_id'] = task_id
        return task

    monkeypatch.setattr(TaskRepository, 'get', fake_get_task)
    monkeypatch.setattr(VirtualPullRequestRepository, 'get', fake_get_virtual_pr)
    monkeypatch.setattr(VirtualPullRequestRepository, 'add_review', fake_add_review)
    monkeypatch.setattr(TaskWorkItemRepository, 'reopen_for_review', fake_reopen_for_review)
    monkeypatch.setattr(TaskWorkItemRepository, 'list_by_task', fake_list_work_items)
    monkeypatch.setattr(TaskRepository, 'set_waiting_for_review', fake_set_waiting_for_review)

    async def run_request() -> httpx.Response:
        transport = httpx.ASGITransport(app=_build_app())
        async with httpx.AsyncClient(transport=transport, base_url='http://testserver') as client:
            return await client.patch(
                f'/v1/tasks/{task.id}/virtual-prs/{virtual_pr.id}/review',
                json={'decision': 'reopened', 'reviewer': 'reviewer'},
            )

    response = asyncio.run(run_request())

    assert response.status_code == 200
    assert response.json()['decision'] == 'reopened'
    assert captured['review']['decision'] == VirtualPullRequestReviewDecision.reopened
    assert captured['reopened_work_item_id'] == virtual_pr.work_item_id
    assert captured['waiting_for_review_task_id'] == task.id


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


def test_list_review_queue_returns_reviewable_tasks_with_pr_counts(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime.now(timezone.utc)
    task_one = _make_task(question='review one', status=TaskStatus.waiting_for_review, created_at=now)
    task_two = _make_task(question='review two', status=TaskStatus.waiting_for_merge, created_at=now - timedelta(minutes=5))

    async def fake_list_review_queue(session, *, limit):
        assert limit == 25
        return [task_one, task_two]

    async def fake_list_virtual_prs(session, task_id):
        if task_id == task_one.id:
            return [SimpleNamespace(id=uuid.uuid4()), SimpleNamespace(id=uuid.uuid4())]
        return [SimpleNamespace(id=uuid.uuid4())]

    monkeypatch.setattr(TaskRepository, 'list_review_queue', fake_list_review_queue)
    monkeypatch.setattr(VirtualPullRequestRepository, 'list_by_task', fake_list_virtual_prs)

    async def run_request() -> httpx.Response:
        transport = httpx.ASGITransport(app=_build_app())
        async with httpx.AsyncClient(transport=transport, base_url='http://testserver') as client:
            return await client.get('/v1/tasks/review-queue', params={'limit': '25'})

    response = asyncio.run(run_request())

    assert response.status_code == 200
    assert response.json() == [
        {
            'task': {
                'id': str(task_one.id),
                'agent': task_one.agent.value,
                'agent_instance_id': str(task_one.agent_instance_id),
                'question': task_one.question,
                'repo': task_one.repo,
                'project': task_one.project,
                'external_issue_url': None,
                'status': task_one.status.value,
                'result': None,
                'error': None,
                'created_at': task_one.created_at.isoformat().replace('+00:00', 'Z'),
                'updated_at': task_one.updated_at.isoformat().replace('+00:00', 'Z'),
                'started_at': task_one.started_at.isoformat().replace('+00:00', 'Z'),
                'finished_at': None,
            },
            'virtual_pr_count': 2,
        },
        {
            'task': {
                'id': str(task_two.id),
                'agent': task_two.agent.value,
                'agent_instance_id': str(task_two.agent_instance_id),
                'question': task_two.question,
                'repo': task_two.repo,
                'project': task_two.project,
                'external_issue_url': None,
                'status': task_two.status.value,
                'result': None,
                'error': None,
                'created_at': task_two.created_at.isoformat().replace('+00:00', 'Z'),
                'updated_at': task_two.updated_at.isoformat().replace('+00:00', 'Z'),
                'started_at': task_two.started_at.isoformat().replace('+00:00', 'Z'),
                'finished_at': None,
            },
            'virtual_pr_count': 1,
        },
    ]


def test_get_task_review_summary_returns_task_work_items_and_virtual_prs(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime.now(timezone.utc)
    task = _make_task(question='review summary', status=TaskStatus.waiting_for_review, created_at=now)
    work_item = SimpleNamespace(
        id=uuid.uuid4(),
        task_id=task.id,
        order_index=1,
        title='Slice one',
        description='Do slice one',
        status=TaskWorkItemStatus.ready_for_review,
        summary='Ready',
        base_commit='base',
        head_commit='head',
        local_path='/workspace/repo',
        created_at=now,
        updated_at=now,
        started_at=now,
        finished_at=None,
    )
    virtual_pr = SimpleNamespace(
        id=uuid.uuid4(),
        task_id=task.id,
        work_item_id=work_item.id,
        status='ready_for_review',
        base_commit='base',
        head_commit='head',
        summary='PR summary',
        changed_files=['src/file.py'],
        additions=10,
        deletions=2,
        created_at=now,
        updated_at=now,
    )

    async def fake_get_task(session, task_id):
        assert task_id == task.id
        return task

    async def fake_list_work_items(session, task_id):
        assert task_id == task.id
        return [work_item]

    async def fake_list_virtual_prs(session, task_id):
        assert task_id == task.id
        return [virtual_pr]

    monkeypatch.setattr(TaskRepository, 'get', fake_get_task)
    monkeypatch.setattr(TaskWorkItemRepository, 'list_by_task', fake_list_work_items)
    monkeypatch.setattr(VirtualPullRequestRepository, 'list_by_task', fake_list_virtual_prs)

    async def run_request() -> httpx.Response:
        transport = httpx.ASGITransport(app=_build_app())
        async with httpx.AsyncClient(transport=transport, base_url='http://testserver') as client:
            return await client.get(f'/v1/tasks/{task.id}/review-summary')

    response = asyncio.run(run_request())

    assert response.status_code == 200
    payload = response.json()
    assert payload['task']['id'] == str(task.id)
    assert payload['work_items'][0]['title'] == 'Slice one'
    assert payload['virtual_prs'][0]['summary'] == 'PR summary'


def test_get_virtual_pr_detail_returns_reviews_and_threads(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime.now(timezone.utc)
    task = _make_task(question='detail task', status=TaskStatus.waiting_for_review, created_at=now)
    work_item_id = uuid.uuid4()
    virtual_pr_id = uuid.uuid4()
    virtual_pr = SimpleNamespace(
        id=virtual_pr_id,
        task_id=task.id,
        work_item_id=work_item_id,
        status='ready_for_review',
        base_commit='base',
        head_commit='head',
        summary='PR body',
        changed_files=['src/file.py'],
        additions=8,
        deletions=1,
        diff='diff --git a/src/file.py b/src/file.py',
        created_at=now,
        updated_at=now,
    )
    work_item = SimpleNamespace(
        id=work_item_id,
        task_id=task.id,
        order_index=1,
        title='Slice one',
        description='Do slice one',
        status=TaskWorkItemStatus.ready_for_review,
        summary='Ready',
        base_commit='base',
        head_commit='head',
        local_path='/workspace/repo',
        created_at=now,
        updated_at=now,
        started_at=now,
        finished_at=None,
    )
    review = SimpleNamespace(
        id=uuid.uuid4(),
        task_id=task.id,
        virtual_pr_id=virtual_pr_id,
        decision=VirtualPullRequestReviewDecision.commented,
        reviewer='reviewer',
        comment='looks fine',
        created_at=now,
    )
    thread_id = uuid.uuid4()
    thread = SimpleNamespace(
        id=thread_id,
        task_id=task.id,
        virtual_pr_id=virtual_pr_id,
        kind='inline',
        status='open',
        file_path='src/file.py',
        start_line=10,
        end_line=12,
        line_side='new',
        diff_hunk='@@ -1,1 +1,3 @@',
        code_snapshot=' line 10\n+line 11\n+line 12',
        created_by='reviewer',
        created_at=now,
        updated_at=now,
    )
    comment = SimpleNamespace(
        id=uuid.uuid4(),
        thread_id=thread_id,
        parent_comment_id=None,
        author='reviewer',
        body='nit',
        created_at=now,
        updated_at=now,
    )

    async def fake_get_task(session, task_id):
        assert task_id == task.id
        return task

    async def fake_get_virtual_pr(session, request_virtual_pr_id):
        assert request_virtual_pr_id == virtual_pr_id
        return virtual_pr

    async def fake_get_work_item(session, request_work_item_id):
        assert request_work_item_id == work_item_id
        return work_item

    async def fake_list_reviews(session, request_virtual_pr_id):
        assert request_virtual_pr_id == virtual_pr_id
        return [review]

    async def fake_list_threads(session, request_virtual_pr_id):
        assert request_virtual_pr_id == virtual_pr_id
        return [thread]

    async def fake_list_comments(session, thread_ids):
        assert thread_ids == [thread_id]
        return [comment]

    monkeypatch.setattr(TaskRepository, 'get', fake_get_task)
    monkeypatch.setattr(VirtualPullRequestRepository, 'get', fake_get_virtual_pr)
    monkeypatch.setattr(TaskWorkItemRepository, 'get', fake_get_work_item)
    monkeypatch.setattr(VirtualPullRequestRepository, 'list_reviews_by_virtual_pr', fake_list_reviews)
    monkeypatch.setattr(tasks_routes.VirtualPullRequestThreadRepository, 'list_by_virtual_pr', fake_list_threads)
    monkeypatch.setattr(tasks_routes.VirtualPullRequestCommentRepository, 'list_by_thread_ids', fake_list_comments)

    async def run_request() -> httpx.Response:
        transport = httpx.ASGITransport(app=_build_app())
        async with httpx.AsyncClient(transport=transport, base_url='http://testserver') as client:
            return await client.get(f'/v1/tasks/{task.id}/virtual-prs/{virtual_pr_id}')

    response = asyncio.run(run_request())

    assert response.status_code == 200
    payload = response.json()
    assert payload['task']['id'] == str(task.id)
    assert payload['work_item']['title'] == 'Slice one'
    assert payload['virtual_pr']['id'] == str(virtual_pr_id)
    assert payload['diff'] == 'diff --git a/src/file.py b/src/file.py'
    assert payload['reviews'][0]['decision'] == 'commented'
    assert payload['threads'][0]['code_snapshot'] == ' line 10\n+line 11\n+line 12'
    assert payload['threads'][0]['comments'][0]['body'] == 'nit'


def test_create_virtual_pr_thread_returns_thread_with_initial_comment(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime.now(timezone.utc)
    task = _make_task(question='thread task', status=TaskStatus.waiting_for_review, created_at=now)
    virtual_pr_id = uuid.uuid4()
    thread = SimpleNamespace(
        id=uuid.uuid4(),
        task_id=task.id,
        virtual_pr_id=virtual_pr_id,
        kind='inline',
        status='open',
        file_path='src/file.py',
        start_line=3,
        end_line=5,
        line_side='new',
        diff_hunk='@@ -1,1 +1,3 @@',
        code_snapshot='+selected\n+code\n+here',
        created_by='reviewer',
        created_at=now,
        updated_at=now,
    )
    comment = SimpleNamespace(
        id=uuid.uuid4(),
        thread_id=thread.id,
        parent_comment_id=None,
        author='reviewer',
        body='please check',
        created_at=now,
        updated_at=now,
    )
    captured: dict[str, Any] = {}

    async def fake_get_task(session, task_id):
        assert task_id == task.id
        return task

    async def fake_create_thread(session, **kwargs):
        captured.update(kwargs)
        return thread, comment

    monkeypatch.setattr(TaskRepository, 'get', fake_get_task)
    monkeypatch.setattr(tasks_routes.VirtualPullRequestThreadRepository, 'create', fake_create_thread)

    async def run_request() -> httpx.Response:
        transport = httpx.ASGITransport(app=_build_app())
        async with httpx.AsyncClient(transport=transport, base_url='http://testserver') as client:
            return await client.post(
                f'/v1/tasks/{task.id}/virtual-prs/{virtual_pr_id}/threads',
                json={
                    'kind': 'inline',
                    'created_by': 'reviewer',
                    'body': 'please check',
                    'file_path': 'src/file.py',
                    'start_line': 3,
                    'end_line': 5,
                    'line_side': 'new',
                    'diff_hunk': '@@ -1,1 +1,3 @@',
                },
            )

    response = asyncio.run(run_request())

    assert response.status_code == 201
    payload = response.json()
    assert payload['id'] == str(thread.id)
    assert payload['code_snapshot'] == '+selected\n+code\n+here'
    assert payload['comments'][0]['body'] == 'please check'
    assert captured['virtual_pr_id'] == virtual_pr_id
    assert captured['body'] == 'please check'


def test_create_virtual_pr_comment_returns_comment(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime.now(timezone.utc)
    task = _make_task(question='comment task', status=TaskStatus.waiting_for_review, created_at=now)
    virtual_pr_id = uuid.uuid4()
    thread_id = uuid.uuid4()
    virtual_pr = SimpleNamespace(id=virtual_pr_id, task_id=task.id)
    thread = SimpleNamespace(id=thread_id, virtual_pr_id=virtual_pr_id)
    comment = SimpleNamespace(
        id=uuid.uuid4(),
        thread_id=thread_id,
        parent_comment_id=None,
        author='reviewer',
        body='follow up',
        created_at=now,
        updated_at=now,
    )

    async def fake_get_task(session, task_id):
        assert task_id == task.id
        return task

    async def fake_get_virtual_pr(session, request_virtual_pr_id):
        assert request_virtual_pr_id == virtual_pr_id
        return virtual_pr

    async def fake_get_thread(session, request_thread_id):
        assert request_thread_id == thread_id
        return thread

    async def fake_add_comment(session, **kwargs):
        assert kwargs == {
            'thread_id': thread_id,
            'author': 'reviewer',
            'parent_comment_id': None,
            'body': 'follow up',
        }
        return comment

    monkeypatch.setattr(TaskRepository, 'get', fake_get_task)
    monkeypatch.setattr(VirtualPullRequestRepository, 'get', fake_get_virtual_pr)
    monkeypatch.setattr(tasks_routes.VirtualPullRequestThreadRepository, 'get', fake_get_thread)
    monkeypatch.setattr(tasks_routes.VirtualPullRequestThreadRepository, 'add_comment', fake_add_comment)

    async def run_request() -> httpx.Response:
        transport = httpx.ASGITransport(app=_build_app())
        async with httpx.AsyncClient(transport=transport, base_url='http://testserver') as client:
            return await client.post(
                f'/v1/tasks/{task.id}/virtual-prs/{virtual_pr_id}/threads/{thread_id}/comments',
                json={'author': 'reviewer', 'body': 'follow up'},
            )

    response = asyncio.run(run_request())

    assert response.status_code == 201
    assert response.json()['body'] == 'follow up'


def test_create_virtual_pr_comment_supports_nested_reply(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime.now(timezone.utc)
    task = _make_task(question='reply task', status=TaskStatus.waiting_for_review, created_at=now)
    virtual_pr_id = uuid.uuid4()
    thread_id = uuid.uuid4()
    parent_comment_id = uuid.uuid4()
    virtual_pr = SimpleNamespace(id=virtual_pr_id, task_id=task.id)
    thread = SimpleNamespace(id=thread_id, virtual_pr_id=virtual_pr_id)
    comment = SimpleNamespace(
        id=uuid.uuid4(),
        thread_id=thread_id,
        parent_comment_id=parent_comment_id,
        author='reviewer',
        body='reply here',
        created_at=now,
        updated_at=now,
    )

    async def fake_get_task(session, task_id):
        assert task_id == task.id
        return task

    async def fake_get_virtual_pr(session, request_virtual_pr_id):
        assert request_virtual_pr_id == virtual_pr_id
        return virtual_pr

    async def fake_get_thread(session, request_thread_id):
        assert request_thread_id == thread_id
        return thread

    async def fake_add_comment(session, **kwargs):
        assert kwargs == {
            'thread_id': thread_id,
            'author': 'reviewer',
            'parent_comment_id': parent_comment_id,
            'body': 'reply here',
        }
        return comment

    monkeypatch.setattr(TaskRepository, 'get', fake_get_task)
    monkeypatch.setattr(VirtualPullRequestRepository, 'get', fake_get_virtual_pr)
    monkeypatch.setattr(tasks_routes.VirtualPullRequestThreadRepository, 'get', fake_get_thread)
    monkeypatch.setattr(tasks_routes.VirtualPullRequestThreadRepository, 'add_comment', fake_add_comment)

    async def run_request() -> httpx.Response:
        transport = httpx.ASGITransport(app=_build_app())
        async with httpx.AsyncClient(transport=transport, base_url='http://testserver') as client:
            return await client.post(
                f'/v1/tasks/{task.id}/virtual-prs/{virtual_pr_id}/threads/{thread_id}/comments',
                json={
                    'author': 'reviewer',
                    'parent_comment_id': str(parent_comment_id),
                    'body': 'reply here',
                },
            )

    response = asyncio.run(run_request())

    assert response.status_code == 201
    payload = response.json()
    assert payload['body'] == 'reply here'
    assert payload['parent_comment_id'] == str(parent_comment_id)


def test_review_virtual_pr_comment_does_not_dispatch_or_requeue(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime.now(timezone.utc)
    task = _make_task(question='comment only', status=TaskStatus.waiting_for_review, created_at=now)
    virtual_pr = SimpleNamespace(
        id=uuid.uuid4(),
        task_id=task.id,
        work_item_id=uuid.uuid4(),
        status=VirtualPullRequestStatus.ready_for_review,
    )
    review = SimpleNamespace(
        id=uuid.uuid4(),
        task_id=task.id,
        virtual_pr_id=virtual_pr.id,
        decision=VirtualPullRequestReviewDecision.commented,
        reviewer='reviewer',
        comment='note only',
        created_at=now,
    )

    async def fake_get_task(session, task_id):
        assert task_id == task.id
        return task

    async def fake_get_virtual_pr(session, virtual_pr_id):
        assert virtual_pr_id == virtual_pr.id
        return virtual_pr

    async def fake_add_review(session, **kwargs):
        return review

    async def fail_mark_approved(session, work_item_id):
        raise AssertionError('comment-only review should not approve work items')

    async def fail_set_waiting_for_review(session, task_id, **kwargs):
        raise AssertionError('comment-only review should not move task to waiting_for_review')

    async def fail_set_waiting_for_merge(session, task_id, **kwargs):
        raise AssertionError('comment-only review should not move task to waiting_for_merge')

    class FakeRunner:
        async def dispatch_existing_task(self, task_id, *, recovered=False):
            raise AssertionError('comment-only review should not dispatch execution')

    monkeypatch.setattr(TaskRepository, 'get', fake_get_task)
    monkeypatch.setattr(VirtualPullRequestRepository, 'get', fake_get_virtual_pr)
    monkeypatch.setattr(VirtualPullRequestRepository, 'add_review', fake_add_review)
    monkeypatch.setattr(TaskWorkItemRepository, 'mark_approved', fail_mark_approved)
    monkeypatch.setattr(TaskRepository, 'set_waiting_for_review', fail_set_waiting_for_review)
    monkeypatch.setattr(TaskRepository, 'set_waiting_for_merge', fail_set_waiting_for_merge)

    async def run_request() -> httpx.Response:
        transport = httpx.ASGITransport(app=_build_app(runner_obj=FakeRunner()))
        async with httpx.AsyncClient(transport=transport, base_url='http://testserver') as client:
            return await client.patch(
                f'/v1/tasks/{task.id}/virtual-prs/{virtual_pr.id}/review',
                json={'decision': 'commented', 'reviewer': 'reviewer', 'comment': 'note only'},
            )

    response = asyncio.run(run_request())

    assert response.status_code == 200
    assert response.json()['decision'] == 'commented'
