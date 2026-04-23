from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.agents.base.agent import BaseAgentResponse
from src.server.celery import execution


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
        "question": "do the task",
        "requested_current_session_ctx": [{"role": "assistant", "content": "current"}],
        "requested_history_session_ctx": [{"role": "user", "content": "history"}],
        "checkpoint": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.mark.asyncio
async def test_run_agent_resumes_from_checkpoint_when_recovered(monkeypatch):
    checkpoint = [
        {"role": "system", "content": "checkpoint system"},
        {"role": "user", "content": "original task"},
    ]
    task = make_task(checkpoint=checkpoint)
    fake_agent = FakeAgent()

    monkeypatch.setattr(execution, "_build_agent", lambda **_: fake_agent)

    result = await execution._run_agent(
        task=task,
        on_progress=None,
        settings=SimpleNamespace(),
        workspace_key="workspace",
        github_repo="owner/repo",
        recovered=True,
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


@pytest.mark.asyncio
async def test_run_agent_uses_fresh_context_without_recovered_checkpoint(monkeypatch):
    task = make_task(checkpoint=[{"role": "system", "content": "old checkpoint"}])
    fake_agent = FakeAgent()

    monkeypatch.setattr(execution, "_build_agent", lambda **_: fake_agent)

    await execution._run_agent(
        task=task,
        on_progress=None,
        settings=SimpleNamespace(),
        workspace_key="workspace",
        github_repo="owner/repo",
        recovered=False,
    )

    fake_agent.work.assert_awaited_once_with(
        question="do the task",
        current_session_ctx=[{"role": "assistant", "content": "current"}],
        history_session_ctx=[{"role": "user", "content": "history"}],
        update_process_callback=None,
    )
