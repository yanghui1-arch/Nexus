from typing import List, Any

import httpx
from pydantic import PrivateAttr, ConfigDict
from openai.types.chat.chat_completion import ChatCompletion
from openai.types.chat.chat_completion_message_param import (
    ChatCompletionMessageParam,
    ChatCompletionAssistantMessageParam,
)
from mwin import track, StepType

from src.agents.base.agent import Agent, BaseAgentStepResult, ModelConfig
from src.agents.tela.system_prompt import TELA_SYSTEM_PROMPT
from src.sandbox import Sandbox, SandboxConfig, PYTHON_312, SandboxPoolManager, get_sandbox_pool_manager
from src.tools.sandbox import SandboxToolKit, SANDBOX_TOOL_DEFINITIONS
from src.tools.code import (
    GITHUB_TOOL_DEFINITIONS,
    GithubToolKit,
)
from src.mcps import web_fetch, WEB_FETCH
from src.tools.web_search import web_search, TOOL_DEFINITION as WEB_SEARCH


_ALL_TOOL_DEFINITIONS = [
    *SANDBOX_TOOL_DEFINITIONS,
    *GITHUB_TOOL_DEFINITIONS,
    WEB_FETCH,
    WEB_SEARCH,
]


class Tela(Agent):
    """Tela — a Python coding agent with a sandboxed Docker workspace.
    Always be a contributor to write python.

    Must be used as an async context manager so the sandbox container
    is started and stopped cleanly:

        async with Tela(...) as tela:
            result = await tela.work(question=..., ...)
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    TELA_GITHUB_NICKNAME: str = "Nexus-Tela"
    github_token: str | None = None
    github_repo: str | None = None   # owner/repo, e.g. "acme/nexus"
    sandbox_config: SandboxConfig = PYTHON_312

    _sandbox: Sandbox | None = PrivateAttr(default=None)
    _sandbox_tools: SandboxToolKit | None = PrivateAttr(default=None)
    _sandbox_pool_manager: SandboxPoolManager | None = PrivateAttr(default=None)

    async def __aenter__(self) -> "Tela":
        repo_url = f"https://github.com/{self.github_repo}" if self.github_repo else None
        self._sandbox_pool_manager = get_sandbox_pool_manager()
        self._sandbox = await self._sandbox_pool_manager.acquire(
            config=self.sandbox_config,
            repo_url=repo_url,
        )
        self._sandbox_tools = SandboxToolKit(self._sandbox)
        github_kit = GithubToolKit(self._sandbox)

        kits = self._sandbox_tools.as_tool_kits()
        kits["FetchFromGithub"] = github_kit.fetch_from_github
        kits["CreateGithubIssue"] = github_kit.create_github_issue
        kits["PrToGithub"] = github_kit.pr_to_github
        
        # Add GitHub review and comment interaction tools
        kits["GetIssueComments"] = github_kit.get_issue_comments
        kits["ReplyToIssue"] = github_kit.reply_to_issue
        kits["GetPRReviews"] = github_kit.get_pr_reviews
        kits["GetPRReviewComments"] = github_kit.get_pr_review_comments
        kits["ReplyToPRReviewComment"] = github_kit.reply_to_pr_review_comment
        kits["GetPRComments"] = github_kit.get_pr_comments
        kits["ReplyToPR"] = github_kit.reply_to_pr
        kits["GetMyOpenPRs"] = github_kit.get_my_open_prs
        kits["GetMyIssues"] = github_kit.get_my_issues
        kits["GetNotifications"] = github_kit.get_notifications
        
        kits["WebFetch"] = web_fetch
        kits["WebSearch"] = web_search
        self.tool_kits = kits

        if self.github_repo or self.github_token:
            repo_lines = ["\n## Your Repository"]
            if self.github_token:
                repo_lines.append(f"- Token: {self.github_token}  (use for git auth and all GitHub API calls)")
            if self.github_repo:
                upstream_url = f"https://github.com/{self.github_repo}"
                repo_lines.append(f"- Upstream repo: {self.github_repo}  (create issues and open PRs here)")
                repo_lines.append(f"- Upstream URL: {upstream_url}")
                if self.github_token:
                    fork_repo = await self._ensure_fork(self.github_token, self.github_repo)
                    fork_clone_url = f"https://x-access-token:{self.github_token}@github.com/{fork_repo}"
                    repo_lines.append(f"- Your fork: {fork_repo}  (clone this as `origin`, push here frequently)")
                    repo_lines.append(f"- Fork clone URL: {fork_clone_url}")
            self.system_prompt = self.system_prompt + "\n".join(repo_lines) + "\n"

        return self

    async def _ensure_fork(self, token: str, upstream_repo: str) -> str:
        """Check if Tela's fork exists; create it if not. Returns the fork name."""
        from src.logger import logger
        repo_name = upstream_repo.split("/")[-1]
        fork_repo = f"{self.TELA_GITHUB_NICKNAME}/{repo_name}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2026-03-10",
        }
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://api.github.com/repos/{fork_repo}/folks",
                headers=headers,
            )
            if response.status_code == 400:
                logger.info(f"Fork {fork_repo} not found — creating from {upstream_repo}")
                create_folk = await client.post(
                    f"https://api.github.com/repos/{upstream_repo}/forks",
                    headers=headers,
                )
                if create_folk.status_code != 202:
                    logger.error(f"Failed to create folk {fork_repo}")
                else:
                    logger.info(f"Fork {fork_repo} created.")
            else:
                logger.info(f"Fork {fork_repo} already exists.")
        return fork_repo

    async def __aexit__(self, *args) -> None:
        if self._sandbox:
            if self._sandbox_pool_manager:
                await self._sandbox_pool_manager.release(self._sandbox)
            else:
                await self._sandbox.__aexit__(*args)
            self._sandbox = None
            self._sandbox_tools = None
            self._sandbox_pool_manager = None


    @track(tags=["exec", "tela"], step_type=StepType.LLM)
    def step(self, current_turn_ctx: List[ChatCompletionMessageParam]) -> BaseAgentStepResult:
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

        completion: ChatCompletion = self.openai_client.chat.completions.create(**kwargs)
        choice = completion.choices[0]
        message = choice.message
        reasoning = None
        if hasattr(message, "reasoning_content"):
            reasoning = getattr(message, "reasoning_content")
            

        return BaseAgentStepResult(
            finish_reason=choice.finish_reason,
            reasoning=reasoning,
            completion_content=message.content,
            tool_calls=message.tool_calls or None,
            message_param=message,
            current_step_consume_tokens=completion.usage.total_tokens if completion.usage else 0,
        )


    # def SOP(self, work_history: List[ChatCompletionMessageParam]) -> str:
        
    #     pass

    def last_report_current_process(self, current_turn_ctx: List[ChatCompletionMessageParam]) -> str:
        for msg in reversed(current_turn_ctx):
            if isinstance(msg, dict) and msg.get("role") == "assistant":
                content = msg.get("content")
                if content:
                    return content
        return "Tela reached the maximum number of attempts without completing the task."


    @track(tags=["compact", "tela"], step_type=StepType.LLM)
    def compact(self, current_turn_ctx: List[ChatCompletionMessageParam]) -> List[ChatCompletionMessageParam]:
        """Keep system message + first user message + last 10 messages."""
        if len(current_turn_ctx) <= 12:
            return current_turn_ctx
        system_msg = current_turn_ctx[0]
        first_user = next(
            (m for m in current_turn_ctx[1:] if isinstance(m, dict) and m.get("role") == "user"),
            None,
        )
        recent = current_turn_ctx[-10:]
        result: List[ChatCompletionMessageParam] = [system_msg]
        if first_user and first_user not in recent:
            result.append(first_user)
        result.extend(recent)
        return result


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
        )

