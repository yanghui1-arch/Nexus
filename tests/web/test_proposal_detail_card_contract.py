from pathlib import Path

CARD = Path(__file__).resolve().parents[2] / "web/src/pages/product-research/components/ProposalDetailCard.tsx"


def test_proposal_detail_card_defaults_to_overview_decision_brief():
    source = CARD.read_text()

    assert "useState<DetailTabKey>('decision-brief')" in source
    assert 'value={visibleTab}' in source
    assert "<TabsContent value=\"decision-brief\"" in source


def test_proposal_detail_card_switches_between_brief_and_plan_panels():
    source = CARD.read_text()

    assert "onValueChange={value =>" in source
    assert "setActiveTab(value as DetailTabKey)" in source
    assert "<TabsTrigger value=\"plan-list\" disabled={!canOpenPlanList}>" in source
    assert "<TabsContent value=\"plan-list\">" in source
    assert "<ProposalPlanList features={relatedFeatures} />" in source


def test_proposal_detail_card_falls_back_to_legacy_answer_without_open_questions():
    source = CARD.read_text()

    assert "parseProposalAnswerSections(proposal.answer)" in source
    assert "proposal.summary" in source
    assert "proposalAnswer.sections.proposedScope" in source
    assert "proposalAnswer.sections.problemOpportunity" in source
    assert "openQuestions" not in source
