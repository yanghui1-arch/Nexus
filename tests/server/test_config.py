from __future__ import annotations

from src.server.config import get_settings




def test_marc_github_token_is_loaded(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("NEXUS_MARC_GITHUB_TOKEN", "marc-token")

    try:
        settings = get_settings()
    finally:
        get_settings.cache_clear()

    assert settings.github_tokens["marc"] == "marc-token"
