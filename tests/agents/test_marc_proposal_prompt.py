from src.agents.marc.system_prompt import MARC_SYSTEM_PROMPT
from src.tools.product import CreateProductProposal


def test_marc_proposal_prompt_is_decision_oriented_not_fixed_template():
    assert "decision-oriented answer" in MARC_SYSTEM_PROMPT
    assert "not a rigid template" in MARC_SYSTEM_PROMPT
    assert "Do not force every proposal into the same fixed markdown section list" in MARC_SYSTEM_PROMPT
    assert "must use these markdown sections in this order" not in MARC_SYSTEM_PROMPT
    assert "Do not omit a section" not in MARC_SYSTEM_PROMPT


def test_marc_proposal_prompt_keeps_core_review_constraints():
    assert "Match the title language" in MARC_SYSTEM_PROMPT
    assert "1-3 sentences" in MARC_SYSTEM_PROMPT
    assert "at least 2 repository-level evidence points" in MARC_SYSTEM_PROMPT
    assert "Include Open Questions only when" in MARC_SYSTEM_PROMPT


def test_create_proposal_schema_describes_compact_decision_brief():
    fields = CreateProductProposal.model_fields

    assert "user's or task's language" in fields["title"].description
    assert "1-3 sentence summary" in fields["summary"].description
    assert "Concise decision brief" in fields["answer"].description
    assert "open questions only if real ones exist" in fields["answer"].description
