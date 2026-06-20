from __future__ import annotations

import json
from typing import List

from mwin import LLMProvider, track
from openai.types.chat.chat_completion_message_param import ChatCompletionMessageParam
from pydantic import ConfigDict, Field, PrivateAttr

from src.agents.assistant.system_prompt import ASSISTANT_SYSTEM_PROMPT
from src.agents.base.agent import Agent, BaseAgentStepResult, ModelConfig
from src.sandbox import PYTHON_312, Sandbox, SandboxConfig, SandboxPoolManager, get_sandbox_pool_manager
from src.tools.code import GITHUB_ADMIN_TOOLS_SCHEMA
from src.tools.code.github.client import GithubTools
from src.tools.code.github.notification import GET_NOTIFICATIONS
from src.tools.code.github.pr import (
    CREATE_PR_REVIEW,
    GET_PR_CHECK_SUMMARY,
    GET_PR_COMMENTS,
    GET_PR_FILES,
    GET_PR_REVIEW_COMMENTS,
    GET_PR_REVIEWS,
    GET_PULL_REQUEST,
    LIST_OPEN_PULL_REQUESTS,
    REPLY_TO_PR,
    REPLY_TO_PR_REVIEW_COMMENT,
)
from src.tools.nexus import NexusTaskContext
from src.tools.sandbox import LIST_FILES, READ_FILE, RUN_SHELL, SandboxToolKit
from src.tools.skills import READ_SKILL, project_path_for_repo


ASSISTANT_GITHUB_TOOLS = [
    LIST_OPEN_PULL_REQUESTS,
    GET_PULL_REQUEST,
    GET_PR_FILES,
    GET_PR_CHECK_SUMMARY,
    GET_PR_REVIEWS,
    GET_PR_REVIEW_COMMENTS,
    GET_PR_COMMENTS,
    REPLY_TO_PR,
    REPLY_TO_PR_REVIEW_COMMENT,
    CREATE_PR_REVIEW,
    *GITHUB_ADMIN_TOOLS_SCHEMA,
    GET_NOTIFICATIONS,
]


class Assistant(Agent):
    """Assistant - Nexus PR review agent."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    github_repo: str | None = None
    repo_url: str | None = None
    github_token: str | None = None
    review_test_commands: dict[str, list[str]] = Field(default_factory=dict)
    sandbox_config: SandboxConfig = PYTHON_312
    sandbox_workspace_key: str | None = None
    tool_definitions: List[dict] = Field(default_factory=lambda: [
        RUN_SHELL,
        READ_FILE,
        LIST_FILES,
        *ASSISTANT_GITHUB_TOOLS,
    ])

    _sandbox: Sandbox | None = PrivateAttr(default=None)
    _sandbox_pool_manager: SandboxPoolManager | None = PrivateAttr(default=None)
    _nexus_task_context: NexusTaskContext | None = PrivateAttr(default=None)

    def set_nexus_task_context(self, context: NexusTaskContext | None) -> None:
        """Attach Nexus task context for tool calls."""
        self._nexus_task_context = context

    async def __aenter__(self) -> "Assistant":
        repo_url = self.repo_url or (f"https://github.com/{self.github_repo}" if self.github_repo else None)
        self._sandbox_pool_manager = get_sandbox_pool_manager()
        self._sandbox = await self._sandbox_pool_manager.acquire(
            config=self.sandbox_config,
            repo_url=repo_url,
            workspace_key=self.sandbox_workspace_key,
        )
        await self.prepare_project_checkout(self._sandbox)

        sandbox_tools = SandboxToolKit(self._sandbox)
        github_tools = GithubTools(self._sandbox, self._nexus_task_context)

        self.tool_kits = {
            "RunCommand": sandbox_tools.all_tools["RunCommand"],
            "ReadFile": sandbox_tools.all_tools["ReadFile"],
            "ListFiles": sandbox_tools.all_tools["ListFiles"],
            "list_open_pull_requests": github_tools.list_open_pull_requests,
            "get_pull_request": github_tools.get_pull_request,
            "get_pr_files": github_tools.get_pr_files,
            "get_pr_check_summary": github_tools.get_pr_check_summary,
            "get_pr_reviews": github_tools.get_pr_reviews,
            "get_pr_review_comments": github_tools.get_pr_review_comments,
            "get_pr_comments": github_tools.get_pr_comments,
            "reply_to_pr": github_tools.reply_to_pr,
            "reply_to_pr_review_comment": github_tools.reply_to_pr_review_comment,
            "create_pr_review": github_tools.create_pr_review,
            **github_tools.admin_tools,
            **github_tools.notifications,
        }

        repo_lines = ["\n## Runtime Context"]
        if self.github_repo:
            repo_lines.append(f"- GitHub repo: {self.github_repo}")
            repo_lines.append(f"- Local path: /workspace/{self.github_repo.rsplit('/', 1)[-1]}")
        if self.github_token:
            repo_lines.append(f"- GitHub token: {self.github_token}")
        repo_lines.append(f"- Merge method: squash unless the task says otherwise")
        repo_lines.append(
            "- Configured test commands: "
            + json.dumps(self.review_test_commands, ensure_ascii=True)
        )
        self.system_prompt = self.system_prompt + "\n".join(repo_lines) + "\n"

        installed_skills = await self.configure_skills(self._sandbox, self.github_repo)
        if installed_skills and READ_SKILL not in self.tool_definitions:
            self.tool_definitions.append(READ_SKILL)
        return self

    async def prepare_project_checkout(self, sandbox: Sandbox) -> None:
        """Clone or pull the assigned repository before review starts."""
        if not self.github_repo:
            return

        repo_url = self.repo_url or f"https://github.com/{self.github_repo}"
        if self.github_token and repo_url == f"https://github.com/{self.github_repo}":
            repo_url = f"https://x-access-token:{self.github_token}@github.com/{self.github_repo}"

        result = await GithubTools(sandbox).fetch_from_github(
            repo_url=repo_url,
            local_path=project_path_for_repo(self.github_repo),
        )
        if not result.get("success", False):
            raise RuntimeError(
                f"Failed to prepare repository {self.github_repo}: {result.get('message', 'git fetch failed')}"
            )

    async def __aexit__(self, *args) -> None:
        if self._sandbox is not None:
            if self._sandbox_pool_manager is not None:
                await self._sandbox_pool_manager.release(self._sandbox)
            else:
                await self._sandbox.__aexit__(*args)
            self._sandbox = None
            self._sandbox_pool_manager = None
        await self.close()

    @track(tags=["exec", "assistant"], step_type="llm", llm_provider=LLMProvider.OPENAI)
    async def step(self, current_turn_ctx: List[ChatCompletionMessageParam]) -> BaseAgentStepResult:
        if self._sandbox is None:
            raise RuntimeError("Assistant must be used as an async context manager.")

        kwargs: dict = {
            "model": self.llm_config.model,
            "messages": current_turn_ctx,
            "tools": self.tool_definitions,
        }
        if self.sample_config:
            if self.sample_config.top_p is not None:
                kwargs["top_p"] = self.sample_config.top_p
            if self.sample_config.extra_body:
                kwargs["extra_body"] = self.sample_config.extra_body

        stream_result = await self._create_chat_completion_stream(kwargs)
        message = stream_result.message
        if stream_result.finish_reason is None:
            raise ValueError("Assistant stream completion missing finish_reason.")

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
        return "Assistant reached the maximum number of attempts without completing the review."

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
        review_test_commands: dict[str, list[str]] | None = None,
        sandbox_config: SandboxConfig = PYTHON_312,
        sandbox_workspace_key: str | None = None,
        **_: object,
    ) -> "Assistant":
        """Convenience factory with runtime settings."""
        return cls(
            name="Assistant",
            tool_kits=None,
            base_url=base_url,
            api_key=api_key,
            system_prompt=ASSISTANT_SYSTEM_PROMPT,
            llm_config=ModelConfig(model=model, max_length_context=max_context),
            max_attempts=max_attempts,
            github_repo=github_repo,
            repo_url=repo_url,
            github_token=github_token,
            review_test_commands=review_test_commands or {},
            sandbox_config=sandbox_config,
            sandbox_workspace_key=sandbox_workspace_key,
        )
