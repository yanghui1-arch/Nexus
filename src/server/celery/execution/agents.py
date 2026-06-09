from __future__ import annotations

from src.agents import Jules, Marc, Sophie, Tela
from src.agents.base.agent import Agent
from src.server.config import Settings
from src.server.postgres.models import TaskRecord


AGENT_BUILDERS: dict[str, Agent] = {
    "tela": Tela,
    "sophie": Sophie,
    "jules": Jules,
    "marc": Marc,
}
CODING_AGENTS = {"tela", "sophie", "jules"}


def build_agent(
    *,
    task: TaskRecord,
    settings: Settings,
    workspace_key: str,
    github_repo: str | None,
) -> Agent:
    """Create the configured agent for a task.

    Args:
        task: Task record that selects the agent and carries repo/project
            context.
        settings: Server settings containing model, API, and GitHub token
            configuration.
        workspace_key: Sandbox workspace key assigned to the agent instance.
        github_repo: Repository resolved from the active workspace.

    Returns:
        Agent instance ready to execute the task.

    Raises:
        RuntimeError: If required API credentials, repo/project context, agent
            name, or coding-agent GitHub token are missing.
    """
    api_key = settings.api_key
    if not api_key:
        raise RuntimeError("NEXUS_API_KEY is required.")

    agent_name = task.agent.value
    resolved_repo = task.repo or github_repo
    resolved_project = task.project
    if not resolved_repo or not resolved_project:
        raise RuntimeError("Missing repo/project context.")

    shared = {
        "base_url": settings.base_url,
        "api_key": api_key,
        "model": settings.model,
        "max_context": settings.max_context,
        "max_attempts": settings.max_attempts,
    }

    agent_builder = AGENT_BUILDERS.get(agent_name)
    if not agent_builder:
        raise RuntimeError(
            f"Task {task.id} failed to create agent `{agent_name}` due to invalid agent name."
            f" Detailed task repo({task.repo})"
        )

    github_token = settings.github_tokens.get(agent_name)
    if agent_name in CODING_AGENTS:
        if not github_token:
            raise RuntimeError(f"Task {task.id} failed to create coding agent `{agent_name}` without github token.")
        return agent_builder.create(
            **shared,
            github_repo=resolved_repo,
            sandbox_workspace_key=workspace_key,
            github_token=github_token,
        )

    return agent_builder.create(
        **shared,
        github_repo=resolved_repo,
        github_token=github_token,
    )
