from pathlib import Path

PARSER = Path(__file__).resolve().parents[2] / "web/src/pages/product-research/proposalAnswerParser.ts"


def test_parser_exports_contract_types_and_function():
    source = PARSER.read_text()

    assert "export function parseProposalAnswerSections" in source
    assert "export function getProposalReviewReadinessItems" in source
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


def test_review_readiness_uses_existing_parser_section_keys():
    source = PARSER.read_text()

    for section_key in [
        "repositoryEvidence",
        "externalEvidence",
        "nonGoals",
        "risksMitigations",
        "openQuestions",
        "suggestedSmallFeatureBreakdown",
    ]:
        assert f"sectionKey: '{section_key}'" in source

    assert "present: Boolean(parseResult.sections[item.sectionKey]?.trim())" in source
