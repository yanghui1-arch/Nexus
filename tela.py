"""Entry point for Nexus — runs Tela against a given task.

Usage:
    python main.py "Your task description here"
    uv run python main.py "Your task description here"

Required environment variables:
    NEXUS_API_KEY        OpenAI-compatible API key
    NEXUS_GITHUB_REPO    GitHub repo in owner/repo format (e.g. acme/nexus)

Optional environment variables:
    NEXUS_BASE_URL       API base URL (default: https://api.openai.com/v1)
    NEXUS_MODEL          Model name (default: gpt-4o)
    NEXUS_MAX_CONTEXT    Context window size in tokens (default: 128000)
    NEXUS_MAX_ATTEMPTS   Max tool-call iterations (default: 30)
    NEXUS_GITHUB_TOKEN   GitHub personal access token (for private repos and creating PRs)
"""

import asyncio
import os
import sys

from dotenv import load_dotenv

from src.agents.tela.agent import Tela
from src.agents.base.agent import WorkTempStatus
from src.logger import logger

load_dotenv()

def _on_progress(status: WorkTempStatus) -> None:
    process = status["process"]
    content = status.get("agent_content")
    tools = status.get("current_use_tool")
    tools_args = status.get("current_use_tool_args")

    if process == "START":
        logger.info("[Tela] Starting task...")
    elif process == "PROCESS":
        if tools:
            logger.info(f"[Tela] Tools: {', '.join(tools)}")
            logger.info(f"[Tela] Tool args: {', '.join(tools_args)}")
        if content:
            logger.debug(f"[Tela] {content}")
    elif process == "COMPLETED":
        logger.info("[Tela] Task completed.")
    elif process == "EXCEED_ATTEMPTS":
        logger.warning("[Tela] Max attempts reached.")


async def run(task: str) -> None:
    base_url = os.environ.get("NEXUS_BASE_URL", "https://api.openai.com/v1")
    api_key = os.environ.get("NEXUS_API_KEY")
    model = os.environ.get("NEXUS_MODEL", "gpt-4o")
    max_context = int(os.environ.get("NEXUS_MAX_CONTEXT", "128000"))
    max_attempts = int(os.environ.get("NEXUS_MAX_ATTEMPTS", "256"))
    github_repo = os.environ.get("NEXUS_GITHUB_REPO")
    github_token = os.environ.get("NEXUS_GITHUB_TOKEN")

    if not api_key:
        logger.error("NEXUS_API_KEY is required.")
        sys.exit(1)

    if not github_repo:
        logger.error("NEXUS_GITHUB_REPO is required (format: owner/repo).")
        sys.exit(1)

    tela = Tela.create(
        base_url=base_url,
        api_key=api_key,
        model=model,
        max_context=max_context,
        max_attempts=max_attempts,
        github_repo=github_repo,
        github_token=github_token,
    )

    async with tela:
        result = await tela.work(
            question=task,
            current_session_ctx=[],
            history_session_ctx=[],
            update_process_callback=_on_progress,
        )

    logger.info(f"Result:\n{result.response}")
    if result.sop:
        logger.info(f"SOP:\n{result.sop}")


def main() -> None:
    if len(sys.argv) < 2:
        logger.error("Usage: python main.py <task>")
        sys.exit(1)

    task = " ".join(sys.argv[1:])
    asyncio.run(run(task))


if __name__ == "__main__":
    main()
