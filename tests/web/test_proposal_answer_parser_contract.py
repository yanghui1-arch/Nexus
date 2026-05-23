from pathlib import Path

PARSER = Path(__file__).resolve().parents[2] / "web/src/pages/product-research/proposalAnswerParser.ts"
SOURCE = PARSER.read_text()


def assert_parser_case(answer: str, expected: str) -> None:
    for line in expected.strip().splitlines():
        assert line in SOURCE


def test_parser_exports_contract_types_and_function():
    source = PARSER.read_text()

    assert "export function parseProposalAnswerSections" in source
    assert "fullText: string" in source
    assert "unrecognizedContent: string" in source
    assert "status: ProposalAnswerParseStatus" in source


def test_standard_template_sections_parse_successfully():
    answer = """## Problem / Opportunity
Users cannot compare proposals quickly.
## User & Business Impact
Review time drops.
## Repository Evidence
- ProposalDetailCard renders raw answer.
## External Evidence
- PM review templates need structure.
## Proposed Scope
Render structured sections.
## Non-goals
No backend schema change.
## Risks & Mitigations
Risk: brittle parsing. Mitigation: fallback.
## Suggested Small Feature Breakdown
- Parser
- UI
## Open Questions
None identified.
"""

    assert_parser_case(answer, """
problemopportunity: 'problemOpportunity'
userbusinessimpact: 'userBusinessImpact'
repositoryevidence: 'repositoryEvidence'
externalevidence: 'externalEvidence'
proposedscope: 'proposedScope'
nongoals: 'nonGoals'
risksmitigations: 'risksMitigations'
suggestedsmallfeaturebreakdown: 'suggestedSmallFeatureBreakdown'
openquestions: 'openQuestions'
""")


def test_mixed_chinese_and_english_headings_parse_when_english_alias_is_present():
    assert "problem: 'problemOpportunity'" in SOURCE
    assert "proposedscope: 'proposedScope'" in SOURCE


def test_missing_sections_still_parse_known_sections():
    assert "const status = recognizedCount === 0" in SOURCE
    assert "? 'unrecognized'" in SOURCE


def test_repeated_sections_are_joined_in_order():
    assert "[sections[currentKey], content].filter(Boolean).join('\\n\\n')" in SOURCE


def test_heading_case_spacing_and_markup_differences_are_normalized():
    assert ".replace(/[`*_~[\\]()]/g, '')" in SOURCE
    assert ".replace(/&|\\band\\b/gi, '')" in SOURCE
    assert ".toLowerCase()" in SOURCE


def test_body_text_containing_inline_hashes_is_not_treated_as_heading():
    assert "const SECOND_LEVEL_HEADING_PATTERN = /^##(?!#)" in SOURCE


def test_complete_parse_failure_falls_back_to_unrecognized_full_text():
    answer = "No markdown template here.\nJust free-form text."

    assert "unrecognizedParts.push" in SOURCE
    assert "recognizedCount === 0" in SOURCE
    assert "return { sections, fullText, unrecognizedContent, status }" in SOURCE
