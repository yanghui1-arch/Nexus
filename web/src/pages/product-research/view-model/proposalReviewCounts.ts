import type { ApiProductProposal } from '@/api/types';
import type { ProposalFilter } from '../types';

export type ProposalReviewCounts = Record<ProposalFilter, number>;

export function getProposalReviewCounts(
  proposals: ApiProductProposal[],
): ProposalReviewCounts {
  return proposals.reduce<ProposalReviewCounts>(
    (counts, proposal) => {
      counts.all += 1;

      if (proposal.status === 'proposed') {
        counts.proposed += 1;
      } else if (proposal.status === 'rejected') {
        counts.rejected += 1;
      } else {
        counts.accepted += 1;
      }

      return counts;
    },
    { all: 0, proposed: 0, accepted: 0, rejected: 0 },
  );
}
