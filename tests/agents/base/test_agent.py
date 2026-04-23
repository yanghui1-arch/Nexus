import pytest
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
    return ModelConfig(model="gpt-4o", max_length_context=8192)


def make_tool_call(id: str, name: str, arguments: str) -> ChatCompletionMessageToolCall:
    return ChatCompletionMessageToolCall(
        id=id,
        type="function",
        function=Function(name=name, arguments=arguments),
    )


def make_stop_result(content: str = "done") -> BaseAgentStepResult:
    return BaseAgentStepResult(
        finish_reason="stop",
        reasoning=None,
        completion_content=content,
        tool_calls=None,
        message_param={"role": "assistant", "content": content},
        current_step_consume_tokens=10,
    )


def make_tool_result(tool_calls: list) -> BaseAgentStepResult:
    return BaseAgentStepResult(
        finish_reason="tool_calls",
        reasoning=None,
        completion_content=None,
        tool_calls=tool_calls,
        message_param={"role": "assistant", "content": None, "tool_calls": []},
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
        raise NotImplementedError("patch me")

    def SOP(self, work_history: list) -> str:
        return "SOP string"

    def last_report_current_process(self, current_turn_ctx: list) -> str:
        return "partial progress"


def make_agent(tool_kits=None, max_attempts=None) -> ConcreteAgent:
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
    completion = MagicMock()
    completion.choices = [MagicMock(message=MagicMock(content=summary))]
    agent.openai_client.chat.completions.create.return_value = completion


class TestProcessCallback:
    def test_calls_callback_with_status(self):
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
        agent = make_agent()
        status: WorkTempStatus = {
            "process": "START",
            "agent_content": None,
            "current_use_tool": None,
            "current_use_tool_args": None,
        }
        agent._process_callback(None, status)


class TestInitCurrentTurnCtx:
    def test_order_system_history_current_user(self):
        agent = make_agent()
        system = {"role": "system", "content": "sys"}
        history: list = [{"role": "user", "content": "hist"}]
        current: list = [{"role": "assistant", "content": "curr"}]
        user = {"role": "user", "content": "q"}

        ctx = agent._init_current_turn_ctx(
            system_message=system,
            user_message=user,
            current_session_ctx=current,
            history_session_ctx=history,
        )

        assert ctx[0] == system
        assert ctx[1] == history[0]
        assert ctx[2] == current[0]
        assert ctx[3] == user

    def test_empty_history_and_current(self):
        agent = make_agent()
        system = {"role": "system", "content": "sys"}
        user = {"role": "user", "content": "q"}
        ctx = agent._init_current_turn_ctx(system, user, [], [])
        assert ctx == [system, user]


class TestWorkStop:
    async def test_returns_response_on_stop(self):
        agent = make_agent()
        set_step(agent, MagicMock(return_value=make_stop_result("final answer")))

        result = await agent.work(question="q", current_session_ctx=[], history_session_ctx=[])

        assert result.response == "final answer"

    async def test_from_checkpoint_uses_checkpoint_as_current_turn_context(self):
        agent = make_agent()
        checkpoint = [
            {"role": "system", "content": "checkpoint system"},
            {"role": "user", "content": "original task"},
            {"role": "assistant", "content": "checkpointed progress"},
        ]
        captured_contexts: list[list] = []

        async def capture_step(current_turn_ctx: list) -> BaseAgentStepResult:
            captured_contexts.append(list(current_turn_ctx))
            return make_stop_result("resumed answer")

        set_step(agent, AsyncMock(side_effect=capture_step))

        result = await agent.work(
            question="fresh question must not be appended",
            current_session_ctx=[{"role": "assistant", "content": "fresh current"}],
            history_session_ctx=[{"role": "user", "content": "fresh history"}],
            from_checkpoint=True,
            checkpoint=checkpoint,
        )

        assert result.response == "resumed answer"
        assert captured_contexts == [checkpoint]

    async def test_from_checkpoint_requires_checkpoint(self):
        agent = make_agent()

        with pytest.raises(ValueError, match="checkpoint is required"):
            await agent.work(
                question="q",
                current_session_ctx=[],
                history_session_ctx=[],
                from_checkpoint=True,
            )

    async def test_start_and_completed_callbacks_fired(self):
        agent = make_agent()
        set_step(agent, MagicMock(return_value=make_stop_result("done")))
        events: list[WorkTempStatus] = []

        await agent.work(
            question="q",
            current_session_ctx=[],
            history_session_ctx=[],
            update_process_callback=events.append,
        )

        processes = [e["process"] for e in events]
        assert processes[0] == "START"
        assert "COMPLETED" in processes

    async def test_sop_set_on_stop(self):
        agent = make_agent()
        set_step(agent, MagicMock(return_value=make_stop_result("done")))

        result = await agent.work(question="q", current_session_ctx=[], history_session_ctx=[])

        assert result.sop == "SOP string"

    async def test_no_callback_does_not_raise(self):
        agent = make_agent()
        set_step(agent, MagicMock(return_value=make_stop_result("done")))

        result = await agent.work(question="q", current_session_ctx=[], history_session_ctx=[])
        assert result.response == "done"


class TestWorkToolCalls:
    async def test_sync_tool_is_called_and_result_appended(self):
        sync_tool = MagicMock(return_value="tool-output")
        agent = make_agent(tool_kits={"my_tool": sync_tool})

        tc = make_tool_call("id1", "my_tool", '{"x": 1}')
        set_step(agent, MagicMock(side_effect=[
            make_tool_result([tc]),
            make_stop_result("done"),
        ]))

        result = await agent.work(question="q", current_session_ctx=[], history_session_ctx=[])

        sync_tool.assert_called_once_with(x=1)
        assert result.response == "done"

    async def test_async_tool_is_awaited(self):
        async_tool = AsyncMock(return_value="async-output")
        agent = make_agent(tool_kits={"async_tool": async_tool})

        tc = make_tool_call("id1", "async_tool", '{"y": 2}')
        set_step(agent, MagicMock(side_effect=[
            make_tool_result([tc]),
            make_stop_result("done"),
        ]))

        await agent.work(question="q", current_session_ctx=[], history_session_ctx=[])
        async_tool.assert_awaited_once_with(y=2)

    async def test_process_callback_fired_on_tool_call(self):
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
            current_session_ctx=[],
            history_session_ctx=[],
            update_process_callback=events.append,
        )

        process_events = [e["process"] for e in events]
        assert "PROCESS" in process_events
        process_status = next(e for e in events if e["process"] == "PROCESS")
        assert process_status["current_use_tool"] == ["t"]

    async def test_multiple_tool_calls_dispatched_in_parallel(self):
        import asyncio
        order: list[str] = []

        async def slow_tool(**_):
            await asyncio.sleep(0.05)
            order.append("slow")
            return "slow"

        async def fast_tool(**_):
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

        await agent.work(question="q", current_session_ctx=[], history_session_ctx=[])
        assert order.index("fast") < order.index("slow")


class TestWorkErrorHandling:
    async def test_unknown_tool_logs_error_no_crash(self):
        agent = make_agent(tool_kits={})
        tc = make_tool_call("id1", "ghost_tool", '{}')
        set_step(agent, MagicMock(side_effect=[
            make_tool_result([tc]),
            make_stop_result("done"),
        ]))

        with patch("src.agents.base.agent.logger") as mock_logger:
            result = await agent.work(question="q", current_session_ctx=[], history_session_ctx=[])

        assert mock_logger.error.called or mock_logger.exception.called
        assert result.response == "done"

    async def test_bad_json_args_logs_error_no_crash(self):
        tool = MagicMock(return_value="out")
        agent = make_agent(tool_kits={"t": tool})
        tc = make_tool_call("id1", "t", "not-json{{")
        set_step(agent, MagicMock(side_effect=[
            make_tool_result([tc]),
            make_stop_result("done"),
        ]))

        with patch("src.agents.base.agent.logger") as mock_logger:
            result = await agent.work(question="q", current_session_ctx=[], history_session_ctx=[])

        assert mock_logger.error.called or mock_logger.exception.called
        tool.assert_not_called()
        assert result.response == "done"


class TestWorkMaxAttempts:
    async def test_exceed_attempts_callback_fired(self):
        tool = MagicMock(return_value="out")
        agent = make_agent(tool_kits={"t": tool}, max_attempts=1)
        tc = make_tool_call("id1", "t", "{}")
        set_step(agent, MagicMock(return_value=make_tool_result([tc])))

        events: list[WorkTempStatus] = []
        await agent.work(
            question="q",
            current_session_ctx=[],
            history_session_ctx=[],
            update_process_callback=events.append,
        )

        processes = [e["process"] for e in events]
        assert "EXCEED_ATTEMPTS" in processes

    async def test_exceed_attempts_response_is_last_report(self):
        tool = MagicMock(return_value="out")
        agent = make_agent(tool_kits={"t": tool}, max_attempts=1)
        tc = make_tool_call("id1", "t", "{}")
        set_step(agent, MagicMock(return_value=make_tool_result([tc])))

        result = await agent.work(question="q", current_session_ctx=[], history_session_ctx=[])

        assert result.response == "partial progress"

    async def test_none_max_attempts_runs_until_stop(self):
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

        result = await agent.work(question="q", current_session_ctx=[], history_session_ctx=[])

        assert result.response == "finally done"
        assert step_mock.call_count == 4


class TestCompactHelpers:
    def test_inject_work_summary_adds_header(self):
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
        agent = make_agent()

        assert await agent.compact([]) == []

    async def test_single_user_turn_without_assistant_is_unchanged(self):
        agent = make_agent()
        ctx = [
            {"role": "system", "content": "Base prompt"},
            {"role": "user", "content": "Current task"},
        ]

        assert await agent.compact(ctx) == ctx
        agent.openai_client.chat.completions.create.assert_not_called()

    async def test_single_user_turn_with_one_assistant_is_unchanged(self):
        agent = make_agent()
        ctx = [
            {"role": "system", "content": "Base prompt"},
            {"role": "user", "content": "Current task"},
            {"role": "assistant", "content": "In progress"},
        ]

        assert await agent.compact(ctx) == ctx
        agent.openai_client.chat.completions.create.assert_not_called()

    async def test_compact_keeps_last_user_when_new_request_starts(self):
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
        agent = make_agent()

        with pytest.raises(AssertionError, match="don't have any user message"):
            await agent.compact([{"role": "system", "content": "Base prompt"}])


class TestReportCurrentProcess:
    async def test_appends_consult_message_and_returns_completion(self):
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
        agent = make_agent()
        completion = MagicMock()
        completion.choices = [MagicMock(message=MagicMock(content="magic mock content"))]
        agent.openai_client.chat.completions.create.return_value = completion

        result = await agent.report_current_process(
            checkpoint=[{"role": "system", "content": "System"}],
            user_message="status?",
        )

        assert result == "magic mock content"
