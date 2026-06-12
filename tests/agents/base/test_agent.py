import pytest
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

from openai.types.chat.chat_completion_message_tool_call import (
    ChatCompletionMessageToolCall,
    Function,
)

from src.agents.base.agent import (
    Agent,
    BaseAgentStepResult,
    ModelConfig,
    WorkTempStatus,
    _COMPACT_SUMMARY_HEADER,
)


def make_model_config() -> ModelConfig:
    """Create a model config for agent tests."""
    return ModelConfig(model="gpt-4o", max_length_context=8192)


def make_tool_call(id: str, name: str, arguments: str) -> ChatCompletionMessageToolCall:
    """Create a chat completion tool call."""
    return ChatCompletionMessageToolCall(
        id=id,
        type="function",
        function=Function(name=name, arguments=arguments),
    )


def _make_message_param_mock(role: str, content: str | None) -> MagicMock:
    """Return a MagicMock whose model_dump() produces a ChatCompletionMessageParam dict."""
    mock = MagicMock()
    mock.model_dump.return_value = {"role": role, "content": content}
    return mock


def make_stop_result(content: str = "done") -> BaseAgentStepResult:
    """Create a stop-step result."""
    return BaseAgentStepResult(
        finish_reason="stop",
        reasoning=None,
        completion_content=content,
        tool_calls=None,
        message_param=_make_message_param_mock("assistant", content),
        current_step_consume_tokens=10,
    )


def make_tool_result(tool_calls: list) -> BaseAgentStepResult:
    """Create a tool-call step result."""
    return BaseAgentStepResult(
        finish_reason="tool_calls",
        reasoning=None,
        completion_content=None,
        tool_calls=tool_calls,
        message_param=_make_message_param_mock("assistant", None),
        current_step_consume_tokens=10,
    )


def set_step(agent: "ConcreteAgent", mock) -> None:
    """Bypass Pydantic's __setattr__ to set an awaitable step method on the instance."""
    if isinstance(mock, AsyncMock):
        async_step = mock
    else:
        # Keep existing MagicMock behavior (side_effect/call_count), but make step awaitable.
        async_step = AsyncMock(side_effect=mock)
    object.__setattr__(agent, "step", async_step)


class ConcreteAgent(Agent):
    """Minimal concrete Agent for testing."""

    async def step(self, current_turn_ctx: list) -> BaseAgentStepResult:
        """Return the next queued test step."""
        raise NotImplementedError("patch me")

    def last_report_current_process(self, current_turn_ctx: list) -> str:
        """Return a test progress report."""
        return "partial progress"


def make_agent(tool_kits=None, max_attempts=None) -> ConcreteAgent:
    """Create a test agent instance."""
    with patch("src.agents.base.agent.AsyncOpenAI"):
        agent = ConcreteAgent(
            name="test-agent",
            tool_kits=tool_kits or {},
            base_url="http://localhost",
            api_key="test-key",
            system_prompt="You are a test agent.",
            llm_config=make_model_config(),
            max_attempts=max_attempts,
        )
    agent.openai_client.chat.completions.create = AsyncMock()
    return agent


def set_compact_summary(agent: ConcreteAgent, summary: str) -> None:
    """Configure the compact summary response."""
    completion = MagicMock()
    completion.choices = [MagicMock(message=MagicMock(content=summary))]
    agent.openai_client.chat.completions.create.return_value = completion


class TestProcessCallback:
    def test_calls_callback_with_status(self):
        """Verify calls callback with status."""
        agent = make_agent()
        cb = MagicMock()
        status: WorkTempStatus = {
            "process": "START",
            "agent_content": None,
            "current_use_tool": None,
            "current_use_tool_args": None,
        }
        agent._process_callback(cb, status)
        cb.assert_called_once_with(status)

    def test_none_callback_does_not_raise(self):
        """Verify none callback does not raise."""
        agent = make_agent()
        status: WorkTempStatus = {
            "process": "START",
            "agent_content": None,
            "current_use_tool": None,
            "current_use_tool_args": None,
        }
        agent._process_callback(None, status)


class TestWorkStop:
    async def test_returns_response_on_stop(self):
        """Verify returns response on stop."""
        agent = make_agent()
        set_step(agent, MagicMock(return_value=make_stop_result("final answer")))

        result = await agent.work(question="q", from_checkpoint=False)

        assert result.response == "final answer"

    async def test_from_checkpoint_uses_checkpoint_as_current_turn_context(self):
        """Verify from checkpoint uses checkpoint as current turn context."""
        agent = make_agent()
        checkpoint = [
            {"role": "system", "content": "checkpoint system"},
            {"role": "user", "content": "original task"},
            {"role": "assistant", "content": "checkpointed progress"},
        ]
        captured_contexts: list[list] = []

        async def capture_step(current_turn_ctx: list) -> BaseAgentStepResult:
            """Capture the context passed to a step."""
            captured_contexts.append(list(current_turn_ctx))
            return make_stop_result("resumed answer")

        set_step(agent, AsyncMock(side_effect=capture_step))

        result = await agent.work(
            question="continue from checkpoint",
            from_checkpoint=True,
            checkpoint=checkpoint,
        )

        assert result.response == "resumed answer"
        assert captured_contexts == [
            [*checkpoint, {"role": "user", "content": "continue from checkpoint"}]
        ]

    async def test_from_checkpoint_requires_checkpoint(self):
        """Verify from checkpoint requires checkpoint."""
        agent = make_agent()

        with pytest.raises(AssertionError, match="Checkpoint is required when from_checkpoint=True"):
            await agent.work(
                question="q",
                from_checkpoint=True,
            )

    async def test_start_and_completed_callbacks_fired(self):
        """Verify start and completed callbacks fired."""
        agent = make_agent()
        set_step(agent, MagicMock(return_value=make_stop_result("done")))
        events: list[WorkTempStatus] = []

        await agent.work(
            question="q",
            from_checkpoint=False,
            update_process_callback=events.append,
        )

        processes = [e["process"] for e in events]
        assert processes[0] == "START"
        assert "COMPLETED" in processes

    async def test_no_callback_does_not_raise(self):
        """Verify no callback does not raise."""
        agent = make_agent()
        set_step(agent, MagicMock(return_value=make_stop_result("done")))

        result = await agent.work(question="q", from_checkpoint=False)
        assert result.response == "done"


class TestWorkToolCalls:
    async def test_sync_tool_is_called_and_result_appended(self):
        """Verify sync tool is called and result appended."""
        sync_tool = MagicMock(return_value="tool-output")
        agent = make_agent(tool_kits={"my_tool": sync_tool})

        tc = make_tool_call("id1", "my_tool", '{"x": 1}')
        set_step(agent, MagicMock(side_effect=[
            make_tool_result([tc]),
            make_stop_result("done"),
        ]))

        result = await agent.work(question="q", from_checkpoint=False)

        sync_tool.assert_called_once_with(x=1)
        assert result.response == "done"

    async def test_async_tool_is_awaited(self):
        """Verify async tool is awaited."""
        async_tool = AsyncMock(return_value="async-output")
        agent = make_agent(tool_kits={"async_tool": async_tool})

        tc = make_tool_call("id1", "async_tool", '{"y": 2}')
        set_step(agent, MagicMock(side_effect=[
            make_tool_result([tc]),
            make_stop_result("done"),
        ]))

        await agent.work(question="q", from_checkpoint=False)
        async_tool.assert_awaited_once_with(y=2)

    async def test_process_callback_fired_on_tool_call(self):
        """Verify process callback fired on tool call."""
        tool = MagicMock(return_value="out")
        agent = make_agent(tool_kits={"t": tool})
        tc = make_tool_call("id1", "t", "{}")
        set_step(agent, MagicMock(side_effect=[
            make_tool_result([tc]),
            make_stop_result("done"),
        ]))
        events: list[WorkTempStatus] = []

        await agent.work(
            question="q",
            from_checkpoint=False,
            update_process_callback=events.append,
        )

        process_events = [e["process"] for e in events]
        assert "PROCESS" in process_events
        process_status = next(e for e in events if e["process"] == "PROCESS")
        assert process_status["current_use_tool"] == ["t"]

    async def test_multiple_tool_calls_dispatched_in_parallel(self):
        """Verify multiple tool calls dispatched in parallel."""
        import asyncio
        order: list[str] = []

        async def slow_tool(**_):
            """Return a slow tool result."""
            await asyncio.sleep(0.05)
            order.append("slow")
            return "slow"

        async def fast_tool(**_):
            """Return a fast tool result."""
            order.append("fast")
            return "fast"

        agent = make_agent(tool_kits={"slow": slow_tool, "fast": fast_tool})
        tcs = [
            make_tool_call("id1", "slow", "{}"),
            make_tool_call("id2", "fast", "{}"),
        ]
        set_step(agent, MagicMock(side_effect=[
            make_tool_result(tcs),
            make_stop_result("done"),
        ]))

        await agent.work(question="q", from_checkpoint=False)
        assert order.index("fast") < order.index("slow")


class TestWorkErrorHandling:
    async def test_unknown_tool_logs_error_no_crash(self):
        """Verify unknown tool logs error no crash."""
        agent = make_agent(tool_kits={})
        tc = make_tool_call("id1", "ghost_tool", '{}')
        set_step(agent, MagicMock(side_effect=[
            make_tool_result([tc]),
            make_stop_result("done"),
        ]))

        with patch("src.agents.base.agent.logger") as mock_logger:
            result = await agent.work(question="q", from_checkpoint=False)

        assert mock_logger.error.called or mock_logger.exception.called
        assert result.response == "done"

    async def test_bad_json_args_logs_error_no_crash(self):
        """Verify bad json args logs error no crash."""
        tool = MagicMock(return_value="out")
        agent = make_agent(tool_kits={"t": tool})
        tc = make_tool_call("id1", "t", "not-json{{")
        set_step(agent, MagicMock(side_effect=[
            make_tool_result([tc]),
            make_stop_result("done"),
        ]))

        with patch("src.agents.base.agent.logger") as mock_logger:
            result = await agent.work(question="q", from_checkpoint=False)

        assert mock_logger.error.called or mock_logger.exception.called
        tool.assert_not_called()
        assert result.response == "done"


class TestWorkMaxAttempts:
    async def test_exceed_attempts_callback_fired(self):
        """Verify exceed attempts callback fired."""
        tool = MagicMock(return_value="out")
        agent = make_agent(tool_kits={"t": tool}, max_attempts=1)
        tc = make_tool_call("id1", "t", "{}")
        set_step(agent, MagicMock(return_value=make_tool_result([tc])))

        events: list[WorkTempStatus] = []
        await agent.work(
            question="q",
            from_checkpoint=False,
            update_process_callback=events.append,
        )

        processes = [e["process"] for e in events]
        assert "EXCEED_ATTEMPTS" in processes

    async def test_exceed_attempts_response_is_last_report(self):
        """Verify exceed attempts response is last report."""
        tool = MagicMock(return_value="out")
        agent = make_agent(tool_kits={"t": tool}, max_attempts=1)
        tc = make_tool_call("id1", "t", "{}")
        set_step(agent, MagicMock(return_value=make_tool_result([tc])))

        result = await agent.work(question="q", from_checkpoint=False)

        assert result.response == "partial progress"

    async def test_none_max_attempts_runs_until_stop(self):
        """Verify none max attempts runs until stop."""
        tool = MagicMock(return_value="out")
        agent = make_agent(tool_kits={"t": tool}, max_attempts=None)
        tc = make_tool_call("id1", "t", "{}")
        step_mock = MagicMock(side_effect=[
            make_tool_result([tc]),
            make_tool_result([tc]),
            make_tool_result([tc]),
            make_stop_result("finally done"),
        ])
        set_step(agent, step_mock)

        result = await agent.work(question="q", from_checkpoint=False)

        assert result.response == "finally done"
        assert step_mock.call_count == 4


class TestCompactHelpers:
    def test_inject_work_summary_adds_header(self):
        """Verify inject work summary adds header."""
        agent = make_agent()

        result = agent._inject_work_summary_into_system_message(
            {"role": "system", "content": "Base prompt"},
            "First summary",
        )

        assert result == {
            "role": "system",
            "content": "Base prompt\n\n## Previous Work Summary\n\nFirst summary",
        }

    def test_inject_work_summary_appends_to_existing_summary(self):
        """Verify inject work summary appends to existing summary."""
        agent = make_agent()
        system_message = {
            "role": "system",
            "content": "Base prompt\n\n## Previous Work Summary\n\nOld summary",
        }

        result = agent._inject_work_summary_into_system_message(system_message, "New summary")

        assert result == {
            "role": "system",
            "content": "Base prompt\n\n## Previous Work Summary\n\nOld summary\n\nNew summary",
        }


@pytest.mark.asyncio
class TestCompact:
    async def test_empty_context_returns_unchanged(self):
        """Verify empty context returns unchanged."""
        agent = make_agent()

        assert await agent.compact([]) == []

    async def test_single_user_turn_without_assistant_is_unchanged(self):
        """Verify single user turn without assistant is unchanged."""
        agent = make_agent()
        ctx = [
            {"role": "system", "content": "Base prompt"},
            {"role": "user", "content": "Current task"},
        ]

        assert await agent.compact(ctx) == ctx
        agent.openai_client.chat.completions.create.assert_not_called()

    async def test_single_user_turn_with_one_assistant_is_unchanged(self):
        """Verify single user turn with one assistant is unchanged."""
        agent = make_agent()
        ctx = [
            {"role": "system", "content": "Base prompt"},
            {"role": "user", "content": "Current task"},
            {"role": "assistant", "content": "In progress"},
        ]

        assert await agent.compact(ctx) == ctx
        agent.openai_client.chat.completions.create.assert_not_called()

    async def test_compact_keeps_last_user_when_new_request_starts(self):
        """Verify compact keeps last user when new request starts."""
        agent = make_agent()
        set_compact_summary(agent, "Summarized previous work")
        ctx = [
            {"role": "system", "content": "Base prompt"},
            {"role": "user", "content": "Old request"},
            {"role": "assistant", "content": "Old answer"},
            {"role": "user", "content": "New request"},
        ]

        result = await agent.compact(ctx)

        assert result == [
            {
                "role": "system",
                "content": f"Base prompt\n\n{_COMPACT_SUMMARY_HEADER}\n\nSummarized previous work",
            },
            {"role": "user", "content": "New request"},
        ]

        call_kwargs = agent.openai_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == "gpt-4o"
        assert call_kwargs["messages"][:-1] == ctx[:3]
        assert call_kwargs["messages"][-1]["role"] == "user"
        assert "Compact the current context" in call_kwargs["messages"][-1]["content"]

    async def test_compact_keeps_active_assistant_and_tool_messages(self):
        """Verify compact keeps active assistant and tool messages."""
        agent = make_agent()
        set_compact_summary(agent, "Finished earlier work")
        ctx = [
            {"role": "system", "content": "Base prompt"},
            {"role": "user", "content": "Old request"},
            {"role": "assistant", "content": "Old answer"},
            {"role": "user", "content": "Current request"},
            {"role": "assistant", "content": "Current progress"},
            {"role": "tool", "tool_call_id": "call-1", "content": "tool output"},
        ]

        result = await agent.compact(ctx)

        assert result == [
            {
                "role": "system",
                "content": f"Base prompt\n\n{_COMPACT_SUMMARY_HEADER}\n\nFinished earlier work",
            },
            {"role": "user", "content": "Current request"},
            {"role": "assistant", "content": "Current progress"},
            {"role": "tool", "tool_call_id": "call-1", "content": "tool output"},
        ]

        summary_messages = agent.openai_client.chat.completions.create.call_args.kwargs["messages"]
        assert summary_messages[:-1] == ctx[:4]

    async def test_compact_requires_user_message(self):
        """Verify compact requires user message."""
        agent = make_agent()

        with pytest.raises(AssertionError, match="don't have any user message"):
            await agent.compact([{"role": "system", "content": "Base prompt"}])


class TestReportCurrentProcess:
    async def test_appends_consult_message_and_returns_completion(self):
        """Verify appends consult message and returns completion."""
        agent = make_agent()
        completion = MagicMock()
        completion.choices = [MagicMock(message=MagicMock(content="Current progress reply"))]
        agent.openai_client.chat.completions.create.return_value = completion
        checkpoint = [
            {"role": "system", "content": "System"},
            {"role": "user", "content": "Original task"},
            {"role": "assistant", "content": "Checkpointed progress"},
        ]

        result = await agent.report_current_process(
            checkpoint=checkpoint,
            user_message="Where is the task now?",
        )

        assert result == "Current progress reply"
        call_kwargs = agent.openai_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == "gpt-4o"
        assert call_kwargs["messages"][:-1] == checkpoint
        assert call_kwargs["messages"][-1]["role"] == "user"
        assert "Where is the task now?" in call_kwargs["messages"][-1]["content"]

    async def test_returns_raw_completion_content(self):
        """Verify returns raw completion content."""
        agent = make_agent()
        completion = MagicMock()
        completion.choices = [MagicMock(message=MagicMock(content="magic mock content"))]
        agent.openai_client.chat.completions.create.return_value = completion

        result = await agent.report_current_process(
            checkpoint=[{"role": "system", "content": "System"}],
            user_message="status?",
        )

        assert result == "magic mock content"


class TestMwinTraceContext:
    async def test_work_opens_mwin_trace_context(self):
        """Verify agent work runs inside mwin's async trace context."""
        entered = False
        exited = False

        @asynccontextmanager
        async def fake_trace():
            nonlocal entered, exited
            entered = True
            try:
                yield
            finally:
                exited = True

        agent = make_agent()
        set_step(agent, MagicMock(return_value=make_stop_result("done")))

        with patch("src.agents.base.agent.start_trace_async", return_value=fake_trace()):
            result = await agent.work(question="q", from_checkpoint=False)

        assert result.response == "done"
        assert entered is True
        assert exited is True

    def test_stream_collector_declares_mwin_llm_tracking(self):
        """Verify stream collection is the LLM-tracked call site."""
        import inspect

        source = inspect.getsource(Agent._create_chat_completion_stream)
        assert '@track(tags=["agent", "stream"], step_type="llm", llm_provider=LLMProvider.OPENAI)' in source
