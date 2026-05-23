from pathlib import Path

DETAIL_CARD = Path('web/src/pages/product-research/components/ProposalDetailCard.tsx')
PARSER = Path('web/src/pages/product-research/proposalAnswerParser.ts')
RESOURCES = Path('web/src/i18n/resources.json')


def read_detail_card() -> str:
    return DETAIL_CARD.read_text()


def test_detail_card_uses_parser_for_structured_answer_tabs():
    source = read_detail_card()

    assert 'parseProposalAnswerSections(proposal.answer)' in source
    assert 'Object.keys(proposalAnswer.sections).length > 0' in source
    assert 'SECTION_TAB_CONFIGS.map(tab =>' in source


def test_decision_brief_is_the_default_section_tab():
    source = read_detail_card()

    assert "useState<ProposalAnswerSectionTab>('decision-brief')" in source
    assert "{ value: 'decision-brief', keys: ['problemOpportunity', 'userBusinessImpact'] }" in source


def test_all_section_tabs_and_full_text_tab_are_rendered():
    source = read_detail_card()

    for value in ('evidence', 'scope', 'risks', 'breakdown', 'open-questions'):
        assert f"value: '{value}'" in source
    assert 'value="full-text"' in source
    assert "productResearch.proposalSectionTabs.full-text" in source


def test_section_tabs_render_present_and_missing_content():
    source = read_detail_card()

    assert '<ProposalSectionBlock' in source
    assert 'content={proposalAnswer.sections[key]}' in source
    assert '<MarkdownContent content={content} />' in source
    assert '<p className="text-sm text-muted-foreground">—</p>' in source


def test_full_text_preserves_complete_answer_from_parser():
    detail_source = read_detail_card()
    parser_source = PARSER.read_text()

    assert 'content={proposalAnswer.fullText}' in detail_source
    assert "const fullText = answer ?? ''" in parser_source
    assert 'return { fullText, sections, status, unrecognizedContent' in parser_source


def test_parse_failure_falls_back_to_legacy_summary_and_answer():
    source = read_detail_card()

    assert 'hasSectionTabs ?' in source
    assert '<MarkdownContent content={proposal.summary} />' in source
    assert '<MarkdownContent content={proposal.answer} />' in source


def test_approve_reject_entries_keep_existing_status_flow():
    source = read_detail_card()

    assert "activeReview?.proposalId === proposal.id && activeReview.status === 'approved'" in source
    assert "activeReview?.proposalId === proposal.id && activeReview.status === 'rejected'" in source
    assert "onReview(proposal.id, 'rejected')" in source
    assert "onReview(proposal.id, 'approved')" in source


def test_section_tab_labels_are_translated():
    source = RESOURCES.read_text()

    assert '"proposalSectionTabs"' in source
    for label in ('Decision Brief', 'Evidence', 'Scope', 'Risks', 'Breakdown', 'Open Questions', 'Full Text'):
        assert label in source
