from pathlib import Path

CLASSIFIER = Path(__file__).resolve().parents[2] / "web/src/lib/failure-reason-classifier.ts"
TASK_CARD = Path(__file__).resolve().parents[2] / "web/src/pages/task-board/components/TaskBoardTaskCard.tsx"
TASK_DETAIL = Path(__file__).resolve().parents[2] / "web/src/pages/TaskDetailPage.tsx"


def test_failure_reason_classifier_covers_keyword_categories():
    source = CLASSIFIER.read_text()

    expected_keywords = {
        "workspace/config": ["workspace", "configuration", "environment", "secret"],
        "github/pr": ["github", "pull request", "merge conflict", "repository not found"],
        "sandbox/dispatch": ["sandbox", "dispatch", "celery", "docker"],
        "agent/runtime": ["agent", "traceback", "exception", "tool call"],
    }
    for category, keywords in expected_keywords.items():
        assert f"category: '{category}'" in source
        for keyword in keywords:
            assert f"'{keyword}'" in source


def test_failure_reason_classifier_has_unknown_fallbacks():
    source = CLASSIFIER.read_text()

    assert "| 'unknown';" in source
    assert "if (!normalized)" in source
    assert "return 'unknown';" in source
    assert "?.category ?? 'unknown'" in source


def test_failure_reason_badges_are_consistent_between_queue_and_detail():
    task_card = TASK_CARD.read_text()
    task_detail = TASK_DETAIL.read_text()

    for source in [task_card, task_detail]:
        assert "classifyFailureReason" in source
        assert "failureReason" in source
        assert "<Badge variant=\"outline\"" in source

    assert "classifyFailureReason(task.error)" in task_card
    assert "classifyFailureReason(task.error)" in task_detail
