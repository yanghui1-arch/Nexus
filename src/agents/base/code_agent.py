"""CodeAgent - Base agent for code-related tasks with GitHub fork management."""

import asyncio
from typing import Any, ClassVar

import httpx
from pydantic import ConfigDict

from src.agents.base.agent import Agent
from src.logger import logger


class CodeAgent(Agent):
    """CodeAgent — Base agent for code-related tasks.

    Provides common functionality for agents that need to interact with GitHub,
    including fork management for contributing to repositories.

    Subclasses must define:
        - GITHUB_NICKNAME: Class attribute for the GitHub username/organization

    Example:
        class MyAgent(CodeAgent):
            GITHUB_NICKNAME: ClassVar[str] = "MyGitHubNick"

            async def _ensure_fork(self, token: str, upstream_repo: str) -> str:
                # Custom implementation or use parent's
                return await super()._ensure_fork(token, upstream_repo)
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    GITHUB_NICKNAME: ClassVar[str] = ""
    FORK_READY_TIMEOUT_SECONDS: ClassVar[float] = 30.0
    FORK_READY_POLL_INTERVAL_SECONDS: ClassVar[float] = 1.0
    github_token: str | None = None
    github_repo: str | None = None  # owner/repo, e.g. "acme/nexus"

    @staticmethod
    def _github_headers(token: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        }

    def _fork_is_ready(
        self,
        payload: dict[str, Any],
        *,
        fork_repo: str,
        upstream_repo: str,
    ) -> bool:
        is_fork = payload.get("fork")
        parent_full_name = (payload.get("parent") or {}).get("full_name")

        if is_fork is False:
            raise RuntimeError(f"Repository {fork_repo} exists but is not a fork.")

        if parent_full_name and parent_full_name != upstream_repo:
            raise RuntimeError(
                f"Repository {fork_repo} forks {parent_full_name}, expected {upstream_repo}."
            )

        return is_fork is True and parent_full_name == upstream_repo

    async def _wait_for_fork_ready(
        self,
        client: httpx.AsyncClient,
        *,
        token: str,
        fork_repo: str,
        upstream_repo: str,
    ) -> None:
        headers = self._github_headers(token)
        deadline = asyncio.get_running_loop().time() + self.FORK_READY_TIMEOUT_SECONDS
        last_status_code: int | None = None

        while True:
            response = await client.get(
                f"https://api.github.com/repos/{fork_repo}",
                headers=headers,
            )
            last_status_code = response.status_code

            if response.status_code == 200:
                payload = response.json()
                if self._fork_is_ready(
                    payload,
                    fork_repo=fork_repo,
                    upstream_repo=upstream_repo,
                ):
                    return
            elif response.status_code != 404:
                raise RuntimeError(
                    f"Failed to verify fork {fork_repo}: GitHub returned {response.status_code}."
                )

            if asyncio.get_running_loop().time() >= deadline:
                raise TimeoutError(
                    f"Fork {fork_repo} was requested but never became ready "
                    f"(last status: {last_status_code})."
                )

            await asyncio.sleep(self.FORK_READY_POLL_INTERVAL_SECONDS)

    async def _ensure_fork(self, token: str, upstream_repo: str) -> str:
        """Check if the agent's fork exists; create it if not. Returns the fork name.

        Args:
            token: GitHub personal access token
            upstream_repo: Upstream repository in owner/repo format

        Returns:
            The fork repository name in owner/repo format

        Raises:
            ValueError: If GITHUB_NICKNAME is not set
        """
        if not self.GITHUB_NICKNAME:
            raise ValueError(
                f"Agent `{self.name}` must define GITHUB_NICKNAME class attribute"
            )

        repo_name = upstream_repo.split("/")[-1]
        fork_repo = f"{self.GITHUB_NICKNAME}/{repo_name}"

        headers = self._github_headers(token)

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://api.github.com/repos/{fork_repo}",
                headers=headers,
            )

            if response.status_code == 404:
                logger.info(f"Fork {fork_repo} not found — creating from {upstream_repo}")
                create_response = await client.post(
                    f"https://api.github.com/repos/{upstream_repo}/forks",
                    headers=headers,
                )
                if create_response.status_code not in {201, 202}:
                    raise RuntimeError(
                        f"Failed to create fork {fork_repo}: {create_response.text}"
                    )
                logger.info(f"Fork {fork_repo} creation accepted by GitHub.")
            elif response.status_code == 200:
                logger.info(f"Fork {fork_repo} already exists.")
                if self._fork_is_ready(
                    response.json(),
                    fork_repo=fork_repo,
                    upstream_repo=upstream_repo,
                ):
                    return fork_repo
            else:
                raise RuntimeError(
                    f"Failed to query fork {fork_repo}: GitHub returned {response.status_code}."
                )

            await self._wait_for_fork_ready(
                client,
                token=token,
                fork_repo=fork_repo,
                upstream_repo=upstream_repo,
            )

        return fork_repo

