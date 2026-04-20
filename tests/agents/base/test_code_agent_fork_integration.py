import os
import shutil
import subprocess
from unittest.mock import patch

import httpx
import pytest

from src.agents.base.agent import BaseAgentStepResult, ModelConfig
from src.agents.base.code_agent import CodeAgent


class LiveCodeAgent(CodeAgent):
    def step(self, current_turn_ctx: list) -> BaseAgentStepResult:
        raise NotImplementedError("unused in these tests")

    def last_report_current_process(self, current_turn_ctx: list) -> str:
        return "unused"


def make_agent(nickname: str) -> LiveCodeAgent:
    LiveCodeAgent.GITHUB_NICKNAME = nickname
    with patch("src.agents.base.agent.AsyncOpenAI"):
        return LiveCodeAgent(
            name="live-code-agent",
            tool_kits=None,
            base_url="http://localhost",
            api_key="test-key",
            system_prompt="test",
            llm_config=ModelConfig(model="gpt-4o", max_length_context=128_000),
            max_attempts=10,
        )


@pytest.mark.integration
async def test_ensure_fork_makes_real_fork_reachable_over_git():
    token = os.getenv("NEXUS_GITHUB_FORK_TEST_TOKEN")
    upstream_repo = os.getenv("NEXUS_GITHUB_FORK_TEST_UPSTREAM_REPO")
    nickname = os.getenv("NEXUS_GITHUB_FORK_TEST_NICKNAME")

    if not token or not upstream_repo or not nickname:
        pytest.skip(
            "Set NEXUS_GITHUB_FORK_TEST_TOKEN, NEXUS_GITHUB_FORK_TEST_UPSTREAM_REPO, and "
            "NEXUS_GITHUB_FORK_TEST_NICKNAME to run this live GitHub fork smoke test."
        )

    if shutil.which("git") is None:
        pytest.skip("git is required for the live GitHub fork smoke test")

    agent = make_agent(nickname)
    fork_repo = await agent._ensure_fork(token=token, upstream_repo=upstream_repo)
    repo_name = upstream_repo.split("/")[-1]

    assert fork_repo == f"{nickname}/{repo_name}"

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api.github.com/repos/{fork_repo}",
            headers=agent._github_headers(token),
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["fork"] is True
    assert payload["parent"]["full_name"] == upstream_repo

    remote_url = f"https://x-access-token:{token}@github.com/{fork_repo}.git"
    result = subprocess.run(
        ["git", "ls-remote", remote_url, "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip()
