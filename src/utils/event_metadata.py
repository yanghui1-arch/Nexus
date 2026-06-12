"""Safe event metadata construction helpers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

DEFAULT_ALLOWED_METADATA_FIELDS = frozenset({"tool_name", "summary"})
SENSITIVE_KEY_PARTS = frozenset({"token", "password", "secret", "key", "authorization", "env"})
REDACTED_VALUE = "[REDACTED]"
DEFAULT_MAX_STRING_LENGTH = 200


def build_safe_event_metadata(
    metadata: Mapping[str, Any] | None = None,
    *,
    tool_name: str | None = None,
    summary: str | None = None,
    allowed_fields: set[str] | frozenset[str] | None = None,
    max_string_length: int = DEFAULT_MAX_STRING_LENGTH,
) -> dict[str, Any]:
    """Return allowlisted, redacted, and length-bounded event metadata."""
    allowed = DEFAULT_ALLOWED_METADATA_FIELDS | (allowed_fields or frozenset())
    source: dict[str, Any] = {}
    if metadata:
        source.update(metadata)
    if tool_name is not None:
        source["tool_name"] = tool_name
    if summary is not None:
        source["summary"] = summary

    return {
        key: _sanitize_value(value, max_string_length=max_string_length)
        for key, value in source.items()
        if key in allowed
    }


def _sanitize_value(value: Any, *, max_string_length: int) -> Any:
    if isinstance(value, str):
        return _truncate(value, max_string_length)
    if isinstance(value, Mapping):
        return {
            str(key): (
                REDACTED_VALUE
                if _is_sensitive_key(str(key))
                else _sanitize_value(item, max_string_length=max_string_length)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_sanitize_value(item, max_string_length=max_string_length) for item in value]
    return value


def _truncate(value: str, max_length: int) -> str:
    if max_length < 1 or len(value) <= max_length:
        return value
    return f"{value[:max_length]}…"


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return any(part in normalized for part in SENSITIVE_KEY_PARTS)
