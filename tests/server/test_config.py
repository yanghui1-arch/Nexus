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
