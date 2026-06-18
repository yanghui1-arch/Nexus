from src.utils.event_metadata import build_status_event_metadata


def test_status_event_metadata_records_tools_errors_and_checkpoint_result():
    metadata = build_status_event_metadata(
        {
            "process": "SAVE_CHECKPOINT",
            "agent_content": "Running tests",
            "current_use_tool": ["RunCommand", "CreateFile"],
            "current_use_tool_args": [
                {"cmd": "pytest", "token": "secret-value"},
                {"path": "/workspace/file.py", "content": "x"},
            ],
            "checkpoint_result": {"saved": True, "message": "ok"},
            "error": "transient failure",
            "retry_info": {"attempt": 2, "max_attempts": 3},
        }
    )

    assert metadata == {
        "summary": "Running tests",
        "tool_names": ["RunCommand", "CreateFile"],
        "tool_summary": "RunCommand, CreateFile",
        "tool_call_summaries": [
            {"cmd": "pytest", "token": "[REDACTED]"},
            {"path": "/workspace/file.py", "content": "x"},
        ],
        "checkpoint_result": {"saved": True, "message": "ok"},
        "error_summary": "transient failure",
        "retry": {"attempt": 2, "max_attempts": 3},
    }


def test_status_event_metadata_handles_missing_fields_with_minimal_summary():
    assert build_status_event_metadata({}) == {"summary": "PROCESS"}

