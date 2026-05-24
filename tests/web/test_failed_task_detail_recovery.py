import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TASK_DETAIL = ROOT / "web/src/pages/TaskDetailPage.tsx"
I18N = ROOT / "web/src/i18n/resources.json"


def test_failed_task_detail_renders_recovery_panel_and_category_badge():
    source = TASK_DETAIL.read_text()

    assert "task.status === 'failed'" in source
    assert "taskDetail.recoveryTitle" in source
    assert "taskDetail.recoveryDescription" in source
    assert "taskDetail.category" in source
    assert "taskDetail.categories.${task.category}" in source
    assert '<Badge variant="outline">' in source


def test_failed_task_retry_requires_confirmation_and_submits_original_task():
    source = TASK_DETAIL.read_text()

    assert "window.confirm(t('taskDetail.retryConfirm'))" in source
    assert "await createTask({" in source
    for field in ["agent: task.agent", "agent_instance_id: task.agent_instance_id", "question: task.question", "external_issue_url: task.external_issue_url"]:
        assert field in source


def test_failed_task_retry_success_navigates_and_notifies():
    source = TASK_DETAIL.read_text()

    assert "toast.success(t('taskDetail.retryStarted')" in source
    assert "description: t('taskDetail.retryStartedDescription')" in source
    assert "navigate(`/task/${response.task_id}`)" in source


def test_failed_task_retry_failure_shows_error_toast():
    source = TASK_DETAIL.read_text()

    assert "toast.error(t('taskDetail.retryFailed')" in source
    assert "getErrorDetail(error, t('taskDetail.retryFailedDescription'))" in source


def test_failed_task_recovery_copy_is_localized():
    resources = json.loads(I18N.read_text())

    for language in ["zh", "en"]:
        task_detail = resources[language]["translation"]["taskDetail"]
        for key in [
            "category",
            "categories",
            "recoveryTitle",
            "recoveryDescription",
            "retry",
            "retrying",
            "retryConfirm",
            "retryStarted",
            "retryStartedDescription",
            "retryFailed",
            "retryFailedDescription",
        ]:
            assert key in task_detail
        assert "coding" in task_detail["categories"]
        assert "product discovery" in task_detail["categories"]
