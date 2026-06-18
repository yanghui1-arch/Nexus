from pathlib import Path

DETAIL_CARD = (
    Path(__file__).resolve().parents[2]
    / "web/src/pages/product-research/components/ProposalDetailCard.tsx"
)


def test_proposal_detail_card_exposes_full_description_tab():
    source = DETAIL_CARD.read_text()

    assert "type DetailTabKey = 'decision-brief' | 'description' | 'plan-list'" in source
    assert 'value="description"' in source
    assert "t('common.description')" in source
    assert "<MarkdownContent content={proposal.answer} />" in source


def test_proposal_detail_card_keeps_decision_brief_parser():
    source = DETAIL_CARD.read_text()

    assert "parseProposalAnswerSections(proposal.answer)" in source
    assert "proposalAnswer.sections.proposedScope" in source
    assert "proposalAnswer.sections.suggestedSmallFeatureBreakdown" in source
