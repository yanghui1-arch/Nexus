from src.tools.sandbox import CREATE_FILE, EDIT_FILE


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
