import asyncio
import inspect
import json
from typing import Literal, Any, List, Dict, Callable, Coroutine, TypedDict, Required, NotRequired
from dataclasses import dataclass
from textwrap import dedent
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, model_validator
from openai import AsyncOpenAI, RateLimitError, APIConnectionError, APIError
from openai.types.chat import ChatCompletion, ChatCompletionMessage
from openai.types.chat.chat_completion_message_param import (
    ChatCompletionMessageParam, 
    ChatCompletionSystemMessageParam, 
    ChatCompletionUserMessageParam,
    ChatCompletionAssistantMessageParam,
    ChatCompletionToolMessageParam
)
from openai.types.chat.chat_completion_message_tool_call import ChatCompletionMessageToolCall
from openai.types.chat.chat_completion_chunk import ChoiceDeltaToolCall
from openai.types.chat.chat_completion_message_tool_call import Function
from mwin import track
from src.logger import logger
from src.exception import ToolNotFoundError
from src.sandbox import Sandbox
from src.tools.skills import (
    SkillRegistry,
    SkillToolKit,
    append_skills_system_prompt,
    project_path_for_repo,
)
from src.utils.asynchronous import make_async
from src.utils.event_metadata import build_safe_event_metadata


_COMPACT_SUMMARY_HEADER = "## Previous Work Summary"


def _json_object(raw: str) -> dict[str, Any]:
    """Parse tool arguments when they are a JSON object."""
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


@dataclass
class BaseAgentStepResult:
    finish_reason: Literal["stop", "length", "tool_calls", "content_filter", "function_call"]
    reasoning: str | None
    completion_content: str | None
    tool_calls: List[ChatCompletionMessageToolCall] | None
    message_param: ChatCompletionMessage
    current_step_consume_tokens: int


@dataclass
class BaseAgentResponse:
    response: str


@dataclass
class StreamCompletionResult:
    message: ChatCompletionMessage
    finish_reason: str | None
    reasoning: str | None
    usage_tokens: int


@dataclass
class SampleConfig:
    top_k: int | None
    top_p: int | None
    extra_body: Dict[str, Any] | None


@dataclass
class ModelConfig:
    model: str
    max_length_context: int


class WorkTempStatus(TypedDict):
    process: Required[Literal["START", "PROCESS", "SAVE_CHECKPOINT", "COMPLETED", "FAILED", "EXCEED_ATTEMPTS"]]
    agent_content: Required[str | None]
    current_use_tool: Required[List[str] | None]
    current_use_tool_args: Required[List[Dict[str, Any]] | None]

    context: NotRequired[List[ChatCompletionMessageParam | ChatCompletionMessage]]
    """Context is complete current turn context when process = SAVE_CHECKPOINT"""


class Agent(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    tool_kits: Dict[str, Callable] | None
    # Instance-owned because project-specific tools must not leak across agent instances.
    tool_definitions: List[dict] = Field(default_factory=list)
    base_url: str
    api_key: str
    system_prompt: str
    llm_config: ModelConfig
    sample_config: SampleConfig | None = None
    max_attempts: int | None = None
    openai_client: AsyncOpenAI | None = None
    current_turn_ctx_len: int = 0

    _skill_registry: SkillRegistry | None = PrivateAttr(default=None)


    @model_validator(mode="after")
    def init_openai_client(self):
        """Initialize the OpenAI client after model validation.

        Returns:
            The current agent instance with an initialized client when configured.
        """
        if self.base_url and self.api_key:
            self.openai_client = AsyncOpenAI(
                base_url=self.base_url,
                api_key=self.api_key,
                default_headers={
                    "User-Agent": "codex-tui/0.135.0 (Ubuntu 24.4.0; x86_64) WindowsTerminal (codex-tui; 0.135.0)",
                },
            )
        return self

    def _install_skills(self, registry: SkillRegistry) -> list[str]:
        """Install a skill catalog into this agent instance.

        Args:
            registry: Skills available to this agent instance.

        Returns:
            Names of discovered skills.
        """
        if self._skill_registry is not None:
            self._ensure_skill_tool()
            return [skill.name for skill in self._skill_registry.skills]

        self._skill_registry = registry
        if not registry:
            return []

        self.system_prompt = append_skills_system_prompt(self.system_prompt, registry)
        self._ensure_skill_tool()
        return [skill.name for skill in registry.skills]

    def _ensure_skill_tool(self):
        """Register the read_skill callable when skills are available."""
        if not self._skill_registry:
            return
        if self.tool_kits is None:
            self.tool_kits = {}
        self.tool_kits.update(SkillToolKit(self._skill_registry).all_tools)

    async def configure_skills(self, sandbox: Sandbox, github_repo: str | None) -> list[str]:
        """Load skills from the checked-out project directory when it exists."""
        if not github_repo:
            return self._install_skills(SkillRegistry())
        registry = await SkillRegistry.from_sandbox_project(
            sandbox,
            project_path=project_path_for_repo(github_repo),
            agent_name=self.name.lower(),
        )
        return self._install_skills(registry)

    @track(tags=["agent"])
    async def work(
        self,
        question: str,
        *,
        from_checkpoint: bool,
        checkpoint: List[ChatCompletionMessageParam] | None = None,
        update_process_callback: Callable[[WorkTempStatus], None] | None = None,
    ) -> BaseAgentResponse:
        """Agent start to work for question.
        If agent resumes from a checkpoint from_checkpoint=True and pass a list of ChatCompletionMessageParam - checkpoint which persists
        system message, user message, assistant message and optional tool messages. The question is following by the checkpoint.

        Args:
            question: user question
            from_checkpoint: start from checkpoint instead of building a fresh context
            checkpoint: complete current turn context persisted at a safe replay boundary. 
                        It includes complete system, user, assistant and tool messages.
            update_process_callback: callback to update agent work's state
        """

        terminate = False
        tries = 0
        base_agent_response = BaseAgentResponse(response="")

        if from_checkpoint:
            assert checkpoint is not None, "Checkpoint is required when from_checkpoint=True"
            # copy a new checkpoint to prevent in-place edit checkpoint
            user_message: ChatCompletionUserMessageParam = {"role": "user", "content": question}
            current_turn_ctx = list(checkpoint)
            current_turn_ctx.append(user_message)
        else:
            system_message: ChatCompletionSystemMessageParam = {"role": "system", "content": self.system_prompt}
            user_message: ChatCompletionUserMessageParam = {"role": "user", "content": question}
            current_turn_ctx = [system_message, user_message]

        self._process_callback(
            update_process_callback,
            work_temp_status=WorkTempStatus(
                process="START",
                agent_content=None,
                current_use_tool=None,
                current_use_tool_args=None,
            ),
        )

        while not terminate and (True if self.max_attempts is None else tries <= self.max_attempts):
            if self.current_turn_ctx_len >= self.llm_config.max_length_context * 0.9:
                logger.info(f"Agent `{self.name}` is compacting...")
                current_turn_ctx = await self.compact(current_turn_ctx)

            try:
                step_response = await self.step(current_turn_ctx)
            except RateLimitError:
                logger.warning(f"Agent `{self.name}` requests {self.llm_config.model} to limit. Wait two minutes")
                await asyncio.sleep(120)
                continue

            except APIConnectionError as openai_conn_error:
                logger.warning(
                    f"Agent {self.name} fails to call llm because openai client is disconnect. " \
                    "Try to reconnect it after one minute. "
                )
                await asyncio.sleep(60)
                continue

            except APIError as api_error:
                # Concurrency limit trigger the api error now
                api_error_msg = str(api_error)
                if "limit" in api_error_msg or "retry" in api_error_msg:
                    logger.warning(
                        f"Agent {self.name} triggers concurrency limit and start waiting for 1 minute."
                    )
                    await asyncio.sleep(60)
                continue
            
            tries += 1
        
            assistant_msg = step_response.message_param
            # elements of current_turn_ctx are all ChatCompletionMessageParam instead of ChatCompletionMessage
            current_turn_ctx.append(assistant_msg.model_dump(mode="json", exclude_none=True))
            self.current_turn_ctx_len = step_response.current_step_consume_tokens

            if step_response.finish_reason == "stop":
                terminate = True
                self._process_callback(
                    update_process_callback,
                    work_temp_status=WorkTempStatus(
                        process="COMPLETED",
                        agent_content=step_response.completion_content,
                        current_use_tool=None,
                        current_use_tool_args=None,
                    ),
                )
                base_agent_response.response = step_response.completion_content

            else:
                if step_response.finish_reason == "tool_calls" and step_response.tool_calls is not None:
                    tool_names = [tc.function.name for tc in step_response.tool_calls]
                    tool_args = [
                        build_safe_event_metadata(
                            _json_object(tc.function.arguments),
                            tool_name=tc.function.name,
                            summary=f"{tc.function.name} called",
                        )
                        for tc in step_response.tool_calls
                    ]
                    self._process_callback(
                        update_process_callback,
                        work_temp_status=WorkTempStatus(
                            process="PROCESS",
                            agent_content=step_response.completion_content,
                            current_use_tool=tool_names,
                            current_use_tool_args=tool_args,
                        ),
                    )

                    tc_ids: List[str] = []
                    coroutines: List[Coroutine] = []
                    for tc in step_response.tool_calls:
                        tc_id = tc.id
                        tc_name = tc.function.name
                        tc_args = tc.function.arguments
                        try:
                            if tc_name not in self.tool_kits.keys():
                                raise ToolNotFoundError(f"{tc_name} not in agent `{self.name}` toolkits.")
                            tc_callable = self.tool_kits[tc_name]
                            args_dict = json.loads(tc_args)
                            if inspect.iscoroutinefunction(tc_callable) is False:
                                task = make_async(func=tc_callable, **args_dict)
                            else:
                                task = tc_callable(**args_dict)
                            tc_ids.append(tc_id)
                            coroutines.append(task)

                        except json.decoder.JSONDecodeError:
                            logger.exception(
                                f"Agent `{self.name}` fail to call tool `{tc_name}` "
                                f"because arguments generated from him/her is not a json str"
                            )

                        except ToolNotFoundError as tfe:
                            logger.exception(str(tfe))

                    assert len(tc_ids) == len(coroutines), "The length of tool call ids is not the same as the length of tools to execute."
                    coroutines_results = await asyncio.gather(*coroutines, return_exceptions=True)
                    tool_messages: List[ChatCompletionToolMessageParam] = [
                        {"role": "tool", "tool_call_id": tc_id, "content": str(result)}
                        for tc_id, result in zip(tc_ids, coroutines_results)
                    ]
                    current_turn_ctx.extend(tool_messages)
                    self._process_callback(
                        update_process_callback,
                        work_temp_status=WorkTempStatus(
                            process="SAVE_CHECKPOINT",
                            agent_content=step_response.completion_content,
                            current_use_tool=None,
                            current_use_tool_args=None,
                            context=current_turn_ctx,
                        ),
                    )
        # terminate is True only when agent finish reason is stop.
        if not terminate:
            agent_content = self.last_report_current_process(current_turn_ctx=current_turn_ctx)
            self._process_callback(
                update_process_callback,
                work_temp_status=WorkTempStatus(
                    process="EXCEED_ATTEMPTS",
                    agent_content=agent_content,
                    current_use_tool=None,
                    current_use_tool_args=None,
                )
            )
            base_agent_response.response = agent_content
        # save the final assistant message into checkpoint
        else:
            self._process_callback(
                update_process_callback,
                work_temp_status=WorkTempStatus(
                    process="SAVE_CHECKPOINT",
                    agent_content=step_response.completion_content,
                    current_use_tool=None,
                    current_use_tool_args=None,
                    context=current_turn_ctx,
                ),
            )

        return base_agent_response
    

    async def report_current_process(
        self,
        checkpoint: List[ChatCompletionMessageParam],
        user_message: str,
    ) -> str:
        """Agent report its new process for convienence to know where agent is.
        
        Args:
            checkpoint: agent checkpoint for this task
            user_message: user quesiton
        
        Returns:
            Report from agent
        """
        if self.openai_client is None:
            raise RuntimeError(f"Agent `{self.name}` is missing an initialized OpenAI client.")

        consult_turn_ctx = list(checkpoint)
        consult_turn_ctx.append(
            {
                "role": "user",
                "content": dedent(
                    f"""
                    You are answering a question about the current progress of an existing task.
                    Base your answer only on the task context already provided in this conversation.
                    Do not continue the task, do not invent new completed work, and do not call tools.
                    If the checkpoint is incomplete or stale, say what is known and what is uncertain.
                    Focus on the latest completed step, the current in-progress step, blockers, and the next likely step.

                    User question:
                    {user_message}
                    """
                ).strip(),
            }
        )

        kwargs: dict[str, Any] = {
            "model": self.llm_config.model,
            "messages": consult_turn_ctx,
        }
        if self.sample_config:
            if self.sample_config.top_p is not None:
                kwargs["top_p"] = self.sample_config.top_p
            if self.sample_config.extra_body:
                kwargs["extra_body"] = self.sample_config.extra_body

        completion: ChatCompletion = await self.openai_client.chat.completions.create(**kwargs)
        content = completion.choices[0].message.content
        return content

    def _process_callback(
        self,
        callback: Callable[[WorkTempStatus], None] | None,
        work_temp_status: WorkTempStatus,
    ):
        """Invoke a progress callback when one is configured.

        Args:
            callback: Optional callback receiving work status updates.
            work_temp_status: Status payload to pass to the callback.
        """
        if callback:
            callback(work_temp_status)

    async def _create_chat_completion_stream(self, kwargs: Dict[str, Any]) -> StreamCompletionResult:
        """Create a streaming chat completion and collect its final message.

        Args:
            kwargs: Keyword arguments for the chat completion request.

        Returns:
            Aggregated stream result including message, reasoning, and usage.

        Raises:
            RuntimeError: If the OpenAI client has not been initialized.
        """
        if self.openai_client is None:
            raise RuntimeError(f"Agent `{self.name}` is missing an initialized OpenAI client.")

        stream_kwargs: Dict[str, Any] = dict(kwargs)
        stream_kwargs["stream"] = True
        stream_kwargs["stream_options"] = {"include_usage": True}

        content_parts: list[str] = []
        reasoning_parts: list[str] = []
        finish_reason: str | None = None
        usage_tokens = 0
        tool_calls_state: dict[int, dict[str, str]] = {}

        stream = await self.openai_client.chat.completions.create(**stream_kwargs)
        async for chunk in stream:
            if getattr(chunk, "usage", None) is not None:
                usage_tokens = chunk.usage.total_tokens or usage_tokens

            if not chunk.choices:
                continue
            choice = chunk.choices[0]
            if choice.finish_reason is not None:
                finish_reason = choice.finish_reason

            delta = choice.delta
            if delta.content:
                content_parts.append(delta.content)

            reasoning_content = getattr(delta, "reasoning_content", None)
            if reasoning_content:
                reasoning_parts.append(reasoning_content)

            if delta.tool_calls:
                for tc in delta.tool_calls:
                    tool_calls_state = self._merge_tool_call_delta(tool_calls_state, tc)

        tool_calls = self._build_tool_calls(tool_calls_state)
        message = ChatCompletionMessage(
            role="assistant",
            content="".join(content_parts) or None,
            tool_calls=tool_calls or None,
        )
        reasoning = "".join(reasoning_parts) if reasoning_parts else None

        return StreamCompletionResult(
            message=message,
            finish_reason=finish_reason,
            reasoning=reasoning,
            usage_tokens=usage_tokens if usage_tokens else 0,
        )

    def _merge_tool_call_delta(
        self,
        tool_calls_state: dict[int, dict[str, str]],
        tc: ChoiceDeltaToolCall,
    ) -> dict[int, dict[str, str]]:
        """Merge a streamed tool-call delta into accumulated state.

        Args:
            tool_calls_state: Current tool-call fragments keyed by index.
            tc: Incoming streamed tool-call delta.

        Returns:
            Updated tool-call state.
        """
        if tc.index not in tool_calls_state:
            tool_calls_state[tc.index] = {"id": "", "name": "", "arguments": ""}
        state = tool_calls_state[tc.index]
        if tc.id:
            state["id"] = tc.id
        if tc.function:
            if tc.function.name:
                state["name"] = tc.function.name
            if tc.function.arguments:
                state["arguments"] += tc.function.arguments
        return tool_calls_state

    def _build_tool_calls(self, tool_calls_state: dict[int, dict[str, str]]) -> list[ChatCompletionMessageToolCall]:
        """Build final tool-call objects from accumulated stream state.

        Args:
            tool_calls_state: Tool-call fragments keyed by stream index.

        Returns:
            Ordered complete tool calls with names and arguments.
        """
        return [
            ChatCompletionMessageToolCall(
                id=state["id"],
                type="function",
                function=Function(name=state["name"], arguments=state["arguments"]),
            )
            for _, state in sorted(tool_calls_state.items(), key=lambda item: item[0])
            if state["name"]
        ]

    async def close(self) -> None:
        """Close the agent OpenAI client if it is open."""
        if self.openai_client is None:
            return

        try:
            await self.openai_client.close()
        except Exception:
            logger.exception("Failed to close OpenAI client for agent `%s`.", self.name)
        finally:
            self.openai_client = None

    async def step(self, current_turn_ctx: List[ChatCompletionMessageParam]) -> BaseAgentStepResult:
        """Execute one agent step.

        Args:
            current_turn_ctx: Current conversation context.

        Raises:
            NotImplementedError: Always raised by the base class.
        """
        raise NotImplementedError(f"Agent `{self.name}` doesn't implement step function.")

    def last_report_current_process(self, current_turn_ctx: List[ChatCompletionMessageParam]) -> str:
        """Return a last-known progress report for unfinished work.

        Args:
            current_turn_ctx: Current conversation context.

        Raises:
            NotImplementedError: Always raised by the base class.
        """
        raise NotImplementedError(f"Agent `{self.name}` doesn't implement last_report_current_process function.")

    @staticmethod
    def create(cls, *args, **kwargs) -> "Agent":
        """Create an agent instance from subclass-specific configuration.

        Args:
            cls: Agent subclass to construct.
            *args: Positional arguments for the subclass factory.
            **kwargs: Keyword arguments for the subclass factory.

        Raises:
            NotImplementedError: Always raised by the base class.
        """
        raise NotImplementedError(f"Agent `{cls.__name__}` doesn't implement create().")
    
    @track(tags=["compact"], step_type="llm")
    async def compact(self, current_turn_ctx: List[ChatCompletionMessageParam]) -> List[ChatCompletionMessageParam]:
        """Keep system message + last user message + optional[last turn of assistant+optional[tool] messages].
        Spilt current_turn_ctx into four parts - system, ctx before last user message, last user message, ctx after last user message.
        The last three turn of assistant+optional(tool) messages is from ctx after last user message.
        Denote ctx before last user message as ctx1 and ctx after last user message as ctx2.
        Previous work should be ctx1 + some of ctx2.
        Some of ctx2 means from first message in it to the last tenth messages.

        For example:
        [system_message, 
        user_message_1, assistant_message1, tool_message_1, assistant_message_2, 
        user_message_2,
        assistant_message_3, tool_message_2, tool_message_3, assistant_message_4, tool_message_4, tool_message_5, tool_message_6, assistant_message_5, tool_message_7, assistant_message_6, tool_message_8, assistant_message_7, tool_message_9]
        
        the last user message is user_message_2. According to compact principle, we keep system_message, user_message_2 and assistant_message_7, tool_message_9.
        Then denote `user_message_1, assistant_message1, tool_message_1, assistant_message_2` as previous_work_1.
        Denote `assistant_message_3, tool_message_2, tool_message_3, assistant_message_4, tool_message_4, tool_message_5, tool_message_6, assistant_message_5, tool_message_7, assistant_message_6, tool_message_8` as previous_work_2.
        Finally inject summary to system_message.

        In self._summarize_work() the prompt should tell agent summary work based on user message. Different messages are working on different user messages. Summary must follow the principle.
        
        Summarize other messages -> inject into system message"""
        if not current_turn_ctx:
            logger.warning(f"Agent `{self.name}` is compacting an empyty message.")
            return current_turn_ctx

        system_message = current_turn_ctx[0]
        assert system_message["role"] == "system", "Fail to compact:" \
            f"The first of messages to pass to agent `{self.name}` is not a system message."

        last_user_index = next(
            (
                idx for idx in range(len(current_turn_ctx) - 1, 0, -1)
                if current_turn_ctx[idx]["role"] == "user"
            ),
            None,
        )
        assert last_user_index is not None, "Fail to compact: " \
            f"The messages to pass to agent `{self.name}` don't have any user message. Ensure at least one user message in it."

        last_assistant_index = next(
            (
                idx for idx in range(len(current_turn_ctx) - 1, last_user_index, -1)
                if current_turn_ctx[idx]["role"] == "assistant"
            ),
            None,
        )
        return await self._compact_in_the_same_session(
            ctx=current_turn_ctx,
            last_user_index=last_user_index,
            last_assistant_index=last_assistant_index,
        )
    
    async def _compact_in_the_same_session(
        self,
        ctx: List[ChatCompletionMessageParam],
        last_user_index: int,
        last_assistant_index: int | None,
    ) -> List[ChatCompletionMessageParam]:
        """
        Compact ctx in the same session. It also keeps kv-cache.
        Create a new user message to compact the current context into a summary for next agent's work.
        The summary contains what agent solves, how he/she works and what next agent have to work for.
        In this condition we will consider two condtions:
        - last user request but without any assistant message
        - last user request but with assistant message
        The first condition means agent compacts contexts during the user requests a new task.
        The second condition means agent compacts contexts when he/she is working for the last user request.
        The function is implemented for both two conditions.
        Tell agent focus on messages except the last user request for one condition and focus on messages except the last
        assistant message + following tool messages(they're optional) for second condition.
        The function has to prepare two prompts to compact for two conditions.

        Args:
            ctx: current context to be compact
            last_user_index: last user message index
            last_assistant_index: last assistant message index
        """

        system_message = ctx[0]
        assert system_message["role"] == "system", "Fail to compact in the same session: " \
            f"The first of messages to pass to agent `{self.name}` is not a system message."

        has_assistant_after_last_user = (
            last_assistant_index is not None
            and last_assistant_index > last_user_index
        )

        if not has_assistant_after_last_user and last_user_index == 1:
            return ctx
        if has_assistant_after_last_user and last_user_index == 1 and last_assistant_index == 2:
            return ctx

        compact_prompt = dedent("""
            Compact the current context into a short summary for the next agent in the same session.
            The summary must contain:
            1. what has been solved already;
            2. how the agent worked, including important tool usage, intermediate results and decisions;
            3. what the next agent still has to work on.
            4. what previous work does if you have a previous work report.
            Return summary only. If there is no previous work to summarize, return an empty string.
        """).strip()

        # If not last assistant_after_last_user message -> remove the user message from contexts -> pass contexts to summary
        #      -> Get the summary -> inject into system -> return [system_msg, last_usr_msg]
        # Else -> Remove the last assistant message and following tool messages from contexts -> pass contexts to summary
        #      -> Get the summary -> inject into system -> return [system_msg, last_usr_msg, last_assistant_msg, following tool messages]
        if not has_assistant_after_last_user:
            ctx_for_summary = ctx[:last_user_index]
            compacted_tail = [ctx[last_user_index]]
        else:
            ctx_for_summary = ctx[:last_assistant_index]
            compacted_tail = [ctx[last_user_index], *ctx[last_assistant_index:]]

        summary_request: ChatCompletionUserMessageParam = {
            "role": "user",
            "content": compact_prompt,
        }
        summary_messages = ctx_for_summary + [summary_request]

        kwargs: Dict[str, Any] = {
            "model": self.llm_config.model,
            "messages": summary_messages,
        }
        if self.sample_config:
            if self.sample_config.top_p is not None:
                kwargs["top_p"] = self.sample_config.top_p
            if self.sample_config.extra_body:
                kwargs["extra_body"] = self.sample_config.extra_body

        summary = ""
        if self.openai_client is None:
            logger.warning(f"Agent `{self.name}` occur an unexpected error: doesn't init openai client. Now initializing client.")
            self.openai_client = AsyncOpenAI(
                base_url=self.base_url,
                api_key=self.api_key,
                default_headers={
                    "User-Agent": "codex-tui/0.135.0 (Ubuntu 24.4.0; x86_64) WindowsTerminal (codex-tui; 0.135.0)",
                },
            )

        completion: ChatCompletion = await self.openai_client.chat.completions.create(**kwargs)
        summary = completion.choices[0].message.content or ""

        compacted_system = self._inject_work_summary_into_system_message(system_message, summary)
        return [compacted_system, *compacted_tail]
    

    def _spilt_base_and_previous_work_from_system_message(
        self,
        system_message: ChatCompletionSystemMessageParam,
    ) -> tuple[str, str]:
        """Return base content and previous work summary"""
        content = system_message["content"]
        if _COMPACT_SUMMARY_HEADER not in content:
            return content, ""

        base_content, existing_work_summary = content.split(_COMPACT_SUMMARY_HEADER, 1)
        return base_content.strip(), existing_work_summary.strip()

    def _inject_work_summary_into_system_message(
        self,
        system_message: ChatCompletionMessageParam,
        summary: str,
    ) -> ChatCompletionSystemMessageParam:
        """Inject compacted work summary into a system message.

        Args:
            system_message: Existing system message to update.
            summary: New summary text to append.

        Returns:
            Updated system message with summary content.
        """
        base_content, previous_work = self._spilt_base_and_previous_work_from_system_message(system_message)
        parts: List[str] = []
        if base_content:
            parts.append(base_content)
        if previous_work:
            parts.append(f"{_COMPACT_SUMMARY_HEADER}\n\n{previous_work}")
            if summary:
                parts.append(summary)
        elif not previous_work and summary:
            parts.append(f"{_COMPACT_SUMMARY_HEADER}\n\n{summary}")

        return {
            "role": "system",
            "content": "\n\n".join(parts)
        }
