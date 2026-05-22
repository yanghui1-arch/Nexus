from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRODUCT_PAGE = ROOT / "web/src/pages/product-research/index.tsx"
PROPOSAL_FILTERS = ROOT / "web/src/pages/product-research/components/ProposalFilters.tsx"
REVIEW_COUNTS = ROOT / "web/src/pages/product-research/view-model/proposalReviewCounts.ts"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_pending_proposals_become_default_view_when_present() -> None:
    source = _source(PRODUCT_PAGE)

    assert "useState<ProposalFilter>('accepted')" in source
    assert "proposalFilterSelectedRef.current || proposalId" in source
    assert "proposals.some(proposal => proposal.status === 'proposed')" in source
    assert "setProposalFilter('proposed')" in source


def test_review_pending_cta_switches_filter_and_resets_pagination() -> None:
    source = _source(PRODUCT_PAGE)
    handler = source.split("function handleReviewPendingProposals(): void", 1)[1].split(
        "const statusFilteredProposals", 1
    )[0]

    assert "proposalFilterSelectedRef.current = true" in handler
    assert "setProposalFilter('proposed')" in handler
    assert "setProposalPage(1)" in handler
    assert "navigate('/product-research', { replace: true })" in handler


def test_filter_labels_render_counts_from_proposal_data() -> None:
    page_source = _source(PRODUCT_PAGE)
    filters_source = _source(PROPOSAL_FILTERS)
    counts_source = _source(REVIEW_COUNTS)

    assert "const proposalCounts = getProposalReviewCounts(proposals)" in page_source
    assert "proposalCounts={proposalCounts}" in page_source
    assert "count: proposalCounts[option.value]" in filters_source
    assert "status === 'proposed'" in counts_source
    assert "status === 'approved' ||" in counts_source
    assert "status === 'planned' ||" in counts_source
    assert "status === 'completed'" in counts_source
    assert "status === 'rejected'" in counts_source
