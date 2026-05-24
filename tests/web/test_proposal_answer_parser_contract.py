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


def test_parser_only_matches_second_level_markdown_headings():
    source = PARSER.read_text()

    assert "SECOND_LEVEL_HEADING_PATTERN" in source
    assert "^##(?!#)" in source


def test_parser_preserves_legacy_answer_fallback_contract():
    source = PARSER.read_text()

    assert "fullText = answer ?? ''" in source
    assert "status = recognizedCount === 0" in source
    assert "? 'unrecognized'" in source
    assert "unrecognizedParts.push" in source


def test_parser_supports_markdown_parse_failure_fallback_contract():
    source = PARSER.read_text()

    assert "fullText" in source
    assert "unrecognizedContent" in source
    assert "status: 'empty'" in source
    assert "status }" in source
