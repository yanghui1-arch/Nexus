import asyncio
import inspect
import json
from typing import Literal, Any, List, Dict, Callable, Coroutine, TypedDict, Required
from dataclasses import dataclass
from textwrap import dedent
from pydantic import BaseModel, ConfigDict, model_validator
from openai import OpenAI, RateLimitError
from openai.types.chat import ChatCompletion
from openai.types.chat.chat_completion_message_param import (
    ChatCompletionMessageParam, 
    ChatCompletionSystemMessageParam, 
    ChatCompletionUserMessageParam,
    ChatCompletionAssistantMessageParam,
    ChatCompletionToolMessageParam
)
from openai.types.chat.chat_completion_message_tool_call import ChatCompletionMessageToolCall
from mwin import track, StepType
from src.logger import logger
from src.exception import ToolNotFoundError
from src.utils.asynchronous import make_async


_COMPACT_SUMMARY_HEADER = "## Previous Work Summary"


@dataclass
class BaseAgentStepResult:
    finish_reason: Literal["stop", "length", "tool_calls", "content_filter", "function_call"]
    reasoning: str | None
    completion_content: str | None
    tool_calls: List[ChatCompletionMessageToolCall] | None
    message_param: ChatCompletionAssistantMessageParam
    current_step_consume_tokens: int


@dataclass
class BaseAgentResponse:
    response: str
    sop: str | None


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
    process: Required[Literal["START", "PROCESS", "COMPLETED", "FAILED", "EXCEED_ATTEMPTS"]]
    agent_content: Required[str | None]
    current_use_tool: Required[List[str] | None]
    current_use_tool_args: Required[List[Dict[str, Any]] | None]


class Agent(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    tool_kits: Dict[str, Callable] | None
    base_url: str
    api_key: str
    system_prompt: str
    llm_config: ModelConfig
    sample_config: SampleConfig | None = None
    max_attempts: int | None = None
    openai_client: OpenAI | None = None


    @model_validator(mode="after")
    def init_openai_client(self):
        if self.base_url and self.api_key:
            self.openai_client = OpenAI(base_url=self.base_url, api_key=self.api_key)
        return self


    async def work(
        self, 
        question: str,
        current_session_ctx: List[ChatCompletionUserMessageParam | ChatCompletionAssistantMessageParam | ChatCompletionToolMessageParam],
        history_session_ctx: List[ChatCompletionUserMessageParam | ChatCompletionAssistantMessageParam | ChatCompletionToolMessageParam],
        update_process_callback: Callable[[WorkTempStatus], None] | None = None,
    ) -> BaseAgentResponse:
        """ Agent start to work for question given current session and history session context

        Args:
            question: user question
            current_session_ctx: current session context which will be added before question
            history_session_ctx: history session context generally it keeps five
            update_process_callback: callback to update agent work's state
        """

        terminate = False
        tries = 0
        base_agent_response = BaseAgentResponse(response="", sop=None)

        system_message: ChatCompletionSystemMessageParam = {"role": "system", "content": self.system_prompt}
        user_message: ChatCompletionUserMessageParam = {"role": "user", "content": question}
        current_turn_ctx: List[ChatCompletionMessageParam] = self._init_current_turn_ctx(
            system_message=system_message,
            user_message=user_message,
            current_session_ctx=current_session_ctx,
            history_session_ctx=history_session_ctx,
        )

        self._process_callback(
            update_process_callback, 
            work_temp_status=WorkTempStatus(process="START", agent_content=None, current_use_tool=None, current_use_tool_args=None)
        )

        while not terminate and (True if self.max_attempts is None else tries <= self.max_attempts):
            try:
                step_response: BaseAgentStepResult = self.step(current_turn_ctx)
            except RateLimitError as rle:
                logger.warning(f"Agent `{self.name}` requests {self.llm_config.model} to limit. Wait one minute")
                await asyncio.sleep(60)
                continue
            
            tries += 1
        
            assistant_msg = step_response.message_param
            current_turn_ctx.append(assistant_msg)

            if step_response.finish_reason == "stop":
                terminate = True
                self._process_callback(
                    update_process_callback, 
                    work_temp_status=WorkTempStatus(
                        process="COMPLETED", 
                        agent_content=step_response.completion_content,
                        current_use_tool=None,
                        current_use_tool_args=None,
                    )
                )
                try:
                    sop = self.SOP(work_history=current_turn_ctx)
                    base_agent_response.sop = sop
                except NotImplementedError as nie:
                    logger.warning(Warning, f"Agent `{self.name}` doesn't do SOP: {str(nie)}")
                    pass
                base_agent_response.response = step_response.completion_content

            else:
                if step_response.finish_reason == "tool_calls" and step_response.tool_calls is not None:
                    tool_names = [tc.function.name for tc in step_response.tool_calls]
                    tool_args = [tc.function.arguments for tc in step_response.tool_calls]
                    self._process_callback(
                        update_process_callback,
                        work_temp_status=WorkTempStatus(
                            process="PROCESS",
                            agent_content=step_response.completion_content,
                            current_use_tool=tool_names,
                            current_use_tool_args=tool_args,
                        )
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
                            logger.error(
                                f"Agent `{self.name}` fail to call tool `{tc_name}` "
                                f"because arguments generated from him/her is not a json str"
                            )

                        except ToolNotFoundError as tfe:
                            logger.error(str(tfe))

                    assert len(tc_ids) == len(coroutines), "The length of tool call ids is not the same as the length of tools to execute."
                    coroutines_results = await asyncio.gather(*coroutines, return_exceptions=True)
                    tool_messages: List[ChatCompletionToolMessageParam] = [
                        {"role": "tool", "tool_call_id": tc_id, "content": str(result)}
                        for tc_id, result in zip(tc_ids, coroutines_results)
                    ]
                    current_turn_ctx.extend(tool_messages)

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
            try:
                sop = self.SOP(work_history=current_turn_ctx)
                base_agent_response.sop = sop
            except NotImplementedError:
                pass
            base_agent_response.response = agent_content

        return base_agent_response
    

    def _init_current_turn_ctx(
        self,
        system_message: ChatCompletionSystemMessageParam,
        user_message: ChatCompletionUserMessageParam,
        current_session_ctx: List[ChatCompletionUserMessageParam | ChatCompletionAssistantMessageParam | ChatCompletionToolMessageParam],
        history_session_ctx: List[ChatCompletionUserMessageParam | ChatCompletionAssistantMessageParam | ChatCompletionToolMessageParam],
    ) -> List[ChatCompletionMessageParam]:
        """Initialize the current turn context
        The turn context follows system + history + current_session + question in this turn.
        """

        context = [system_message]
        context.extend(history_session_ctx)
        context.extend(current_session_ctx)
        context.append(user_message)
        return context
    
    
    def _process_callback(
        self,
        callback: Callable[[WorkTempStatus], None] | None,
        work_temp_status: WorkTempStatus,
    ):
        if callback:
            callback(work_temp_status)
        

    def step(self, question: str, **kwargs) -> BaseAgentStepResult:
        
        raise NotImplementedError(f"Agent `{self.name}` doesn't implement step function.")


    def SOP(self, work_history: List[ChatCompletionMessageParam]) -> str:
        
        raise NotImplementedError(f"Agent `{self.name}` doesn't implement sop function.")
    
    def last_report_current_process(self, current_turn_ctx: List[ChatCompletionMessageParam]) -> str:

        raise NotImplementedError(f"Agent `{self.name}` doesn't implement last_report_current_process function.")

    
    @track(tags=["compact"], step_type=StepType.LLM)
    def compact(self, current_turn_ctx: List[ChatCompletionMessageParam]) -> List[ChatCompletionMessageParam]:
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
        return self._compact_in_the_same_session(
            ctx=current_turn_ctx,
            last_user_index=last_user_index,
            last_assistant_index=last_assistant_index,
        )
    
    def _compact_in_the_same_session(
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
            self.openai_client = OpenAI(base_url=self.base_url, api_key=self.api_key)

        completion: ChatCompletion = self.openai_client.chat.completions.create(**kwargs)
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
