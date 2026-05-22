import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from src.agents.base.agent import BaseAgentResponse
from src.server.celery import execution
from src.server.postgres.models import GithubPullRequestFeedbackKind, TaskCategory, TaskStatus, TaskWorkItemStatus
from src.server.postgres.repositories import ProductProposalRepository, ProposalPlanningRunRepository, TaskRepository, TaskWorkItemRepository


class FakeAgent:
    def __init__(self) -> None:
        """Initialize the test helper."""
        self.work = AsyncMock(return_value=BaseAgentResponse(response="done"))
        self.closed = False
        self.enter_count = 0
        self.exit_count = 0
        self.close_count = 0
        self.nexus_task_context = None

    async def __aenter__(self):
        """Enter the async test context."""
        self.enter_count += 1
        return self

    async def __aexit__(self, *args):
        """Exit the async test context."""
        self.exit_count += 1
        await self.close()
        return None

    async def close(self) -> None:
        """Close a fake service."""
        self.closed = True
        self.close_count += 1

    def set_nexus_task_context(self, context) -> None:
        """Store Nexus task context for tests."""
        self.nexus_task_context = context


def make_task(**overrides):
    """Create a task record for execution tests."""
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
    """Verify run agent resumes from checkpoint when passed."""
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
    """Verify run agent passes question as checkpoint resume question."""
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
    def __init__(self) -> None:
        """Initialize the test helper."""
        self._session = SimpleNamespace(commit=AsyncMock())

    def session(self):
        """Return a fake database session."""
        return self

    async def __aenter__(self):
        """Enter the async test context."""
        return self._session

    async def __aexit__(self, *args):
        """Exit the async test context."""
        return None


def test_build_marc_agent_with_optional_repo_context(monkeypatch):
    """Verify build marc agent with optional repo context."""
    captured_agent = {}

    class FakeMarc:
        @classmethod
        def create(cls, **kwargs):
            """Support create tests."""
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
    """Verify run agent uses fresh context without checkpoint."""
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
    """Verify run code agent workflow small task passthrough."""
    task = make_task()
    fake_agent = FakeAgent()
    calls = []

    async def no_work_items(session, task_id):
        """Return no work items."""
        return []

    async def no_running(session, task_id):
        """Return no running."""
        return None

    async def no_next(session, task_id):
        """Return no next."""
        return None

    async def fake_run_agent(**kwargs):
        """Provide a fake run agent."""
        calls.append(kwargs)
        return BaseAgentResponse(response="final pr opened")

    async def empty_checkpoint(database, task_id):
        """Return an empty checkpoint."""
        assert task_id == task.id
        return []

    async def no_pending_feedback(database, task_id, *, limit):
        """Return no pending feedback."""
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
    """Verify run agent workflow pauses when work item is ready."""
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
        """Support list items tests."""
        return [ready_item if state["ready"] else pending_item]

    async def no_running(session, task_id):
        """Return no running."""
        return None

    async def next_item(session, task_id):
        """Support next item tests."""
        return None if state["ready"] else pending_item

    async def set_running(session, work_item_id):
        """Support set running tests."""
        return running_item

    async def get_item(session, work_item_id):
        """Support get item tests."""
        return ready_item

    async def fake_run_agent(**kwargs):
        """Provide a fake run agent."""
        assert "finish_current_task_work_item" in kwargs["question"]
        assert "final executable work item" in kwargs["question"]
        state["ready"] = True
        return BaseAgentResponse(response="ready")

    async def empty_checkpoint(database, task_id):
        """Return an empty checkpoint."""
        assert task_id == task.id
        return []

    async def no_pending_feedback(database, task_id, *, limit):
        """Return no pending feedback."""
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
    """Verify run agent workflow keeps checkpoint between work items."""
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
        """Support ready item tests."""
        return SimpleNamespace(
            id=item.id,
            order_index=item.order_index,
            title=item.title,
            description=item.description,
            status=TaskWorkItemStatus.ready_for_review,
        )

    def _running_item(item):
        """Support running item tests."""
        return SimpleNamespace(
            id=item.id,
            order_index=item.order_index,
            title=item.title,
            description=item.description,
            status=TaskWorkItemStatus.running,
        )

    async def list_items(session, task_id):
        """Support list items tests."""
        return [
            _ready_item(item) if item.id in ready_ids else item
            for item in pending_items
        ]

    async def no_running(session, task_id):
        """Return no running."""
        return None

    async def next_item(session, task_id):
        """Support next item tests."""
        for item in pending_items:
            if item.id not in ready_ids:
                return item
        return None

    async def set_running(session, work_item_id):
        """Support set running tests."""
        return _running_item(next(item for item in pending_items if item.id == work_item_id))

    async def get_item(session, work_item_id):
        """Support get item tests."""
        return _ready_item(next(item for item in pending_items if item.id == work_item_id))

    async def fake_run_agent(**kwargs):
        """Provide a fake run agent."""
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
        """Support latest checkpoint tests."""
        assert task_id == task.id
        return task.checkpoint or []

    async def no_pending_feedback(database, task_id, *, limit):
        """Return no pending feedback."""
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
    """Verify run agent workflow waits when all work items review ready."""
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
        """Support list items tests."""
        return [approved_item, ready_item]

    fake_agent = FakeAgent()

    async def latest_checkpoint(database, task_id):
        """Support latest checkpoint tests."""
        assert task_id == task.id
        return task.checkpoint or []

    async def no_pending_feedback(database, task_id, *, limit):
        """Return no pending feedback."""
        assert task_id == task.id
        return []

    async def fail_run_agent(**kwargs):
        """Fail if run agent is called."""
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
    """Verify run agent workflow processes github feedback from checkpoint."""
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
        """Support claim feedback tests."""
        assert task_id == task.id
        assert limit == 5
        return feedback_items

    async def mark_processed(database, claimed_items):
        """Support mark processed tests."""
        captured["processed"] = claimed_items

    async def latest_checkpoint(database, task_id):
        """Support latest checkpoint tests."""
        assert task_id == task.id
        return task.checkpoint or []

    async def fake_run_agent(**kwargs):
        """Provide a fake run agent."""
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
    """Verify mark post execution wait state restores waiting for review."""
    task_id = "task-id"
    captured = {}

    async def fake_get(session, requested_task_id):
        """Provide a fake get."""
        assert requested_task_id == task_id
        return SimpleNamespace(id=task_id, status=TaskStatus.waiting_for_review, resume_status=None)

    async def fake_waiting_for_review(session, requested_task_id, *, result):
        """Provide a fake waiting for review."""
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
    """Verify release workspace keeps binding for active instance."""
    captured = {}

    async def fake_get(session, agent_instance_id):
        """Provide a fake get."""
        assert agent_instance_id == "agent-id"
        return SimpleNamespace(is_active=True)

    async def fake_set_idle(session, *, agent_instance_id):
        """Provide a fake set idle."""
        captured["agent_instance_id"] = agent_instance_id

    async def fail_set_inactive(session, *, agent_instance_id):
        """Fail if set inactive is called."""
        raise AssertionError("inactive workspace release should not run for active instances")

    monkeypatch.setattr(execution.AgentInstanceRepository, "get", fake_get)
    monkeypatch.setattr(execution.WorkspaceRepository, "set_idle", fake_set_idle)
    monkeypatch.setattr(execution.WorkspaceRepository, "set_inactive", fail_set_inactive)

    asyncio.run(execution._release_workspace(FakeDatabase(), "agent-id"))

    assert captured == {
        "agent_instance_id": "agent-id",
    }


def test_release_workspace_keeps_binding_for_inactive_instance(monkeypatch):
    """Verify release workspace keeps binding for inactive instance."""
    captured = {}

    async def fake_get(session, agent_instance_id):
        """Provide a fake get."""
        assert agent_instance_id == "agent-id"
        return SimpleNamespace(is_active=False)

    async def fail_set_idle(session, *, agent_instance_id):
        """Fail if set idle is called."""
        raise AssertionError("active workspace release should not run for inactive instances")

    async def fake_set_inactive(session, *, agent_instance_id):
        """Provide a fake set inactive."""
        captured["agent_instance_id"] = agent_instance_id

    monkeypatch.setattr(execution.AgentInstanceRepository, "get", fake_get)
    monkeypatch.setattr(execution.WorkspaceRepository, "set_idle", fail_set_idle)
    monkeypatch.setattr(execution.WorkspaceRepository, "set_inactive", fake_set_inactive)

    asyncio.run(execution._release_workspace(FakeDatabase(), "agent-id"))

    assert captured == {
        "agent_instance_id": "agent-id",
    }


def test_mark_waiting_for_review_completes_planning_run_when_plan_is_valid(monkeypatch):
    """Verify mark waiting for review completes planning run when plan is valid."""
    captured = {}
    planning_run = SimpleNamespace(id="planning-run-id", proposal_id="proposal-id")

    async def fake_set_waiting_for_review(session, task_id, *, result):
        """Provide a fake set waiting for review."""
        captured["waiting"] = (task_id, result)

    async def fake_get_by_task_id(session, task_id):
        """Provide a fake get by task id."""
        return planning_run

    async def fake_validate_plan(session, proposal_id):
        """Provide a fake validate plan."""
        captured["validated_proposal_id"] = proposal_id
        return None

    async def fake_set_completed(session, run_id):
        """Provide a fake set completed."""
        captured["completed_run_id"] = run_id

    async def fake_sync_status_from_features(session, proposal_id):
        """Provide a fake sync status from features."""
        captured["synced_proposal_id"] = proposal_id

    monkeypatch.setattr(TaskRepository, "set_waiting_for_review", fake_set_waiting_for_review)
    monkeypatch.setattr(ProposalPlanningRunRepository, "get_by_task_id", fake_get_by_task_id)
    monkeypatch.setattr(ProposalPlanningRunRepository, "validate_plan", fake_validate_plan)
    monkeypatch.setattr(ProposalPlanningRunRepository, "set_completed", fake_set_completed)
    monkeypatch.setattr(ProductProposalRepository, "sync_status_from_features", fake_sync_status_from_features)

    asyncio.run(execution._mark_waiting_for_review(FakeDatabase(), "task-id", "pm result"))

    assert captured == {
        "waiting": ("task-id", "pm result"),
        "validated_proposal_id": "proposal-id",
        "completed_run_id": "planning-run-id",
        "synced_proposal_id": "proposal-id",
    }


def test_mark_waiting_for_review_fails_planning_run_when_plan_is_invalid(monkeypatch):
    """Verify mark waiting for review fails planning run when plan is invalid."""
    captured = {}
    planning_run = SimpleNamespace(id="planning-run-id", proposal_id="proposal-id")

    async def fake_set_waiting_for_review(session, task_id, *, result):
        """Provide a fake set waiting for review."""
        captured["waiting"] = (task_id, result)

    async def fake_get_by_task_id(session, task_id):
        """Provide a fake get by task id."""
        return planning_run

    async def fake_validate_plan(session, proposal_id):
        """Provide a fake validate plan."""
        return "missing feature items"

    async def fake_set_failed(session, task_id, *, error):
        """Provide a fake set failed."""
        captured["task_failed"] = (task_id, error)

    async def fake_set_run_failed(session, run_id, *, error):
        """Provide a fake set run failed."""
        captured["run_failed"] = (run_id, error)

    async def fail_set_completed(session, run_id):
        """Fail if set completed is called."""
        raise AssertionError("completed hook should not run for an invalid plan")

    async def fail_sync_status(session, proposal_id):
        """Fail if sync status is called."""
        raise AssertionError("proposal status sync should not run for an invalid plan")

    monkeypatch.setattr(TaskRepository, "set_waiting_for_review", fake_set_waiting_for_review)
    monkeypatch.setattr(ProposalPlanningRunRepository, "get_by_task_id", fake_get_by_task_id)
    monkeypatch.setattr(ProposalPlanningRunRepository, "validate_plan", fake_validate_plan)
    monkeypatch.setattr(TaskRepository, "set_failed", fake_set_failed)
    monkeypatch.setattr(ProposalPlanningRunRepository, "set_failed", fake_set_run_failed)
    monkeypatch.setattr(ProposalPlanningRunRepository, "set_completed", fail_set_completed)
    monkeypatch.setattr(ProductProposalRepository, "sync_status_from_features", fail_sync_status)

    asyncio.run(execution._mark_waiting_for_review(FakeDatabase(), "task-id", "pm result"))

    assert captured == {
        "waiting": ("task-id", "pm result"),
        "task_failed": ("task-id", "missing feature items"),
        "run_failed": ("planning-run-id", "missing feature items"),
    }
