import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from src.agents.base.agent import BaseAgentResponse
from src.server.celery import execution
from src.server.postgres.models import TaskWorkItemStatus
from src.server.postgres.repositories import TaskWorkItemRepository, VirtualPullRequestRepository


class FakeAgent:
    def __init__(self) -> None:
        self.work = AsyncMock(return_value=BaseAgentResponse(response="done", sop=None))
        self.closed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def close(self) -> None:
        self.closed = True


def make_task(**overrides):
    values = {
        "id": "task-id",
        "repo": "owner/repo",
        "question": "do the task",
        "requested_current_session_ctx": [{"role": "assistant", "content": "current"}],
        "requested_history_session_ctx": [{"role": "user", "content": "history"}],
        "checkpoint": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_run_agent_resumes_from_checkpoint_when_recovered(monkeypatch):
    checkpoint = [
        {"role": "system", "content": "checkpoint system"},
        {"role": "user", "content": "original task"},
    ]
    task = make_task(checkpoint=checkpoint)
    fake_agent = FakeAgent()

    monkeypatch.setattr(execution, "_build_agent", lambda **_: fake_agent)

    result = asyncio.run(
        execution._run_agent(
            task=task,
            on_progress=None,
            settings=SimpleNamespace(),
            workspace_key="workspace",
            github_repo="owner/repo",
            recovered=True,
        )
    )

    assert result.response == "done"
    fake_agent.work.assert_awaited_once_with(
        question="do the task",
        current_session_ctx=[{"role": "assistant", "content": "current"}],
        history_session_ctx=[{"role": "user", "content": "history"}],
        update_process_callback=None,
        from_checkpoint=True,
        checkpoint=[
            {"role": "system", "content": "checkpoint system"},
            {"role": "user", "content": "original task"},
        ],
    )
    assert fake_agent.closed is True


class FakeDatabase:
    def session(self):
        return self

    async def __aenter__(self):
        return object()

    async def __aexit__(self, *args):
        return None


def test_run_agent_uses_fresh_context_without_recovered_checkpoint(monkeypatch):
    task = make_task(checkpoint=[{"role": "system", "content": "old checkpoint"}])
    fake_agent = FakeAgent()

    monkeypatch.setattr(execution, "_build_agent", lambda **_: fake_agent)

    asyncio.run(
        execution._run_agent(
            task=task,
            on_progress=None,
            settings=SimpleNamespace(),
            workspace_key="workspace",
            github_repo="owner/repo",
            recovered=False,
        )
    )

    fake_agent.work.assert_awaited_once_with(
        question="do the task",
        current_session_ctx=[{"role": "assistant", "content": "current"}],
        history_session_ctx=[{"role": "user", "content": "history"}],
        update_process_callback=None,
    )


def test_run_agent_workflow_small_task_passthrough(monkeypatch):
    task = make_task()

    async def no_work_items(session, task_id):
        return []

    async def all_approved(session, task_id):
        return False

    async def no_running(session, task_id):
        return None

    async def no_next(session, task_id):
        return None

    async def fake_run_agent(**kwargs):
        return BaseAgentResponse(response="final pr opened", sop=None)

    monkeypatch.setattr(TaskWorkItemRepository, "list_by_task", no_work_items)
    monkeypatch.setattr(TaskWorkItemRepository, "all_approved", all_approved)
    monkeypatch.setattr(TaskWorkItemRepository, "get_running", no_running)
    monkeypatch.setattr(TaskWorkItemRepository, "get_next_for_execution", no_next)
    monkeypatch.setattr(execution, "_run_agent", fake_run_agent)

    outcome = asyncio.run(
        execution._run_agent_workflow(
            database=FakeDatabase(),
            task=task,
            on_progress=None,
            settings=SimpleNamespace(),
            workspace_key="workspace",
            github_repo="owner/repo",
            recovered=False,
        )
    )

    assert outcome.status == "waiting_for_merge"
    assert outcome.response == "final pr opened"


def test_run_agent_workflow_pauses_when_work_item_is_ready(monkeypatch):
    task = make_task()
    pending_item = SimpleNamespace(id="item-id", order_index=1, title="One", description="Do one")
    running_item = SimpleNamespace(
        id="item-id",
        order_index=1,
        title="One",
        description="Do one",
        status=TaskWorkItemStatus.running,
    )
    ready_item = SimpleNamespace(
        id="item-id",
        order_index=1,
        title="One",
        description="Do one",
        status=TaskWorkItemStatus.ready_for_review,
    )

    async def list_items(session, task_id):
        return [pending_item]

    async def all_approved(session, task_id):
        return False

    async def no_running(session, task_id):
        return None

    async def next_item(session, task_id):
        return pending_item

    async def set_running(session, work_item_id):
        return running_item

    async def get_item(session, work_item_id):
        return ready_item

    async def get_virtual_pr(session, work_item_id):
        return SimpleNamespace(id="virtual-pr-id")

    async def fake_run_agent(**kwargs):
        assert "finish_current_task_work_item" in kwargs["question_override"]
        return BaseAgentResponse(response="ready", sop=None)

    monkeypatch.setattr(TaskWorkItemRepository, "list_by_task", list_items)
    monkeypatch.setattr(TaskWorkItemRepository, "all_approved", all_approved)
    monkeypatch.setattr(TaskWorkItemRepository, "get_running", no_running)
    monkeypatch.setattr(TaskWorkItemRepository, "get_next_for_execution", next_item)
    monkeypatch.setattr(TaskWorkItemRepository, "set_running", set_running)
    monkeypatch.setattr(TaskWorkItemRepository, "get", get_item)
    monkeypatch.setattr(VirtualPullRequestRepository, "get_by_work_item", get_virtual_pr)
    monkeypatch.setattr(execution, "_run_agent", fake_run_agent)

    outcome = asyncio.run(
        execution._run_agent_workflow(
            database=FakeDatabase(),
            task=task,
            on_progress=None,
            settings=SimpleNamespace(),
            workspace_key="workspace",
            github_repo="owner/repo",
            recovered=False,
        )
    )

    assert outcome.status == "waiting"
    assert outcome.response == "ready"


def test_run_agent_workflow_final_pr_when_all_work_items_approved(monkeypatch):
    task = make_task()
    approved_item = SimpleNamespace(
        id="item-id",
        order_index=1,
        title="One",
        description="Do one",
        summary="Done",
        status=TaskWorkItemStatus.approved,
    )

    async def list_items(session, task_id):
        return [approved_item]

    async def all_approved(session, task_id):
        return True

    async def no_running(session, task_id):
        return None

    async def no_next(session, task_id):
        return None

    async def fake_run_agent(**kwargs):
        assert "one real external GitHub pull request" in kwargs["question_override"]
        return BaseAgentResponse(response="external pr opened", sop=None)

    monkeypatch.setattr(TaskWorkItemRepository, "list_by_task", list_items)
    monkeypatch.setattr(TaskWorkItemRepository, "all_approved", all_approved)
    monkeypatch.setattr(TaskWorkItemRepository, "get_running", no_running)
    monkeypatch.setattr(TaskWorkItemRepository, "get_next_for_execution", no_next)
    monkeypatch.setattr(execution, "_run_agent", fake_run_agent)

    outcome = asyncio.run(
        execution._run_agent_workflow(
            database=FakeDatabase(),
            task=task,
            on_progress=None,
            settings=SimpleNamespace(),
            workspace_key="workspace",
            github_repo="owner/repo",
            recovered=False,
        )
    )

    assert outcome.status == "waiting_for_merge"
    assert outcome.response == "external pr opened"
