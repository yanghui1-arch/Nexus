import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from src.agents.base.agent import BaseAgentResponse
from src.server.celery import execution
from src.server.postgres.models import GithubPullRequestFeedbackKind, TaskCategory, TaskStatus, TaskWorkItemStatus
from src.server.postgres.repositories import TaskWorkItemRepository


class FakeAgent:
    def __init__(self) -> None:
        self.work = AsyncMock(return_value=BaseAgentResponse(response="done"))
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
        "agent": SimpleNamespace(value="sophie"),
        "category": TaskCategory.coding,
        "repo": "owner/repo",
        "project": None,
        "question": "do the task",
        "checkpoint": None,
        "resume_status": None,
    }
    values.update(overrides)
    values.setdefault("category", SimpleNamespace(value="coding"))
    values.setdefault("project", None)
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


def test_build_marc_agent_with_optional_repo_context(monkeypatch):
    captured_agent = {}

    class FakeMarc:
        @classmethod
        def create(cls, **kwargs):
            captured_agent.update(kwargs)
            return "marc-agent"

    task = make_task(agent=SimpleNamespace(value="marc"), repo="owner/repo")
    settings = SimpleNamespace(
        api_key="api-key",
        base_url="https://api.example.com/v1",
        model="gpt-test",
        max_context=4096,
        max_attempts=8,
        github_tokens={"marc": "marc-token"},
    )

    monkeypatch.setitem(execution._agents, "marc", FakeMarc)

    agent = execution._build_agent(
        task=task,
        settings=settings,
        workspace_key="workspace",
        github_repo=None,
    )

    assert agent == "marc-agent"
    assert captured_agent == {
        "base_url": "https://api.example.com/v1",
        "api_key": "api-key",
        "model": "gpt-test",
        "max_context": 4096,
        "max_attempts": 8,
        "github_repo": "owner/repo",
        "github_token": "marc-token",
    }


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


def test_run_code_agent_workflow_small_task_passthrough(monkeypatch):
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
        return BaseAgentResponse(response="final pr opened")

    async def empty_checkpoint(database, task_id):
        assert task_id == task.id
        return []

    async def no_pending_feedback(database, task_id, *, limit):
        assert task_id == task.id
        return []

    monkeypatch.setattr(TaskWorkItemRepository, "list_by_task", no_work_items)
    monkeypatch.setattr(TaskWorkItemRepository, "get_running", no_running)
    monkeypatch.setattr(TaskWorkItemRepository, "get_next_for_execution", no_next)
    monkeypatch.setattr(execution, "_build_agent", lambda **_: fake_agent)
    monkeypatch.setattr(execution, "_run_agent", fake_run_agent)
    monkeypatch.setattr(execution, "_get_latest_checkpoint", empty_checkpoint)
    monkeypatch.setattr(execution, "_claim_pending_github_feedback", no_pending_feedback)

    result = asyncio.run(
        execution._run_code_agent_workflow(
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

    async def fake_run_agent(**kwargs):
        assert "finish_current_task_work_item" in kwargs["question"]
        assert "final executable work item" in kwargs["question"]
        state["ready"] = True
        return BaseAgentResponse(response="ready")

    async def empty_checkpoint(database, task_id):
        assert task_id == task.id
        return []

    async def no_pending_feedback(database, task_id, *, limit):
        assert task_id == task.id
        return []

    monkeypatch.setattr(TaskWorkItemRepository, "list_by_task", list_items)
    monkeypatch.setattr(TaskWorkItemRepository, "get_running", no_running)
    monkeypatch.setattr(TaskWorkItemRepository, "get_next_for_execution", next_item)
    monkeypatch.setattr(TaskWorkItemRepository, "set_running", set_running)
    monkeypatch.setattr(TaskWorkItemRepository, "get", get_item)
    monkeypatch.setattr(execution, "_build_agent", lambda **_: fake_agent)
    monkeypatch.setattr(execution, "_run_agent", fake_run_agent)
    monkeypatch.setattr(execution, "_get_latest_checkpoint", empty_checkpoint)
    monkeypatch.setattr(execution, "_claim_pending_github_feedback", no_pending_feedback)

    result = asyncio.run(
        execution._run_code_agent_workflow(
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
        return BaseAgentResponse(response=f"{work_item_id} ready")

    async def latest_checkpoint(database, task_id):
        assert task_id == task.id
        return task.checkpoint or []

    async def no_pending_feedback(database, task_id, *, limit):
        assert task_id == task.id
        return []

    monkeypatch.setattr(TaskWorkItemRepository, "list_by_task", list_items)
    monkeypatch.setattr(TaskWorkItemRepository, "get_running", no_running)
    monkeypatch.setattr(TaskWorkItemRepository, "get_next_for_execution", next_item)
    monkeypatch.setattr(TaskWorkItemRepository, "set_running", set_running)
    monkeypatch.setattr(TaskWorkItemRepository, "get", get_item)
    monkeypatch.setattr(execution, "_build_agent", lambda **_: fake_agent)
    monkeypatch.setattr(execution, "_run_agent", fake_run_agent)
    monkeypatch.setattr(execution, "_get_latest_checkpoint", latest_checkpoint)
    monkeypatch.setattr(execution, "_claim_pending_github_feedback", no_pending_feedback)

    result = asyncio.run(
        execution._run_code_agent_workflow(
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

    async def no_pending_feedback(database, task_id, *, limit):
        assert task_id == task.id
        return []

    async def fail_run_agent(**kwargs):
        raise AssertionError("review-ready work items should not run the agent")

    monkeypatch.setattr(TaskWorkItemRepository, "list_by_task", list_items)
    monkeypatch.setattr(execution, "_build_agent", lambda **_: fake_agent)
    monkeypatch.setattr(execution, "_run_agent", fail_run_agent)
    monkeypatch.setattr(execution, "_get_latest_checkpoint", latest_checkpoint)
    monkeypatch.setattr(execution, "_claim_pending_github_feedback", no_pending_feedback)

    result = asyncio.run(
        execution._run_code_agent_workflow(
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


def test_run_agent_workflow_processes_github_feedback_from_checkpoint(monkeypatch):
    task = make_task(
        checkpoint=[
            {"role": "system", "content": "checkpoint system"},
            {"role": "assistant", "content": "checkpoint progress"},
        ]
    )
    fake_agent = FakeAgent()
    captured = {}
    feedback_items = [
        SimpleNamespace(
            id="feedback-1",
            pull_request_number=17,
            kind=GithubPullRequestFeedbackKind.pr_review_comment,
            external_id=901,
            author="reviewer",
            body="Please rename this variable.",
            review_state=None,
            file_path="src/main.py",
            line=42,
            html_url="https://github.com/owner/repo/pull/17#discussion_r901",
        )
    ]

    async def claim_feedback(database, task_id, *, limit):
        assert task_id == task.id
        assert limit == 5
        return feedback_items

    async def mark_processed(database, claimed_items):
        captured["processed"] = claimed_items

    async def latest_checkpoint(database, task_id):
        assert task_id == task.id
        return task.checkpoint or []

    async def fake_run_agent(**kwargs):
        captured["run"] = kwargs
        return BaseAgentResponse(response="replied")

    monkeypatch.setattr(execution, "_claim_pending_github_feedback", claim_feedback)
    monkeypatch.setattr(execution, "_mark_github_feedback_processed", mark_processed)
    monkeypatch.setattr(execution, "_get_latest_checkpoint", latest_checkpoint)
    monkeypatch.setattr(execution, "_build_agent", lambda **_: fake_agent)
    monkeypatch.setattr(execution, "_run_agent", fake_run_agent)

    result = asyncio.run(
        execution._run_code_agent_workflow(
            database=FakeDatabase(),
            task=task,
            on_progress=None,
            settings=SimpleNamespace(github_feedback_batch_size=5),
            workspace_key="workspace",
            github_repo="owner/repo",
            recovered=False,
        )
    )

    assert result is None
    assert captured["processed"] == feedback_items
    assert captured["run"]["checkpoint"] == [
        {"role": "system", "content": "checkpoint system"},
        {"role": "assistant", "content": "checkpoint progress"},
    ]
    assert "Continue the current task." in captured["run"]["question"]
    assert "reply_to_pr_review_comment(pull_number=17, comment_id=901)" in captured["run"]["question"]
    assert (
        "<agent-system-reminder>The following feedback was sent from GitHub by `reviewer` "
        "as `pr_review_comment`.</agent-system-reminder>Please rename this variable."
    ) in captured["run"]["question"]
    assert fake_agent.enter_count == 1
    assert fake_agent.close_count == 1


def test_mark_post_execution_wait_state_restores_waiting_for_review(monkeypatch):
    task_id = "task-id"
    captured = {}

    async def fake_get(session, requested_task_id):
        assert requested_task_id == task_id
        return SimpleNamespace(id=task_id, status=TaskStatus.waiting_for_review, resume_status=None)

    async def fake_waiting_for_review(session, requested_task_id, *, result):
        captured["task_id"] = requested_task_id
        captured["result"] = result

    monkeypatch.setattr(execution.TaskRepository, "get", fake_get)
    monkeypatch.setattr(execution.TaskRepository, "set_waiting_for_review", fake_waiting_for_review)

    asyncio.run(
        execution._mark_post_execution_wait_state(
            FakeDatabase(),
            task_id,
            "done",
        )
    )

    assert captured == {"task_id": task_id, "result": "done"}


def test_release_workspace_keeps_binding_for_active_instance(monkeypatch):
    captured = {}

    async def fake_get(session, agent_instance_id):
        assert agent_instance_id == "agent-id"
        return SimpleNamespace(is_active=True)

    async def fake_set_idle(session, *, agent_instance_id):
        captured["agent_instance_id"] = agent_instance_id

    async def fail_set_inactive(session, *, agent_instance_id):
        raise AssertionError("inactive workspace release should not run for active instances")

    monkeypatch.setattr(execution.AgentInstanceRepository, "get", fake_get)
    monkeypatch.setattr(execution.WorkspaceRepository, "set_idle", fake_set_idle)
    monkeypatch.setattr(execution.WorkspaceRepository, "set_inactive", fail_set_inactive)

    asyncio.run(execution._release_workspace(FakeDatabase(), "agent-id"))

    assert captured == {
        "agent_instance_id": "agent-id",
    }


def test_release_workspace_keeps_binding_for_inactive_instance(monkeypatch):
    captured = {}

    async def fake_get(session, agent_instance_id):
        assert agent_instance_id == "agent-id"
        return SimpleNamespace(is_active=False)

    async def fail_set_idle(session, *, agent_instance_id):
        raise AssertionError("active workspace release should not run for inactive instances")

    async def fake_set_inactive(session, *, agent_instance_id):
        captured["agent_instance_id"] = agent_instance_id

    monkeypatch.setattr(execution.AgentInstanceRepository, "get", fake_get)
    monkeypatch.setattr(execution.WorkspaceRepository, "set_idle", fail_set_idle)
    monkeypatch.setattr(execution.WorkspaceRepository, "set_inactive", fake_set_inactive)

    asyncio.run(execution._release_workspace(FakeDatabase(), "agent-id"))

    assert captured == {
        "agent_instance_id": "agent-id",
    }


def test_execute_agent_task_treats_shutdown_as_redispatch(monkeypatch):
    task = SimpleNamespace(id="task-id", status=TaskStatus.running, agent_instance_id="agent-id")
    captured = {}

    class FakeSessionContext:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, *args):
            return None

    class FakeDatabase:
        def __init__(self):
            self.connected = False
            self.disconnected = False

        async def connect(self):
            self.connected = True

        async def disconnect(self):
            self.disconnected = True

        def session(self):
            return FakeSessionContext()

    async def fake_load_task(database, task_id):
        assert task_id == task.id
        return task

    async def fake_load_binding(database, task):
        return SimpleNamespace(github_repo="owner/repo", project=None, workspace_key="workspace")

    async def fake_set_workspace_running(*args, **kwargs):
        return None

    async def fake_claim_running(*args, **kwargs):
        return True

    async def fake_run_agent_workflow(**kwargs):
        raise asyncio.CancelledError()

    async def fake_release_workspace(*args, **kwargs):
        return None

    async def fake_mark_queued_for_redispatch(database, task_id):
        captured["task_id"] = task_id
        captured["error"] = None
        task.status = TaskStatus.queued

    async def fake_set_failed(*args, **kwargs):
        raise AssertionError("shutdown should not mark task failed")

    monkeypatch.setattr(execution, "_load_task", fake_load_task)
    monkeypatch.setattr(execution, "_load_binding", fake_load_binding)
    monkeypatch.setattr(execution, "_set_workspace_running", fake_set_workspace_running)
    monkeypatch.setattr(execution, "_claim_running", fake_claim_running)
    monkeypatch.setattr(execution, "_run_agent_workflow", fake_run_agent_workflow)
    monkeypatch.setattr(execution, "_release_workspace", fake_release_workspace)
    monkeypatch.setattr(execution, "_mark_queued_for_redispatch", fake_mark_queued_for_redispatch)
    monkeypatch.setattr(execution.TaskRepository, "set_failed", fake_set_failed)

    asyncio.run(
        execution.execute_agent_task(
            task_id=task.id,
            settings=SimpleNamespace(database_url="sqlite+aiosqlite:///:memory:", task_dispatch_lease_seconds=5),
            dispatch_token="dispatch-token",
        )
    )

    assert captured == {"task_id": task.id, "error": None}
    assert task.status == TaskStatus.queued


def test_is_worker_shutdown_exception_detects_shutdown_signals():
    assert execution._is_worker_shutdown_exception(asyncio.CancelledError()) is True
    assert execution._is_worker_shutdown_exception(KeyboardInterrupt()) is True
    assert execution._is_worker_shutdown_exception(SystemExit()) is True
    assert execution._is_worker_shutdown_exception(RuntimeError()) is False
