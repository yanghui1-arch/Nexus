import type { ApiFeature, ApiProductProposal, ApiProductProposalStatus } from '@/api/types';

export type ProductResearchSnapshot = {
  proposals: ApiProductProposal[];
  features: ApiFeature[];
};

export type LoadOrigin = 'initial' | 'poll' | 'mutation';
export type ProposalFilter = 'all' | 'proposed' | 'accepted' | 'rejected';
export type ReviewActionStatus = Extract<
  ApiProductProposalStatus,
  'approved' | 'rejected'
>;
export type ReviewActionState = {
  proposalId: string;
  status: ReviewActionStatus;
} | null;
export type BadgeVariant = 'default' | 'secondary' | 'destructive' | 'outline';
export type StatusBadgeMeta = {
  label: string;
  variant: BadgeVariant;
  className?: string;
};
export type ProjectOption = {
  value: string;
  label: string;
};
