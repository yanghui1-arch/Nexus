from pathlib import Path

COMPONENT = (
    Path(__file__).resolve().parents[2]
    / "web/src/pages/product-research/components/ProposalDetailCard.tsx"
)


def test_proposal_detail_shows_review_readiness_checklist_from_parser():
    source = COMPONENT.read_text()

    assert "parseProposalAnswerSections(proposal.answer)" in source
    assert "getProposalReviewReadinessItems" in source
    assert "productResearch.reviewReadinessChecklist" in source


def test_review_readiness_checklist_is_non_blocking_for_review_actions():
    source = COMPONENT.read_text()

    approve_index = source.index("onReview(proposal.id, 'approved')")
    reject_index = source.index("onReview(proposal.id, 'rejected')")
    checklist_index = source.index("reviewReadinessItems.map")

    assert checklist_index < reject_index < approve_index
    assert "disabled={isBusy}" in source
    assert "reviewReadinessItems" not in source[source.index("<footer"):]
