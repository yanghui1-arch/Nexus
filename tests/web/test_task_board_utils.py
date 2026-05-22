from pathlib import Path


UTILS = Path(__file__).resolve().parents[2] / "web/src/pages/task-board/utils.ts"


def test_task_board_defines_coding_task_filter() -> None:
    source = UTILS.read_text()

    assert "const TASK_BOARD_CATEGORY = 'coding'" in source
    assert "task.category === TASK_BOARD_CATEGORY" in source


def test_task_board_applies_coding_filter_to_visible_tasks() -> None:
    source = UTILS.read_text()

    assert "tasks.filter(task => isTaskBoardTask(task) && task.repo === repoFilter)" in source


def test_task_board_applies_coding_filter_to_grouped_tasks() -> None:
    source = UTILS.read_text()

    assert "if (isTaskBoardTask(task) && isTaskBoardStatus(task.status))" in source
