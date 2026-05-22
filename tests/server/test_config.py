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


def test_product_discovery_poll_interval_defaults_to_hourly(monkeypatch):
    """Verify product discovery poll interval defaults to hourly."""
    get_settings.cache_clear()
    monkeypatch.delenv("NEXUS_PRODUCT_DISCOVERY_POLL_INTERVAL_SECONDS", raising=False)

    try:
        settings = get_settings()
    finally:
        get_settings.cache_clear()

    assert settings.product_discovery_poll_interval_seconds == 3600


def test_product_discovery_governance_defaults_are_conservative(monkeypatch):
    """Verify product discovery governance settings have stable defaults."""
    get_settings.cache_clear()
    monkeypatch.delenv("NEXUS_PRODUCT_DISCOVERY_PENDING_PROPOSAL_LIMIT", raising=False)
    monkeypatch.delenv("NEXUS_PRODUCT_DISCOVERY_COOLDOWN_SECONDS", raising=False)
    monkeypatch.delenv("NEXUS_PRODUCT_DISCOVERY_RECENT_CONTEXT_LIMIT", raising=False)

    try:
        settings = get_settings()
    finally:
        get_settings.cache_clear()

    assert settings.product_discovery_pending_proposal_limit == 3
    assert settings.product_discovery_cooldown_seconds == 86400
    assert settings.product_discovery_recent_context_limit == 5


def test_product_discovery_governance_settings_are_loaded(monkeypatch):
    """Verify product discovery governance settings are loaded from env."""
    get_settings.cache_clear()
    monkeypatch.setenv("NEXUS_PRODUCT_DISCOVERY_PENDING_PROPOSAL_LIMIT", "7")
    monkeypatch.setenv("NEXUS_PRODUCT_DISCOVERY_COOLDOWN_SECONDS", "7200")
    monkeypatch.setenv("NEXUS_PRODUCT_DISCOVERY_RECENT_CONTEXT_LIMIT", "12")

    try:
        settings = get_settings()
    finally:
        get_settings.cache_clear()

    assert settings.product_discovery_pending_proposal_limit == 7
    assert settings.product_discovery_cooldown_seconds == 7200
    assert settings.product_discovery_recent_context_limit == 12


def test_product_discovery_governance_does_not_change_poll_settings(monkeypatch):
    """Verify governance env vars do not affect existing poll settings."""
    get_settings.cache_clear()
    monkeypatch.setenv("NEXUS_PRODUCT_DISCOVERY_PENDING_PROPOSAL_LIMIT", "7")
    monkeypatch.setenv("NEXUS_PRODUCT_DISCOVERY_COOLDOWN_SECONDS", "7200")
    monkeypatch.setenv("NEXUS_PRODUCT_DISCOVERY_RECENT_CONTEXT_LIMIT", "12")
    monkeypatch.setenv("NEXUS_PRODUCT_DISCOVERY_POLL_INTERVAL_SECONDS", "33")
    monkeypatch.setenv("NEXUS_PRODUCT_DISCOVERY_POLL_TASK_LIMIT", "44")

    try:
        settings = get_settings()
    finally:
        get_settings.cache_clear()

    assert settings.product_discovery_poll_interval_seconds == 33
    assert settings.product_discovery_poll_task_limit == 44


def test_frontend_base_url_is_loaded(monkeypatch):
    """Verify frontend base url is loaded."""
    get_settings.cache_clear()
    monkeypatch.setenv("NEXUS_FRONTEND_BASE_URL", "http://localhost:5174")

    try:
        settings = get_settings()
    finally:
        get_settings.cache_clear()

    assert settings.frontend_base_url == "http://localhost:5174"


def test_product_discovery_recent_proposal_limit_is_loaded(monkeypatch):
    """Verify product discovery recent proposal limit is loaded."""
    get_settings.cache_clear()
    monkeypatch.setenv("NEXUS_PRODUCT_DISCOVERY_RECENT_PROPOSAL_LIMIT", "3")

    try:
        settings = get_settings()
    finally:
        get_settings.cache_clear()

    assert settings.product_discovery_recent_proposal_limit == 3


def test_product_discovery_pending_proposal_limit_default_is_conservative(monkeypatch):
    """Verify product discovery pending proposal limit default."""
    get_settings.cache_clear()
    monkeypatch.delenv("NEXUS_PRODUCT_DISCOVERY_PENDING_PROPOSAL_LIMIT", raising=False)

    try:
        settings = get_settings()
    finally:
        get_settings.cache_clear()

    assert settings.product_discovery_pending_proposal_limit == 3


def test_product_discovery_pending_proposal_limit_is_loaded(monkeypatch):
    """Verify product discovery pending proposal limit is loaded."""
    get_settings.cache_clear()
    monkeypatch.setenv("NEXUS_PRODUCT_DISCOVERY_PENDING_PROPOSAL_LIMIT", "7")

    try:
        settings = get_settings()
    finally:
        get_settings.cache_clear()

    assert settings.product_discovery_pending_proposal_limit == 7
