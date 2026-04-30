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
        self.enter_count = 0
        self.exit_count = 0
        self.close_count = 0
        self.nexus_task_context = None

    async def __aenter__(self):
        self.enter_count += 1
        return self

    async def __aexit__(self, *args):
        self.exit_count += 1
        await self.close()
        return None

    async def close(self) -> None:
        self.closed = True
        self.close_count += 1

    def set_nexus_task_context(self, context) -> None:
        self.nexus_task_context = context


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


def test_run_agent_resumes_from_checkpoint_when_passed(monkeypatch):
    checkpoint = [
        {"role": "system", "content": "checkpoint system"},
        {"role": "user", "content": "original task"},
    ]
    fake_agent = FakeAgent()

    result = asyncio.run(
        execution._run_agent(
            agent=fake_agent,
            question="do the task",
            checkpoint=checkpoint,
            on_progress=None,
        )
    )

    assert result.response == "done"
    fake_agent.work.assert_awaited_once_with(
        question="do the task",
        update_process_callback=None,
        from_checkpoint=True,
        checkpoint=[
            {"role": "system", "content": "checkpoint system"},
            {"role": "user", "content": "original task"},
        ],
    )
    assert fake_agent.closed is False


def test_run_agent_passes_question_as_checkpoint_resume_question(monkeypatch):
    checkpoint = [
        {"role": "system", "content": "checkpoint system"},
        {"role": "user", "content": "original task"},
    ]
    fake_agent = FakeAgent()

    asyncio.run(
        execution._run_agent(
            agent=fake_agent,
            question="Please address review feedback.",
            checkpoint=checkpoint,
            on_progress=None,
        )
    )

    fake_agent.work.assert_awaited_once()
    assert fake_agent.work.await_args.kwargs["question"] == "Please address review feedback."
    assert fake_agent.work.await_args.kwargs["from_checkpoint"] is True
    assert fake_agent.work.await_args.kwargs["checkpoint"] == [
        {"role": "system", "content": "checkpoint system"},
        {"role": "user", "content": "original task"},
    ]


class FakeDatabase:
    def session(self):
        return self

    async def __aenter__(self):
        return object()

    async def __aexit__(self, *args):
        return None


def test_run_agent_uses_fresh_context_without_checkpoint(monkeypatch):
    fake_agent = FakeAgent()

    asyncio.run(
        execution._run_agent(
            agent=fake_agent,
            question="do the task",
            on_progress=None,
        )
    )

    fake_agent.work.assert_awaited_once_with(
        question="do the task",
        update_process_callback=None,
        from_checkpoint=False,
    )


def test_run_agent_workflow_small_task_passthrough(monkeypatch):
    task = make_task()
    fake_agent = FakeAgent()
    calls = []

    async def no_work_items(session, task_id):
        return []

    async def no_running(session, task_id):
        return None

    async def no_next(session, task_id):
        return None

    async def fake_run_agent(**kwargs):
        calls.append(kwargs)
        return BaseAgentResponse(response="final pr opened", sop=None)

    async def empty_checkpoint(database, task_id):
        assert task_id == task.id
        return []

    monkeypatch.setattr(TaskWorkItemRepository, "list_by_task", no_work_items)
    monkeypatch.setattr(TaskWorkItemRepository, "get_running", no_running)
    monkeypatch.setattr(TaskWorkItemRepository, "get_next_for_execution", no_next)
    monkeypatch.setattr(execution, "_build_agent", lambda **_: fake_agent)
    monkeypatch.setattr(execution, "_run_agent", fake_run_agent)
    monkeypatch.setattr(execution, "_get_latest_checkpoint", empty_checkpoint)

    result = asyncio.run(
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

    assert result is None
    assert len(calls) == 1
    assert calls[0]["question"] == "do the task"
    assert calls[0]["checkpoint"] == []
    assert fake_agent.enter_count == 1
    assert fake_agent.close_count == 1


def test_run_agent_workflow_pauses_when_work_item_is_ready(monkeypatch):
    task = make_task()
    fake_agent = FakeAgent()
    state = {"ready": False}
    pending_item = SimpleNamespace(
        id="item-id",
        order_index=1,
        title="One",
        description="Do one",
        status=TaskWorkItemStatus.pending,
    )
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
        return [ready_item if state["ready"] else pending_item]

    async def no_running(session, task_id):
        return None

    async def next_item(session, task_id):
        return None if state["ready"] else pending_item

    async def set_running(session, work_item_id):
        return running_item

    async def get_item(session, work_item_id):
        return ready_item

    async def get_virtual_pr(session, work_item_id):
        return SimpleNamespace(id="virtual-pr-id")

    async def list_reviews(session, virtual_pr_id):
        return []

    async def fake_run_agent(**kwargs):
        assert "finish_current_task_work_item" in kwargs["question"]
        assert "final executable work item" in kwargs["question"]
        state["ready"] = True
        return BaseAgentResponse(response="ready", sop=None)

    async def empty_checkpoint(database, task_id):
        assert task_id == task.id
        return []

    monkeypatch.setattr(TaskWorkItemRepository, "list_by_task", list_items)
    monkeypatch.setattr(TaskWorkItemRepository, "get_running", no_running)
    monkeypatch.setattr(TaskWorkItemRepository, "get_next_for_execution", next_item)
    monkeypatch.setattr(TaskWorkItemRepository, "set_running", set_running)
    monkeypatch.setattr(TaskWorkItemRepository, "get", get_item)
    monkeypatch.setattr(VirtualPullRequestRepository, "get_by_work_item", get_virtual_pr)
    monkeypatch.setattr(VirtualPullRequestRepository, "list_reviews_by_virtual_pr", list_reviews)
    monkeypatch.setattr(execution, "_build_agent", lambda **_: fake_agent)
    monkeypatch.setattr(execution, "_run_agent", fake_run_agent)
    monkeypatch.setattr(execution, "_get_latest_checkpoint", empty_checkpoint)

    result = asyncio.run(
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

    assert result is None
    assert fake_agent.enter_count == 1
    assert fake_agent.close_count == 1


def test_run_agent_workflow_keeps_checkpoint_between_work_items(monkeypatch):
    task = make_task()
    fake_agent = FakeAgent()
    ready_ids = set()
    calls = []
    pending_items = [
        SimpleNamespace(
            id="item-1",
            order_index=1,
            title="One",
            description="Do one",
            status=TaskWorkItemStatus.pending,
        ),
        SimpleNamespace(
            id="item-2",
            order_index=2,
            title="Two",
            description="Do two",
            status=TaskWorkItemStatus.pending,
        ),
    ]

    def _ready_item(item):
        return SimpleNamespace(
            id=item.id,
            order_index=item.order_index,
            title=item.title,
            description=item.description,
            status=TaskWorkItemStatus.ready_for_review,
        )

    def _running_item(item):
        return SimpleNamespace(
            id=item.id,
            order_index=item.order_index,
            title=item.title,
            description=item.description,
            status=TaskWorkItemStatus.running,
        )

    async def list_items(session, task_id):
        return [
            _ready_item(item) if item.id in ready_ids else item
            for item in pending_items
        ]

    async def no_running(session, task_id):
        return None

    async def next_item(session, task_id):
        for item in pending_items:
            if item.id not in ready_ids:
                return item
        return None

    async def set_running(session, work_item_id):
        return _running_item(next(item for item in pending_items if item.id == work_item_id))

    async def get_item(session, work_item_id):
        return _ready_item(next(item for item in pending_items if item.id == work_item_id))

    async def get_virtual_pr(session, work_item_id):
        return SimpleNamespace(id=f"virtual-pr-{work_item_id}")

    async def list_reviews(session, virtual_pr_id):
        return []

    async def fake_run_agent(**kwargs):
        work_item_id = kwargs["agent"].nexus_task_context.current_work_item_id
        calls.append(
            {
                "agent_id": id(kwargs["agent"]),
                "current_work_item_id": work_item_id,
                "checkpoint": kwargs["checkpoint"],
                "question": kwargs["question"],
            }
        )
        ready_ids.add(work_item_id)
        if work_item_id == "item-1":
            task.checkpoint = [{"role": "assistant", "content": "first item finished"}]
        return BaseAgentResponse(response=f"{work_item_id} ready", sop=None)

    async def latest_checkpoint(database, task_id):
        assert task_id == task.id
        return task.checkpoint or []

    monkeypatch.setattr(TaskWorkItemRepository, "list_by_task", list_items)
    monkeypatch.setattr(TaskWorkItemRepository, "get_running", no_running)
    monkeypatch.setattr(TaskWorkItemRepository, "get_next_for_execution", next_item)
    monkeypatch.setattr(TaskWorkItemRepository, "set_running", set_running)
    monkeypatch.setattr(TaskWorkItemRepository, "get", get_item)
    monkeypatch.setattr(VirtualPullRequestRepository, "get_by_work_item", get_virtual_pr)
    monkeypatch.setattr(VirtualPullRequestRepository, "list_reviews_by_virtual_pr", list_reviews)
    monkeypatch.setattr(execution, "_build_agent", lambda **_: fake_agent)
    monkeypatch.setattr(execution, "_run_agent", fake_run_agent)
    monkeypatch.setattr(execution, "_get_latest_checkpoint", latest_checkpoint)

    result = asyncio.run(
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

    assert result is None
    assert [call["current_work_item_id"] for call in calls] == ["item-1", "item-2"]
    assert {call["agent_id"] for call in calls} == {id(fake_agent)}
    assert calls[0]["checkpoint"] == []
    assert calls[1]["checkpoint"] == [{"role": "assistant", "content": "first item finished"}]
    assert "Do not create a github pull request" in calls[0]["question"]
    assert "final executable work item" in calls[1]["question"]
    assert fake_agent.enter_count == 1
    assert fake_agent.close_count == 1


def test_run_agent_workflow_waits_when_all_work_items_review_ready(monkeypatch):
    task = make_task(checkpoint=[{"role": "assistant", "content": "work items complete"}])
    approved_item = SimpleNamespace(
        id="item-1",
        order_index=1,
        title="One",
        description="Do one",
        summary="Done",
        status=TaskWorkItemStatus.approved,
    )
    ready_item = SimpleNamespace(
        id="item-2",
        order_index=2,
        title="Two",
        description="Do two",
        summary="Done",
        status=TaskWorkItemStatus.ready_for_review,
    )

    async def list_items(session, task_id):
        return [approved_item, ready_item]

    fake_agent = FakeAgent()

    async def latest_checkpoint(database, task_id):
        assert task_id == task.id
        return task.checkpoint or []

    async def fail_run_agent(**kwargs):
        raise AssertionError("review-ready work items should not run the agent")

    monkeypatch.setattr(TaskWorkItemRepository, "list_by_task", list_items)
    monkeypatch.setattr(execution, "_build_agent", lambda **_: fake_agent)
    monkeypatch.setattr(execution, "_run_agent", fail_run_agent)
    monkeypatch.setattr(execution, "_get_latest_checkpoint", latest_checkpoint)

    result = asyncio.run(
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

    assert result is None
    assert fake_agent.enter_count == 1
    assert fake_agent.close_count == 1
