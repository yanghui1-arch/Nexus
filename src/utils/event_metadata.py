"""Safe event metadata construction helpers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

DEFAULT_MAX_STRING_LENGTH = 200
SENSITIVE_KEY_PARTS = frozenset({"authorization", "env", "key", "password", "secret", "token"})
REDACTED_VALUE = "[REDACTED]"


def build_status_event_metadata(
    status: Mapping[str, Any],
    *,
    max_string_length: int = DEFAULT_MAX_STRING_LENGTH,
) -> dict[str, Any]:
    """Build scrubbed metadata for an agent status payload.

    Missing fields are tolerated so callers can still persist a minimal event
    summary for partially populated progress payloads.
    """
    process = str(status.get("process") or status.get("status") or status.get("event") or "PROCESS")
    summary = status.get("summary") or status.get("agent_content") or status.get("description") or process
    metadata: dict[str, Any] = {"summary": _truncate(str(summary), max_string_length)}

    tools = status.get("current_use_tool") or status.get("tools") or status.get("tool_names")
    tool_names = [str(tool) for tool in tools if tool] if isinstance(tools, list) else []
    if tool_names:
        metadata["tool_names"] = tool_names
        metadata["tool_summary"] = ", ".join(tool_names)

    tool_args = status.get("current_use_tool_args") or status.get("tool_call_summaries")
    if isinstance(tool_args, list) and tool_args:
        metadata["tool_call_summaries"] = [
            _sanitize_value(item, max_string_length=max_string_length) for item in tool_args
        ]

    checkpoint_result = status.get("checkpoint_result")
    if checkpoint_result is not None:
        metadata["checkpoint_result"] = _sanitize_value(
            checkpoint_result,
            max_string_length=max_string_length,
        )

    error = status.get("error") or status.get("exception")
    if error:
        metadata["error_summary"] = _truncate(str(error), max_string_length)

    retry = status.get("retry") or status.get("retry_info") or status.get("attempt")
    if retry is not None:
        metadata["retry"] = _sanitize_value(retry, max_string_length=max_string_length)

    return metadata


def _sanitize_value(value: Any, *, max_string_length: int) -> Any:
    if isinstance(value, str):
        return _truncate(value, max_string_length)
    if isinstance(value, Mapping):
        return {
            str(key): REDACTED_VALUE if _is_sensitive_key(str(key)) else _sanitize_value(item, max_string_length=max_string_length)
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
