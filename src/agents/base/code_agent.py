"""CodeAgent - Base agent for code-related tasks with GitHub fork management."""

from typing import ClassVar

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
    github_token: str | None = None
    github_repo: str | None = None  # owner/repo, e.g. "acme/nexus"

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

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        }

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
                if create_response.status_code == 202:
                    logger.info(f"Fork {fork_repo} created.")
                else:
                    logger.error(f"Failed to create fork {fork_repo}: {create_response.text}")
            else:
                logger.info(f"Fork {fork_repo} already exists.")

        return fork_repo
