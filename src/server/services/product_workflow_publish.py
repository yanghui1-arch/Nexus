from __future__ import annotations

import json
import uuid
from typing import Any

from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from src.logger import logger
from src.server.config import get_settings
from src.server.postgres.models import (
    AgentInstanceRecord,
    AgentName,
    FeatureItemRecord,
    ProductProposalRecord,
)
from src.server.postgres.repositories import AgentInstanceRepository, FeatureItemRepository
from src.server.runner import AgentTaskRunner, TaskSubmission


CODING_AGENT_NAMES = (AgentName.tela, AgentName.sophie, AgentName.jules)

AGENT_CAPABILITIES = {
    AgentName.tela: "Tela is best for Python, backend services, scripts, APIs, tests, and general code maintenance.",
    AgentName.sophie: "Sophie is best for React, TypeScript, frontend UI, web design, accessibility, and CSS.",
    AgentName.jules: "Jules is best for Java, Spring Boot, Maven, Gradle, backend APIs, and production Java services.",
}


class NoActiveCodingAgentInstanceError(RuntimeError):
    """Raised when no coding agent instance can run a feature item."""


async def publish_feature_item_task(
    session: AsyncSession,
    *,
    runner: AgentTaskRunner,
    item: FeatureItemRecord,
    proposal: ProductProposalRecord,
    require_unassigned: bool,
) -> tuple[FeatureItemRecord | None, uuid.UUID, uuid.UUID]:
    """Publish a coding task and attach it to a feature item.

    ``require_unassigned`` is intentionally caller-controlled: background
    publishing should only claim unassigned pending items, while retry must
    replace the failed task id already stored on the item.
    """
    available_agents = await list_available_coding_agent_instances(session, proposal=proposal)
    if not available_agents:
        raise NoActiveCodingAgentInstanceError

    selected_agent, selected_instance = await select_coding_agent_instance(
        proposal=proposal,
        item=item,
        available_agents=available_agents,
    )
    agent_instance_id = selected_instance.id
    # Bind the feature item before dispatch so worker failures can always resolve
    # the feature item by task_id and sync it to failed.
    task = await runner.create_task_record(
        TaskSubmission(
            agent_instance_id=agent_instance_id,
            agent=selected_agent,
            question=build_feature_item_coding_question(item),
            external_issue_url=None,
        ),
        session=session,
    )
    assigned = await FeatureItemRepository.assign_task(
        session, item.id, task_id=task.id, require_unassigned=require_unassigned
    )
    if assigned is None:
        logger.warning("Feature item %s was already assigned before publishing task %s.", item.id, task.id)
        return assigned, task.id, agent_instance_id
    await runner.dispatch_task(task.id)
    return assigned, task.id, agent_instance_id


async def list_available_coding_agent_instances(
    session: AsyncSession,
    *,
    proposal: ProductProposalRecord,
) -> list[tuple[AgentName, AgentInstanceRecord]]:
    """Return one least-loaded available instance per coding agent for a proposal."""
    available: list[tuple[AgentName, AgentInstanceRecord]] = []
    for agent in CODING_AGENT_NAMES:
        instances = await AgentInstanceRepository.list_by_active_task_load(
            session,
            agent=agent,
            user_id=proposal.user_id,
            github_repo=proposal.repo,
            project=proposal.project,
            limit=1,
        )
        if instances:
            available.append((agent, instances[0]))
    return available


async def select_coding_agent_instance(
    *,
    proposal: ProductProposalRecord,
    item: FeatureItemRecord,
    available_agents: list[tuple[AgentName, AgentInstanceRecord]],
) -> tuple[AgentName, AgentInstanceRecord]:
    """Select the best available coding agent for a feature item."""
    if len(available_agents) == 1:
        return available_agents[0]

    available_names = [agent for agent, _ in available_agents]
    selected_agent = await choose_coding_agent_name_with_gpt(
        proposal=proposal,
        item=item,
        available_agents=available_names,
    )
    if selected_agent in available_names:
        return next(candidate for candidate in available_agents if candidate[0] == selected_agent)

    logger.warning(
        "Coding agent selector returned %s outside available agents %s; falling back.",
        selected_agent.value if selected_agent is not None else None,
        [agent.value for agent in available_names],
    )
    return available_agents[0]


async def choose_coding_agent_name_with_gpt(
    *,
    proposal: ProductProposalRecord,
    item: FeatureItemRecord,
    available_agents: list[AgentName],
) -> AgentName | None:
    """Ask GPT to choose one available coding agent for the feature item."""
    settings = get_settings()
    if not settings.api_key:
        logger.warning("NEXUS_API_KEY is not configured; coding agent selection will fall back.")
        return None

    client = AsyncOpenAI(
        base_url=settings.base_url,
        api_key=settings.api_key,
        default_headers={
            "User-Agent": "codex-tui/0.135.0 (Ubuntu 24.4.0; x86_64) WindowsTerminal (codex-tui; 0.135.0)",
        },    
    )
    try:
        completion = await client.chat.completions.create(
            model=settings.model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You route implementation work to the best available Nexus coding agent. "
                        "Choose only from the available agent names. Return only JSON like "
                        '{"agent":"tela"}.'
                    ),
                },
                {
                    "role": "user",
                    "content": build_agent_selection_prompt(
                        proposal=proposal,
                        item=item,
                        available_agents=available_agents,
                    ),
                },
            ],
        )
    except Exception:
        logger.exception("GPT coding agent selection failed; falling back.")
        return None
    finally:
        await client.close()

    if not completion.choices:
        logger.warning("GPT coding agent selection returned no choices.")
        return None

    content = completion.choices[0].message.content or ""
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        logger.warning("GPT coding agent selection returned invalid JSON: %s", content)
        return None

    agent_name = payload.get("agent")
    if not isinstance(agent_name, str):
        return None
    try:
        return AgentName(agent_name.strip().lower())
    except ValueError:
        return None


def build_agent_selection_prompt(
    *,
    proposal: ProductProposalRecord,
    item: FeatureItemRecord,
    available_agents: list[AgentName],
) -> str:
    available_agent_lines = "\n".join(
        f"- {agent.value}: {AGENT_CAPABILITIES[agent]}" for agent in available_agents
    )
    return "\n".join(
        [
            "Available agents:",
            available_agent_lines,
            "",
            "Proposal context:",
            f"Title: {proposal.title}",
            f"Plan type: {proposal.plan_type}",
            f"Summary: {proposal.summary}",
            f"Answer: {proposal.answer}",
            "",
            "Feature item:",
            f"Title: {item.title}",
            f"Description: {item.description}",
        ]
    )


def build_feature_item_coding_question(item: Any) -> str:
    return f"Implement product feature item: {item.title}\n\n{item.description}"
