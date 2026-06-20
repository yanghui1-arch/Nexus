from __future__ import annotations

from src.server.config import get_settings


def test_marc_github_token_is_loaded(monkeypatch):
    """Verify marc github token is loaded."""
    get_settings.cache_clear()
    monkeypatch.setenv("NEXUS_MARC_GITHUB_TOKEN", "marc-token")

    try:
        settings = get_settings()
    finally:
        get_settings.cache_clear()

    assert settings.github_tokens["marc"] == "marc-token"


def test_jules_github_token_is_loaded(monkeypatch):
    """Verify jules github token is loaded."""
    get_settings.cache_clear()
    monkeypatch.setenv("NEXUS_JULES_GITHUB_TOKEN", "jules-token")

    try:
        settings = get_settings()
    finally:
        get_settings.cache_clear()

    assert settings.github_tokens["jules"] == "jules-token"


def test_product_discovery_poll_interval_defaults_to_hourly(monkeypatch):
    """Verify product discovery poll interval defaults to hourly."""
    get_settings.cache_clear()
    monkeypatch.delenv("NEXUS_PRODUCT_DISCOVERY_POLL_INTERVAL_SECONDS", raising=False)

    try:
        settings = get_settings()
    finally:
        get_settings.cache_clear()

    assert settings.product_discovery_poll_interval_seconds == 3600


def test_product_workflow_poll_interval_defaults_to_minutely(monkeypatch):
    """Verify product workflow poll interval defaults to one minute."""
    get_settings.cache_clear()
    monkeypatch.delenv("NEXUS_PRODUCT_WORKFLOW_POLL_INTERVAL_SECONDS", raising=False)

    try:
        settings = get_settings()
    finally:
        get_settings.cache_clear()

    assert settings.product_workflow_poll_interval_seconds == 60


def test_frontend_base_url_is_loaded(monkeypatch):
    """Verify frontend base url is loaded."""
    get_settings.cache_clear()
    monkeypatch.setenv("NEXUS_FRONTEND_BASE_URL", "http://localhost:5174")

    try:
        settings = get_settings()
    finally:
        get_settings.cache_clear()

    assert settings.frontend_base_url == "http://localhost:5174"


def test_discord_gateway_settings_are_loaded(monkeypatch):
    """Verify Discord Gateway settings are loaded from env."""
    get_settings.cache_clear()
    monkeypatch.setenv("NEXUS_DISCORD_GATEWAY_ENABLED", "true")
    monkeypatch.setenv("NEXUS_DISCORD_GATEWAY_BOT_TOKEN", "discord-token")
    monkeypatch.setenv("NEXUS_DISCORD_GATEWAY_CHANNEL_IDS", "111, 222")
    monkeypatch.setenv("NEXUS_DISCORD_GATEWAY_USER_IDS", '["333", "444"]')

    try:
        settings = get_settings()
    finally:
        get_settings.cache_clear()

    assert settings.discord_gateway_enabled is True
    assert settings.discord_gateway_bot_token == "discord-token"
    assert settings.discord_gateway_channel_ids == ["111", "222"]
    assert settings.discord_gateway_user_ids == ["333", "444"]


def test_product_discovery_recent_proposal_limit_is_loaded(monkeypatch):
    """Verify product discovery recent proposal limit is loaded."""
    get_settings.cache_clear()
    monkeypatch.setenv("NEXUS_PRODUCT_DISCOVERY_RECENT_PROPOSAL_LIMIT", "3")

    try:
        settings = get_settings()
    finally:
        get_settings.cache_clear()

    assert settings.product_discovery_recent_proposal_limit == 3


def test_product_discovery_pending_proposal_limit_defaults_to_50(monkeypatch):
    """Verify product discovery pending proposal limit default."""
    get_settings.cache_clear()
    monkeypatch.delenv("NEXUS_PRODUCT_DISCOVERY_PENDING_PROPOSAL_LIMIT", raising=False)

    try:
        settings = get_settings()
    finally:
        get_settings.cache_clear()

    assert settings.product_discovery_pending_proposal_limit == 50


def test_product_discovery_pending_proposal_limit_is_loaded(monkeypatch):
    """Verify product discovery pending proposal limit is loaded."""
    get_settings.cache_clear()
    monkeypatch.setenv("NEXUS_PRODUCT_DISCOVERY_PENDING_PROPOSAL_LIMIT", "7")

    try:
        settings = get_settings()
    finally:
        get_settings.cache_clear()

    assert settings.product_discovery_pending_proposal_limit == 7


def test_product_workflow_poll_interval_is_loaded(monkeypatch):
    """Verify product workflow poll interval is loaded."""
    get_settings.cache_clear()
    monkeypatch.setenv("NEXUS_PRODUCT_WORKFLOW_POLL_INTERVAL_SECONDS", "15")

    try:
        settings = get_settings()
    finally:
        get_settings.cache_clear()

    assert settings.product_workflow_poll_interval_seconds == 15


def test_assistant_settings_are_loaded(monkeypatch):
    """Verify assistant settings are loaded from env."""
    get_settings.cache_clear()
    monkeypatch.setenv("NEXUS_ASSISTANT_ENABLED", "true")
    monkeypatch.setenv("NEXUS_ASSISTANT_GITHUB_TOKEN", "assistant-token")
    monkeypatch.setenv("NEXUS_ASSISTANT_POLL_INTERVAL_SECONDS", "30")
    monkeypatch.setenv("NEXUS_ASSISTANT_MERGE_METHOD", "merge")
    monkeypatch.setenv(
        "NEXUS_ASSISTANT_TEST_COMMANDS_JSON",
        '{"owner/repo":["pytest"],"*":"uv run pytest"}',
    )

    try:
        settings = get_settings()
    finally:
        get_settings.cache_clear()

    assert settings.assistant_enabled is True
    assert settings.assistant_github_token == "assistant-token"
    assert settings.github_tokens["assistant"] == "assistant-token"
    assert settings.assistant_poll_interval_seconds == 30
    assert settings.assistant_merge_method == "merge"
    assert settings.assistant_test_commands == {
        "owner/repo": ["pytest"],
        "*": ["uv run pytest"],
    }
