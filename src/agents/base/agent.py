import asyncio
import inspect
import json
from typing import Literal, Any, List, Dict, Callable, Coroutine, TypedDict, Required
from dataclasses import dataclass
from pydantic import BaseModel, ConfigDict, model_validator
from openai import OpenAI
from openai.types.chat.chat_completion_message_param import (
    ChatCompletionMessageParam, 
    ChatCompletionSystemMessageParam, 
    ChatCompletionUserMessageParam,
    ChatCompletionAssistantMessageParam,
    ChatCompletionToolMessageParam
)
from openai.types.chat.chat_completion_message_tool_call import ChatCompletionMessageToolCall
from src.logger import logger
from src.exception import ToolNotFoundError
from src.utils.asynchronous import make_async


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
    openai_client: Any = None


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
            work_temp_status=WorkTempStatus(process="START", agent_content=None, current_use_tool=None)
        )

        while not terminate and (True if self.max_attempts is None else tries <= self.max_attempts):
            tries += 1

            step_response: BaseAgentStepResult = self.step(current_turn_ctx)
            assistant_msg = step_response.message_param
            current_turn_ctx.append(assistant_msg)

            if step_response.finish_reason == "stop":
                terminate = True
                self._process_callback(
                    update_process_callback, 
                    work_temp_status=WorkTempStatus(
                        process="COMPLETED", 
                        agent_content=step_response.completion_content, current_use_tool=None
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
                    self._process_callback(
                        update_process_callback,
                        work_temp_status=WorkTempStatus(
                            process="PROCESS",
                            agent_content=step_response.completion_content,
                            current_use_tool=tool_names
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

    
    def compact(self, current_turn_ctx: List[ChatCompletionMessageParam]) -> List[ChatCompletionMessageParam]:

        raise NotImplementedError(f"Agent `{self.name}` doesn't implement compact function.")
    
    
    def last_report_current_process(self, current_turn_ctx: List[ChatCompletionMessageParam]) -> str:

        raise NotImplementedError(f"Agent `{self.name}` doesn't implement last_report_current_process function.")
    


