from __future__ import annotations

import os
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
    task_dispatch_lease_seconds: int
    github_feedback_poll_interval_seconds: int
    github_feedback_poll_task_limit: int
    github_feedback_batch_size: int
    github_feedback_http_timeout_seconds: float
    github_oauth_client_id: str | None
    github_oauth_client_secret: str | None
    github_oauth_redirect_uri: str
    auth_session_cookie_name: str
    auth_session_ttl_seconds: int


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
        task_dispatch_lease_seconds=int(
            os.getenv("NEXUS_TASK_DISPATCH_LEASE_SECONDS", "60"),
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
    )
