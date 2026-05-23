from pathlib import Path

CARD = Path(__file__).resolve().parents[2] / "web/src/pages/product-research/components/ProposalDetailCard.tsx"
I18N = Path(__file__).resolve().parents[2] / "web/src/i18n/resources.json"


def test_detail_card_uses_parsed_sections_for_detail_tabs():
    source = CARD.read_text()

    assert "parseProposalAnswerSections(proposal.answer)" in source
    for tab in ["evidence", "scope", "risks", "breakdown", "open-questions", "full-text"]:
        assert f"value: '{tab}'" in source
    assert "content: fullText" in source


def test_detail_card_keeps_summary_answer_fallback_when_no_sections_parse():
    source = CARD.read_text()

    assert "Object.keys(proposalAnswer.sections).length > 0" in source
    assert "hasSectionTabs ?" in source
    assert "<MarkdownContent content={proposal.summary} />" in source
    assert "<MarkdownContent content={proposal.answer} />" in source


def test_section_tab_labels_are_translated():
    source = I18N.read_text()

    assert '"proposalSectionTabs"' in source
    for label in ["Evidence", "Scope", "Risks", "Breakdown", "Open Questions", "Full Text"]:
        assert label in source
