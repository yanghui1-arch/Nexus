from __future__ import annotations

import os
import json
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    api_key: str | None
    base_url: str
    model: str
    max_context: int
    max_attempts: int
    github_tokens: dict[str, str | None]
    database_url: str
    redis_url: str
    redis_message_ttl_seconds: int
    celery_broker_url: str
    celery_result_backend: str
    celery_queue: str
    celery_visibility_timeout_seconds: int
    celery_task_publish_max_retries: int
    celery_broker_connection_timeout_seconds: float
    github_feedback_poll_interval_seconds: int
    github_feedback_poll_task_limit: int
    github_feedback_batch_size: int
    github_feedback_http_timeout_seconds: float
    github_oauth_client_id: str | None
    github_oauth_client_secret: str | None
    github_oauth_redirect_uri: str
    auth_session_cookie_name: str
    auth_session_ttl_seconds: int
    frontend_base_url: str
    product_discovery_poll_interval_seconds: int
    product_discovery_poll_task_limit: int
    product_discovery_recent_proposal_limit: int
    product_discovery_pending_proposal_limit: int
    product_workflow_poll_interval_seconds: int
    secretary_enabled: bool
    secretary_github_token: str | None
    secretary_discord_bot_token: str | None
    secretary_discord_user_id: str | None
    secretary_poll_interval_seconds: int
    secretary_merge_method: str
    secretary_test_commands: dict[str, list[str]]


def _env_bool(name: str, default: bool = False) -> bool:
    """Read a boolean environment value."""
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_test_commands(name: str) -> dict[str, list[str]]:
    """Read repo-scoped secretary test commands from JSON."""
    raw = os.getenv(name, "{}").strip()
    if not raw:
        return {}
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError(f"{name} must be a JSON object.")

    commands: dict[str, list[str]] = {}
    for repo, value in payload.items():
        if not isinstance(repo, str) or not repo.strip():
            raise ValueError(f"{name} keys must be repository names or '*'.")
        if isinstance(value, str):
            normalized = [value]
        elif isinstance(value, list) and all(isinstance(item, str) for item in value):
            normalized = list(value)
        else:
            raise ValueError(f"{name}[{repo!r}] must be a string or list of strings.")
        commands[repo.strip()] = [item.strip() for item in normalized if item.strip()]
    return commands


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings."""
    redis_url = os.getenv("NEXUS_REDIS_URL", "redis://localhost:6379/0")
    tela_github_token = os.getenv("NEXUS_GITHUB_TOKEN")
    sophie_github_token = os.getenv("NEXUS_SOPHIE_GITHUB_TOKEN")
    jules_github_token = os.getenv("NEXUS_JULES_GITHUB_TOKEN")
    marc_github_token = os.getenv("NEXUS_MARC_GITHUB_TOKEN")
    assistant_github_token = os.getenv("NEXUS_ASSISTANT_GITHUB_TOKEN") or os.getenv("NEXUS_SECRETARY_GITHUB_TOKEN")
    github_tokens = {
        "tela": tela_github_token,
        "sophie": sophie_github_token,
        "jules": jules_github_token,
        "marc": marc_github_token,
        "assistant": assistant_github_token,
    }

    return Settings(
        api_key=os.getenv("NEXUS_API_KEY"),
        base_url=os.getenv("NEXUS_BASE_URL", "https://api.openai.com/v1"),
        model=os.getenv("NEXUS_MODEL", "gpt-4o"),
        max_context=int(os.getenv("NEXUS_MAX_CONTEXT", "128000")),
        max_attempts=int(os.getenv("NEXUS_MAX_ATTEMPTS", "256")),
        github_tokens=github_tokens,
        database_url=os.getenv(
            "NEXUS_DATABASE_URL",
            "postgresql+asyncpg://postgres:123456@localhost:5432/nexus",
        ),
        redis_url=redis_url,
        redis_message_ttl_seconds=int(
            os.getenv("NEXUS_REDIS_MESSAGE_TTL_SECONDS", "86400"),
        ),
        celery_broker_url=os.getenv("NEXUS_CELERY_BROKER_URL", redis_url),
        celery_result_backend=os.getenv("NEXUS_CELERY_RESULT_BACKEND", redis_url),
        celery_queue=os.getenv("NEXUS_CELERY_QUEUE", "nexus_agent_tasks"),
        celery_visibility_timeout_seconds=int(
            os.getenv("NEXUS_CELERY_VISIBILITY_TIMEOUT_SECONDS", "86400"),
        ),
        celery_task_publish_max_retries=int(
            os.getenv("NEXUS_CELERY_TASK_PUBLISH_MAX_RETRIES", "3"),
        ),
        celery_broker_connection_timeout_seconds=float(
            os.getenv("NEXUS_CELERY_BROKER_CONNECTION_TIMEOUT_SECONDS", "2.0"),
        ),
        github_feedback_poll_interval_seconds=int(
            os.getenv("NEXUS_GITHUB_FEEDBACK_POLL_INTERVAL_SECONDS", "60"),
        ),
        github_feedback_poll_task_limit=int(
            os.getenv("NEXUS_GITHUB_FEEDBACK_POLL_TASK_LIMIT", "100"),
        ),
        github_feedback_batch_size=int(
            os.getenv("NEXUS_GITHUB_FEEDBACK_BATCH_SIZE", "20"),
        ),
        github_feedback_http_timeout_seconds=float(
            os.getenv("NEXUS_GITHUB_FEEDBACK_HTTP_TIMEOUT_SECONDS", "10.0"),
        ),
        github_oauth_client_id=os.getenv("NEXUS_GITHUB_OAUTH_CLIENT_ID"),
        github_oauth_client_secret=os.getenv("NEXUS_GITHUB_OAUTH_CLIENT_SECRET"),
        github_oauth_redirect_uri=os.getenv(
            "NEXUS_GITHUB_OAUTH_REDIRECT_URI",
            "http://localhost:8000/v1/auth/github/callback",
        ),
        auth_session_cookie_name=os.getenv("NEXUS_AUTH_SESSION_COOKIE_NAME", "nexus_session"),
        auth_session_ttl_seconds=int(os.getenv("NEXUS_AUTH_SESSION_TTL_SECONDS", "2592000")),
        frontend_base_url=os.getenv("NEXUS_FRONTEND_BASE_URL", "http://localhost:5174"),
        product_discovery_poll_interval_seconds=int(
            os.getenv("NEXUS_PRODUCT_DISCOVERY_POLL_INTERVAL_SECONDS", "3600"),
        ),
        product_discovery_poll_task_limit=int(
            os.getenv("NEXUS_PRODUCT_DISCOVERY_POLL_TASK_LIMIT", "100"),
        ),
        product_discovery_recent_proposal_limit=int(
            os.getenv("NEXUS_PRODUCT_DISCOVERY_RECENT_PROPOSAL_LIMIT", "5"),
        ),
        product_discovery_pending_proposal_limit=int(
            os.getenv("NEXUS_PRODUCT_DISCOVERY_PENDING_PROPOSAL_LIMIT", "50"),
        ),
        product_workflow_poll_interval_seconds=int(
            os.getenv("NEXUS_PRODUCT_WORKFLOW_POLL_INTERVAL_SECONDS", "60"),
        ),
        secretary_enabled=_env_bool("NEXUS_SECRETARY_ENABLED", False),
        secretary_github_token=assistant_github_token,
        secretary_discord_bot_token=os.getenv("NEXUS_SECRETARY_DISCORD_BOT_TOKEN"),
        secretary_discord_user_id=os.getenv("NEXUS_SECRETARY_DISCORD_USER_ID"),
        secretary_poll_interval_seconds=int(
            os.getenv("NEXUS_SECRETARY_POLL_INTERVAL_SECONDS", "120"),
        ),
        secretary_merge_method=os.getenv("NEXUS_SECRETARY_MERGE_METHOD", "squash"),
        secretary_test_commands=_env_test_commands("NEXUS_SECRETARY_TEST_COMMANDS_JSON"),
    )
