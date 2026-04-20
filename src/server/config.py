from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv


load_dotenv()


def _int_env(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None or raw_value == "":
        return default
    try:
        return int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {raw_value!r}") from exc


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
    task_dispatch_lease_seconds: int


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    redis_url = os.getenv("NEXUS_REDIS_URL", "redis://localhost:6379/0")
    tela_github_token = os.getenv("NEXUS_GITHUB_TOKEN")
    sophie_github_token = os.getenv("NEXUS_SOPHIE_GITHUB_TOKEN")
    github_tokens = {
        "tela": tela_github_token,
        "sophie": sophie_github_token,
    }

    return Settings(
        api_key=os.getenv("NEXUS_API_KEY"),
        base_url=os.getenv("NEXUS_BASE_URL", "https://api.openai.com/v1"),
        model=os.getenv("NEXUS_MODEL", "gpt-4o"),
        max_context=_int_env("NEXUS_MAX_CONTEXT", 128000),
        max_attempts=_int_env("NEXUS_MAX_ATTEMPTS", 256),
        github_tokens=github_tokens,
        database_url=os.getenv(
            "NEXUS_DATABASE_URL",
            "postgresql+asyncpg://postgres:123456@localhost:5432/nexus",
        ),
        redis_url=redis_url,
        redis_message_ttl_seconds=_int_env("NEXUS_REDIS_MESSAGE_TTL_SECONDS", 86400),
        celery_broker_url=os.getenv("NEXUS_CELERY_BROKER_URL", redis_url),
        celery_result_backend=os.getenv("NEXUS_CELERY_RESULT_BACKEND", redis_url),
        celery_queue=os.getenv("NEXUS_CELERY_QUEUE", "nexus_agent_tasks"),
        celery_visibility_timeout_seconds=_int_env("NEXUS_CELERY_VISIBILITY_TIMEOUT_SECONDS", 86400),
        task_dispatch_lease_seconds=_int_env("NEXUS_TASK_DISPATCH_LEASE_SECONDS", 60),
    )
