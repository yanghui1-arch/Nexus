from __future__ import annotations

from typing import List

from mwin import LLMProvider, track
from openai.types.chat.chat_completion import ChatCompletion
from openai.types.chat.chat_completion_message_param import ChatCompletionMessageParam
from pydantic import ConfigDict, PrivateAttr

from src.agents.base.agent import Agent, BaseAgentStepResult, ModelConfig
from src.agents.marc.system_prompt import MARC_SYSTEM_PROMPT
from src.sandbox import PYTHON_312, Sandbox, SandboxConfig, SandboxPoolManager, get_sandbox_pool_manager
from src.tools.code.github.readonly import GITHUB_READONLY_TOOL_DEFINITIONS, GithubReadOnlyTools
from src.tools.nexus import NexusTaskContext
from src.tools.product import PRODUCT_TOOL_DEFINITIONS, ProductTools
from src.tools.sandbox import RUN_SHELL, SandboxToolKit
from src.tools.web_search import web_search, TOOL_DEFINITION as WEB_SEARCH


_ALL_TOOL_DEFINITIONS = [
    RUN_SHELL,
    WEB_SEARCH,
    *GITHUB_READONLY_TOOL_DEFINITIONS,
    *PRODUCT_TOOL_DEFINITIONS,
]


class Marc(Agent):
    """Marc — Nexus product manager agent."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    github_repo: str | None = None
    repo_url: str | None = None
    github_token: str | None = None
    sandbox_config: SandboxConfig = PYTHON_312
    sandbox_workspace_key: str | None = None

    _sandbox: Sandbox | None = PrivateAttr(default=None)
    _sandbox_pool_manager: SandboxPoolManager | None = PrivateAttr(default=None)
    _nexus_task_context: NexusTaskContext | None = PrivateAttr(default=None)

    def set_nexus_task_context(self, context: NexusTaskContext) -> None:
        self._nexus_task_context = context

    async def __aenter__(self) -> "Marc":
        repo_url = self.repo_url or (f"https://github.com/{self.github_repo}" if self.github_repo else None)
        self._sandbox_pool_manager = get_sandbox_pool_manager()
        self._sandbox = await self._sandbox_pool_manager.acquire(
            config=self.sandbox_config,
            repo_url=repo_url,
            workspace_key=self.sandbox_workspace_key,
        )
        sandbox_tools = SandboxToolKit(self._sandbox)
        github_readonly_tools = GithubReadOnlyTools(
            default_repo=self.github_repo,
            default_repo_url=self.repo_url,
            token=self.github_token,
        )
        self.tool_kits = {
            "RunCommand": sandbox_tools.all_tools["RunCommand"],
            "WebSearch": web_search,
            **github_readonly_tools.all_tools,
        }

        if self._nexus_task_context is not None:
            product_tools = ProductTools(
                database=self._nexus_task_context.database,
                context=self._nexus_task_context,
            )
            self.tool_kits.update(product_tools.all_tools)

        if self.github_repo or repo_url:
            repo_lines = ["\n## Your GitHub Context"]
            if self.github_repo:
                repo_lines.append(f"- GitHub repo: {self.github_repo}")
            if repo_url:
                repo_lines.append(f"- GitHub repo URL: {repo_url}")
            self.system_prompt = self.system_prompt + "\n".join(repo_lines) + "\n"
        return self

    async def __aexit__(self, *args) -> None:
        if self._sandbox is not None:
            if self._sandbox_pool_manager is not None:
                await self._sandbox_pool_manager.release(self._sandbox)
            else:
                await self._sandbox.__aexit__(*args)
            self._sandbox = None
            self._sandbox_pool_manager = None
        await self.close()

    @track(tags=["exec", "marc"], step_type="llm", llm_provider=LLMProvider.OPENAI, system_prompt="Marc/step@0.1")
    async def step(self, current_turn_ctx: List[ChatCompletionMessageParam]) -> BaseAgentStepResult:
        if self._sandbox is None:
            raise RuntimeError("Marc must be used as an async context manager (async with Marc(...) as marc:)")

        kwargs: dict = {
            "model": self.llm_config.model,
            "messages": current_turn_ctx,
            "tools": _ALL_TOOL_DEFINITIONS,
        }
        if self.sample_config:
            if self.sample_config.top_p is not None:
                kwargs["top_p"] = self.sample_config.top_p
            if self.sample_config.extra_body:
                kwargs["extra_body"] = self.sample_config.extra_body

        completion: ChatCompletion = await self.openai_client.chat.completions.create(**kwargs)
        choice = completion.choices[0]
        message = choice.message
        reasoning = getattr(message, "reasoning_content", None)

        return BaseAgentStepResult(
            finish_reason=choice.finish_reason,
            reasoning=reasoning,
            completion_content=message.content,
            tool_calls=message.tool_calls or None,
            message_param=message,
            current_step_consume_tokens=completion.usage.total_tokens if completion.usage else 0,
        )

    def last_report_current_process(self, current_turn_ctx: List[ChatCompletionMessageParam]) -> str:
        for msg in reversed(current_turn_ctx):
            if isinstance(msg, dict) and msg.get("role") == "assistant":
                content = msg.get("content")
                if content:
                    return content
        return "Marc reached the maximum number of attempts without completing product planning."

    @classmethod
    def create(
        cls,
        base_url: str,
        api_key: str,
        model: str,
        max_context: int,
        max_attempts: int = 30,
        github_repo: str | None = None,
        repo_url: str | None = None,
        github_token: str | None = None,
        sandbox_config: SandboxConfig = PYTHON_312,
        sandbox_workspace_key: str | None = None,
        **_: object,
    ) -> "Marc":
        return cls(
            name="Marc",
            tool_kits=None,
            base_url=base_url,
            api_key=api_key,
            system_prompt=MARC_SYSTEM_PROMPT,
            llm_config=ModelConfig(model=model, max_length_context=max_context),
            max_attempts=max_attempts,
            github_repo=github_repo,
            repo_url=repo_url,
            github_token=github_token,
            sandbox_config=sandbox_config,
            sandbox_workspace_key=sandbox_workspace_key,
        )
