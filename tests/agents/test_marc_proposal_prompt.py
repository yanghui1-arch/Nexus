from src.agents.marc.system_prompt import MARC_SYSTEM_PROMPT
from src.tools.product import CreateProductProposal


def test_marc_proposal_prompt_is_decision_oriented_not_fixed_template():
    assert "decision-oriented answer" in MARC_SYSTEM_PROMPT
    assert "not a rigid template" in MARC_SYSTEM_PROMPT
    assert "frontend can extract sections" in MARC_SYSTEM_PROMPT
    assert "must use these markdown sections in this order" not in MARC_SYSTEM_PROMPT
    assert "Do not omit a section" not in MARC_SYSTEM_PROMPT


def test_marc_proposal_prompt_keeps_core_review_constraints():
    assert "Match the title language" in MARC_SYSTEM_PROMPT
    assert "1-3 sentences" in MARC_SYSTEM_PROMPT
    assert "at least 2 repository-level evidence points" in MARC_SYSTEM_PROMPT
    assert "Include Open Questions only when" in MARC_SYSTEM_PROMPT


def test_marc_proposal_prompt_preserves_frontend_parseable_headings():
    for heading in [
        "## Problem / Opportunity",
        "## User & Business Impact",
        "## Repository Evidence",
        "## Proposed Scope",
        "## Non-goals",
        "## Risks & Mitigations",
        "## Suggested Small-feature Breakdown",
        "## Open Questions",
    ]:
        assert heading in MARC_SYSTEM_PROMPT


def test_marc_proposal_prompt_matches_decision_brief_rendering_contract():
    assert "three decision brief blocks" in MARC_SYSTEM_PROMPT
    assert "决策方向 / Decision Direction" in MARC_SYSTEM_PROMPT
    assert "smallest implementation scope recommended for approval" in MARC_SYSTEM_PROMPT
    assert "实施路径 / Implementation Approach" in MARC_SYSTEM_PROMPT
    assert "预期收益 / Expected Value" in MARC_SYSTEM_PROMPT


def test_create_proposal_schema_describes_compact_decision_brief():
    fields = CreateProductProposal.model_fields

    assert "user's or task's language" in fields["title"].description
    assert "1-3 sentence summary" in fields["summary"].description
    assert "frontend-parseable decision brief" in fields["answer"].description
    assert "three summary blocks" in fields["answer"].description
    assert "open questions only if real ones exist" in fields["answer"].description
