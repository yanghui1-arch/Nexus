from typing import List, ClassVar

from pydantic import PrivateAttr, ConfigDict
from openai.types.chat.chat_completion import ChatCompletion
from openai.types.chat.chat_completion_message_param import ChatCompletionMessageParam
from mwin import track, LLMProvider

from src.agents.base.agent import BaseAgentStepResult, ModelConfig
from src.agents.base.code_agent import CodeAgent
from src.agents.tela.system_prompt import TELA_SYSTEM_PROMPT
from src.sandbox import (
    Sandbox,
    SandboxConfig,
    PYTHON_312,
    SandboxPoolManager,
    get_sandbox_pool_manager,
)
from src.tools.sandbox import SandboxToolKit, SANDBOX_TOOL_DEFINITIONS
from src.tools.code import GITHUB_TOOLS_SCHEMA, GithubTools
from src.tools.nexus import (
    NEXUS_WORK_ITEM_TOOL_DEFINITIONS,
    NexusReviewTools,
    NexusTaskContext,
)
from src.mcps import web_fetch, WEB_FETCH
from src.tools.web_search import web_search, TOOL_DEFINITION as WEB_SEARCH


_ALL_TOOL_DEFINITIONS = [
    *SANDBOX_TOOL_DEFINITIONS,
    *GITHUB_TOOLS_SCHEMA,
    *NEXUS_WORK_ITEM_TOOL_DEFINITIONS,
    WEB_FETCH,
    WEB_SEARCH,
]


class Tela(CodeAgent):
    """Tela — a Python coding agent with a sandboxed Docker workspace.
    Always be a contributor to write python.

    Must be used as an async context manager so the sandbox container
    is started and stopped cleanly:

        async with Tela(...) as tela:
            result = await tela.work(question=..., ...)
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    GITHUB_NICKNAME: ClassVar[str] = "Nexus-Tela"
    sandbox_config: SandboxConfig = PYTHON_312
    sandbox_workspace_key: str | None = None

    _sandbox: Sandbox | None = PrivateAttr(default=None)
    _sandbox_pool_manager: SandboxPoolManager | None = PrivateAttr(default=None)
    _nexus_task_context: NexusTaskContext | None = PrivateAttr(default=None)

    def set_nexus_task_context(self, context: NexusTaskContext | None) -> None:
        self._nexus_task_context = context

    async def __aenter__(self) -> "Tela":
        repo_url = f"https://github.com/{self.github_repo}" if self.github_repo else None
        self._sandbox_pool_manager = get_sandbox_pool_manager()
        sandbox_env = {"GITHUB_TOKEN": self.github_token} if self.github_token else None
        self._sandbox = await self._sandbox_pool_manager.acquire(
            config=self.sandbox_config,
            repo_url=repo_url,
            workspace_key=self.sandbox_workspace_key,
            env=sandbox_env,
        )

        sandbox_tools = SandboxToolKit(self._sandbox)
        github_kit = GithubTools(
            self._sandbox,
            self._nexus_task_context,
            token=self.github_token,
        )
        nexus_kit = NexusReviewTools(self._sandbox, self._nexus_task_context)

        kits = {}
        kits.update(sandbox_tools.all_tools)
        kits.update(github_kit.all_tools)
        kits.update(nexus_kit.all_tools)

        kits["WebFetch"] = web_fetch
        kits["web_search_agent"] = web_search
        self.tool_kits = kits

        if self.github_repo or self.github_token:
            repo_lines = ["\n## Your Repository"]
            if self.github_token:
                repo_lines.append(
                    "- GitHub token: configured for tool authentication; value intentionally omitted. "
                    "GitHub tools use it automatically. For git clone/fetch/pull/push, use normal "
                    "HTTPS GitHub URLs; the sandbox is preconfigured with non-interactive git authentication."
                )
            if self.github_repo:
                upstream_url = f"https://github.com/{self.github_repo}"
                repo_lines.append(
                    f"- Upstream repo: {self.github_repo}  (create issues and open PRs here)"
                )
                repo_lines.append(f"- Upstream URL: {upstream_url}")
                if self.github_token:
                    fork_repo = await self._ensure_fork(self.github_token, self.github_repo)
                    fork_clone_url = f"https://github.com/{fork_repo}"
                    repo_lines.append(
                        f"- Your fork: {fork_repo}  (clone this as `origin`, push here frequently)"
                    )
                    repo_lines.append(f"- Fork clone URL: {fork_clone_url}")
            self.system_prompt = self.system_prompt + "\n".join(repo_lines) + "\n"

        return self

    async def _ensure_fork(self, token: str, upstream_repo: str) -> str:
        """Check if Tela's fork exists; create it if not. Returns the fork name.

        Extends CodeAgent._ensure_fork with Tela-specific configuration.
        """
        return await super()._ensure_fork(token, upstream_repo)

    async def __aexit__(self, *args) -> None:
        if self._sandbox:
            if self._sandbox_pool_manager:
                await self._sandbox_pool_manager.release(self._sandbox)
            else:
                await self._sandbox.__aexit__(*args)
            self._sandbox = None
            self._sandbox_pool_manager = None
        await self.close()

    @track(tags=["exec", "tela"], step_type="llm", llm_provider=LLMProvider.OPENAI)
    async def step(self, current_turn_ctx: List[ChatCompletionMessageParam]) -> BaseAgentStepResult:
        if self._sandbox is None:
            raise RuntimeError("Tela must be used as an async context manager (async with Tela(...) as tela:)")

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

        stream_result = await self._create_chat_completion_stream(kwargs)
        message = stream_result.message
        if stream_result.finish_reason is None:
            raise ValueError("Tela stream completion missing finish_reason.")

        return BaseAgentStepResult(
            finish_reason=stream_result.finish_reason,
            reasoning=stream_result.reasoning,
            completion_content=message.content,
            tool_calls=message.tool_calls or None,
            message_param=message,
            current_step_consume_tokens=stream_result.usage_tokens,
        )

    def last_report_current_process(self, current_turn_ctx: List[ChatCompletionMessageParam]) -> str:
        for msg in reversed(current_turn_ctx):
            if isinstance(msg, dict) and msg.get("role") == "assistant":
                content = msg.get("content")
                if content:
                    return content
        return "Tela reached the maximum number of attempts without completing the task."

    @classmethod
    def create(
        cls,
        base_url: str,
        api_key: str,
        model: str,
        max_context: int,
        github_repo: str,
        max_attempts: int = 30,
        github_token: str | None = None,
        sandbox_config: SandboxConfig = PYTHON_312,
        sandbox_workspace_key: str | None = None,
    ) -> "Tela":
        """Convenience factory with sensible defaults."""
        return cls(
            name="Tela",
            tool_kits=None,
            base_url=base_url,
            api_key=api_key,
            system_prompt=TELA_SYSTEM_PROMPT,
            llm_config=ModelConfig(model=model, max_length_context=max_context),
            github_repo=github_repo,
            max_attempts=max_attempts,
            github_token=github_token,
            sandbox_config=sandbox_config,
            sandbox_workspace_key=sandbox_workspace_key,
        )
