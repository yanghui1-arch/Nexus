from pathlib import Path

DISPLAY = Path(__file__).resolve().parents[2] / "web/src/lib/task-display.tsx"
TASK_CARD = Path(__file__).resolve().parents[2] / "web/src/pages/task-board/components/TaskBoardTaskCard.tsx"
TASK_DETAIL = Path(__file__).resolve().parents[2] / "web/src/pages/TaskDetailPage.tsx"


def test_shared_task_display_defines_fallback_truncation_and_source_links():
    source = DISPLAY.read_text()

    assert "UNKNOWN_TASK_DISPLAY_VALUE = 'unknown'" in source
    assert "TASK_ERROR_PREVIEW_LIMIT = 160" in source
    assert "export function truncateTaskError" in source
    assert "export function taskSourceNode" in source
    assert "external_issue_url?.trim() || task.external_pull_request_url?.trim()" in source
    assert 'target="_blank"' in source
    assert 'rel="noreferrer"' in source


def test_failed_task_queue_and_task_detail_reuse_shared_display_logic():
    task_card = TASK_CARD.read_text()
    task_detail = TASK_DETAIL.read_text()

    for helper in ["taskCategoryLabel", "taskSourceNode", "truncateTaskError"]:
        assert helper in task_card
        assert helper in task_detail

    assert "title={task.error ?? undefined}" in task_card
    assert "title={task.error ?? undefined}" in task_detail
