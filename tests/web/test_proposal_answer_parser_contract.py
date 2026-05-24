from pathlib import Path

PARSER = Path(__file__).resolve().parents[2] / "web/src/pages/product-research/proposalAnswerParser.ts"


def test_parser_exports_contract_types_and_function():
    source = PARSER.read_text()

    assert "export function parseProposalAnswerSections" in source
    assert "fullText: string" in source
    assert "unrecognizedContent: string" in source
    assert "status: ProposalAnswerParseStatus" in source


def test_parser_knows_required_proposal_sections():
    source = PARSER.read_text()

    for key in [
        "problemOpportunity",
        "userBusinessImpact",
        "repositoryEvidence",
        "externalEvidence",
        "proposedScope",
        "nonGoals",
        "risksMitigations",
        "suggestedSmallFeatureBreakdown",
        "openQuestions",
    ]:
        assert key in source


def test_parser_matches_legacy_markdown_headings_and_aliases():
    source = PARSER.read_text()

    assert "ANY_MARKDOWN_HEADING_PATTERN" in source
    assert "overview: 'problemOpportunity'" in source
    assert "evidence: 'repositoryEvidence'" in source
    assert "risks: 'risksMitigations'" in source
    assert "split: 'suggestedSmallFeatureBreakdown'" in source
    assert "概览: 'problemOpportunity'" in source
    assert "范围: 'proposedScope'" in source
    assert "证据: 'repositoryEvidence'" in source
    assert "风险: 'risksMitigations'" in source
    assert "拆分: 'suggestedSmallFeatureBreakdown'" in source


def test_detail_card_falls_back_to_full_content_when_unrecognized():
    source = (PARSER.parent / "components/ProposalDetailCard.tsx").read_text()

    assert "proposalAnswer.status === 'unrecognized'" in source
    assert "proposal.answer" in source
    assert "decisionBriefOriginalContent" in source
