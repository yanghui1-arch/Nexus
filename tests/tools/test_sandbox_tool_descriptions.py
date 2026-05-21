from src.tools.sandbox import CREATE_FILE, EDIT_FILE, SandboxToolKit


def _description(tool: dict) -> str:
    return tool["function"]["description"]


def _parameter_description(tool: dict, name: str) -> str:
    return tool["function"]["parameters"]["properties"][name]["description"]


def test_create_file_description_guides_create_or_full_overwrite() -> None:
    description = _description(CREATE_FILE)

    assert "Create a new text file" in description
    assert "completely replace" in description
    assert "For small edits" in description


def test_edit_file_description_includes_change_delete_insert_examples() -> None:
    description = _description(EDIT_FILE)

    assert "Change" in description
    assert "Delete" in description
    assert "Insert" in description
    assert "old_str='x = 1'" in description
    assert "new_str=''" in description


def test_edit_file_argument_descriptions_reinforce_safe_replacements() -> None:
    assert "multi-line" in _parameter_description(EDIT_FILE, "old_str")
    assert "empty to delete" in _parameter_description(EDIT_FILE, "new_str")
    assert "include old_str plus inserted text" in _parameter_description(EDIT_FILE, "new_str")


class _FakeSandbox:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def write_file(self, path: str, content: str) -> dict:
        self.calls.append((path, content))
        return {"success": True, "path": path, "error": None}


async def test_sandbox_toolkit_keeps_write_file_alias_for_internal_callers() -> None:
    sandbox = _FakeSandbox()
    toolkit = SandboxToolKit(sandbox)  # type: ignore[arg-type]

    result = await toolkit.write_file("/workspace/new.py", "print('hi')\n")

    assert result == {"success": True, "path": "/workspace/new.py", "error": None}
    assert sandbox.calls == [("/workspace/new.py", "print('hi')\n")]
    assert "WriteFile" not in toolkit.all_tools
    assert "CreateFile" in toolkit.all_tools
