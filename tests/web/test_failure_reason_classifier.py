from pathlib import Path

CLASSIFIER = Path(__file__).resolve().parents[2] / "web/src/lib/failure-reason-classifier.ts"
TASK_CARD = Path(__file__).resolve().parents[2] / "web/src/pages/task-board/components/TaskBoardTaskCard.tsx"
TASK_DETAIL = Path(__file__).resolve().parents[2] / "web/src/pages/TaskDetailPage.tsx"


def test_failure_reason_classifier_contract_categories():
    source = CLASSIFIER.read_text()

    assert "export function classifyFailureReason" in source
    for category in [
        "workspace/config",
        "github/pr",
        "sandbox/dispatch",
        "agent/runtime",
        "unknown",
    ]:
        assert category in source


def test_failure_reason_classifier_is_keyword_based_and_deterministic():
    source = CLASSIFIER.read_text()

    for keyword in ["workspace", "github", "pull request", "sandbox", "dispatch", "agent", "traceback"]:
        assert keyword in source
    assert "Math.random" not in source
    assert "Date.now" not in source


def test_failure_reason_classifier_empty_or_unmatched_text_returns_unknown():
    source = CLASSIFIER.read_text()

    assert "if (!normalized)" in source
    assert "?? 'unknown'" in source


def test_failure_reason_badges_are_ui_only_and_do_not_gate_retry():
    task_card = TASK_CARD.read_text()
    task_detail = TASK_DETAIL.read_text()

    assert "classifyFailureReason(task.error)" in task_card
    assert "classifyFailureReason(task.error)" in task_detail
    assert "retry" not in task_card.lower()
    assert "retry" not in task_detail.lower()
