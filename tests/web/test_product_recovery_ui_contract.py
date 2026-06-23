from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DETAIL_CARD = ROOT / "web/src/pages/product-research/components/ProposalDetailCard.tsx"
PRODUCT_PAGE = ROOT / "web/src/pages/product-research/index.tsx"
RESOURCES = ROOT / "web/src/i18n/resources.json"
TIMELINE = ROOT / "web/src/pages/process-tracking/components/ExecutionTimeline.tsx"


def test_recovery_buttons_disable_while_request_is_pending():
    source = DETAIL_CARD.read_text()

    assert source.count("disabled={recoveringPlanning}") >= 2
    assert "t('productResearch.planningRecovering')" in source
    assert "t('productResearch.planningRetrying')" in source


def test_recovery_confirmation_copy_is_used_before_dispatch():
    page_source = PRODUCT_PAGE.read_text()
    resources = RESOURCES.read_text()

    assert "window.confirm(t('productResearch.planningRecoverConfirm'))" in page_source
    assert '"planningRecoverConfirm"' in resources
    assert "retryProductProposalPlanning(currentProposalId)" in page_source


def test_recovery_event_types_are_visible_in_task_timeline():
    source = TIMELINE.read_text()

    assert "MUTED_EVENT_TYPES" in source
    assert "recovery" not in source[source.index("MUTED_EVENT_TYPES"):source.index("function toolNames")]
    assert "return formatEventType(event.event_type)" in source
