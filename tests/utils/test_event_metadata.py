from src.utils.event_metadata import REDACTED_VALUE, build_safe_event_metadata


def test_build_safe_event_metadata_keeps_defaults_and_drops_extra_fields() -> None:
    """Verify only default safe event fields are retained."""
    metadata = {
        "tool_name": "RunCommand",
        "summary": "ls -la",
        "raw_arguments": {"cmd": "ls -la"},
    }

    safe = build_safe_event_metadata(metadata)

    assert safe == {"tool_name": "RunCommand", "summary": "ls -la"}


def test_build_safe_event_metadata_redacts_sensitive_nested_keys() -> None:
    """Verify allowlisted nested metadata is recursively redacted."""
    safe = build_safe_event_metadata(
        {
            "summary": "created issue",
            "payload": {
                "token": "ghp_secret",
                "Authorization": "Bearer abc",
                "headers": {"api-key": "abc", "content_type": "json"},
            },
        },
        allowed_fields={"payload"},
    )

    assert safe["payload"] == {
        "token": REDACTED_VALUE,
        "Authorization": REDACTED_VALUE,
        "headers": {"api-key": REDACTED_VALUE, "content_type": "json"},
    }


def test_build_safe_event_metadata_truncates_strings() -> None:
    """Verify long strings are bounded in safe metadata."""
    safe = build_safe_event_metadata(
        {"summary": "abcdef", "payload": ["123456", {"note": "xyz"}]},
        allowed_fields={"payload"},
        max_string_length=3,
    )

    assert safe == {"summary": "abc…", "payload": ["123…", {"note": "xyz"}]}
