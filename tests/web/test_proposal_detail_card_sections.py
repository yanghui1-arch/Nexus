from pathlib import Path

PARSER = Path('web/src/pages/product-research/proposalAnswerParser.ts')
DETAIL_CARD = Path('web/src/pages/product-research/components/ProposalDetailCard.tsx')
RESOURCES = Path('web/src/i18n/resources.json')


def test_parser_exports_contract_types_and_function():
    source = PARSER.read_text()

    assert 'export function parseProposalAnswerSections' in source
    assert 'fullText: string' in source
    assert 'unrecognizedContent: string' in source
    assert 'status: ProposalAnswerParseStatus' in source


def test_parser_knows_required_proposal_sections():
    source = PARSER.read_text()

    for key in (
        'problemOpportunity',
        'userBusinessImpact',
        'repositoryEvidence',
        'externalEvidence',
        'proposedScope',
        'nonGoals',
        'risksMitigations',
        'suggestedSmallFeatureBreakdown',
        'openQuestions',
    ):
        assert key in source


def test_parser_only_matches_second_level_markdown_headings():
    source = PARSER.read_text()

    assert 'SECOND_LEVEL_HEADING_PATTERN' in source
    assert '^##(?!#)' in source


def test_detail_card_uses_parsed_sections_for_detail_tabs():
    source = DETAIL_CARD.read_text()

    assert 'parseProposalAnswerSections(proposal.answer)' in source
    for value in (
        'decision-brief',
        'evidence',
        'scope',
        'risks',
        'breakdown',
        'open-questions',
        'full-text',
    ):
        assert f"value: '{value}'" in source or f'value="{value}"' in source
    assert 'content={proposalAnswer.fullText}' in source


def test_detail_card_defaults_to_decision_brief_and_handles_empty_sections():
    source = DETAIL_CARD.read_text()

    assert "useState<ProposalAnswerSectionTab>('decision-brief')" in source
    assert '<ProposalSectionBlock' in source
    assert 'content={proposalAnswer.sections[key]}' in source
    assert '<p className="text-sm text-muted-foreground">—</p>' in source


def test_detail_card_keeps_summary_answer_fallback_when_no_sections_parse():
    source = DETAIL_CARD.read_text()

    assert 'Object.keys(proposalAnswer.sections).length > 0' in source
    assert 'hasSectionTabs ?' in source
    assert '<MarkdownContent content={proposal.summary} />' in source
    assert '<MarkdownContent content={proposal.answer} />' in source


def test_review_actions_still_use_existing_status_flow():
    source = DETAIL_CARD.read_text()

    assert "onReview(proposal.id, 'rejected')" in source
    assert "onReview(proposal.id, 'approved')" in source
    assert "activeReview?.proposalId === proposal.id && activeReview.status === 'approved'" in source
    assert "activeReview?.proposalId === proposal.id && activeReview.status === 'rejected'" in source


def test_section_tab_labels_are_translated():
    source = RESOURCES.read_text()

    assert '"proposalSectionTabs"' in source
    for label in ('Decision Brief', 'Evidence', 'Scope', 'Risks', 'Breakdown', 'Open Questions', 'Full Text'):
        assert label in source
