from pathlib import Path

REVIEW_PAGE = Path(__file__).resolve().parents[2] / "web/src/pages/nexus-review/index.tsx"
WORKSPACE_HOOK = Path(__file__).resolve().parents[2] / "web/src/lib/useWorkspaceRecords.ts"
I18N = Path(__file__).resolve().parents[2] / "web/src/i18n/resources.json"


def test_failed_queue_has_status_states_and_navigation():
    source = REVIEW_PAGE.read_text()

    for snippet in [
        "id: 'failed'",
        "tasksError",
        "reload",
        "codeReview.refreshQueue",
        "codeReview.loadFailedTitle",
        "codeReview.emptyFailedQueue",
        'to="/task-board"',
        'to="/publish-task"',
    ]:
        assert snippet in source


def test_workspace_records_exposes_refresh_and_task_error_state():
    source = WORKSPACE_HOOK.read_text()

    for snippet in [
        "isRefreshing: boolean",
        "tasksError: string | null",
        "setIsRefreshing(true)",
        "setTasksError(result.tasksError)",
    ]:
        assert snippet in source


def test_failed_queue_copy_is_localized():
    source = I18N.read_text()

    for snippet in [
        "There are no failed coding tasks.",
        "Back to Task Board",
        "Create task",
        "当前没有失败的 coding tasks。",
        "返回任务看板",
        "创建任务",
    ]:
        assert snippet in source
