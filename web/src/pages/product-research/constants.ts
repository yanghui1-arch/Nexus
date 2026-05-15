import type {
  ApiFeatureItemStatus,
  ApiFeatureStatus,
  ApiProductProposalStatus,
} from '@/api/types';
import type { ProposalFilter, StatusBadgeMeta } from './types';

export const POLL_INTERVAL_MS = 15_000;
export const ALL_PROJECTS = '__all_projects__';
export const NO_PROJECT = '__no_project__';
export const PAGE_SIZE = 10;

export const TABLE_CARD_CLASS =
  'overflow-hidden rounded-[28px] border border-black/10 bg-white shadow-[0_1px_0_rgba(0,0,0,0.04)]';
export const TABLE_HEADER_ROW_CLASS =
  'border-black/10 bg-black/[0.03] hover:bg-black/[0.03]';
export const TABLE_HEAD_CLASS =
  'h-12 text-[11px] font-semibold uppercase tracking-[0.16em] text-black/55';
export const TABLE_BODY_CLASS =
  '[&_tr]:border-black/10 [&_tr:nth-child(even)]:bg-black/[0.015]';
export const TABLE_ROW_CLASS =
  'cursor-pointer border-black/10 hover:bg-black/[0.04] focus-visible:bg-black/[0.04]';

export const PROPOSAL_FILTER_OPTIONS: Array<{
  value: ProposalFilter;
  label: string;
}> = [
  { value: 'all', label: 'All' },
  { value: 'proposed', label: 'Pending' },
  { value: 'accepted', label: 'Accepted' },
  { value: 'rejected', label: 'Rejected' },
];

export const PROPOSAL_STATUS_META: Record<
  ApiProductProposalStatus,
  StatusBadgeMeta
> = {
  proposed: {
    label: 'Pending Review',
    variant: 'outline',
    className: 'border-black bg-black text-white hover:bg-black',
  },
  approved: {
    label: 'Approved',
    variant: 'outline',
    className: 'border-black/80 bg-black/80 text-white hover:bg-black/80',
  },
  rejected: {
    label: 'Rejected',
    variant: 'outline',
    className: 'border-black/12 bg-black/[0.12] text-black hover:bg-black/[0.12]',
  },
  planned: {
    label: 'Planned',
    variant: 'outline',
    className: 'border-black/10 bg-black/[0.05] text-black hover:bg-black/[0.08]',
  },
};

export const FEATURE_STATUS_META: Record<ApiFeatureStatus, StatusBadgeMeta> = {
  planned: {
    label: 'Planned',
    variant: 'outline',
    className: 'border-black/10 bg-black/[0.05] text-black hover:bg-black/[0.08]',
  },
  in_progress: {
    label: 'In Progress',
    variant: 'outline',
    className: 'border-black bg-black text-white hover:bg-black',
  },
  completed: {
    label: 'Completed',
    variant: 'outline',
    className: 'border-black/18 bg-white text-black hover:bg-black/[0.03]',
  },
  closed: {
    label: 'Closed',
    variant: 'outline',
    className: 'border-black/12 bg-black/[0.12] text-black hover:bg-black/[0.12]',
  },
};

export const FEATURE_ITEM_STATUS_META: Record<
  ApiFeatureItemStatus,
  StatusBadgeMeta
> = {
  pending: {
    label: 'Pending',
    variant: 'outline',
    className: 'border-black/10 bg-black/[0.05] text-black hover:bg-black/[0.08]',
  },
  in_progress: {
    label: 'In Progress',
    variant: 'outline',
    className: 'border-black bg-black text-white hover:bg-black',
  },
  completed: {
    label: 'Completed',
    variant: 'outline',
    className: 'border-black/18 bg-white text-black hover:bg-black/[0.03]',
  },
  closed: {
    label: 'Closed',
    variant: 'outline',
    className: 'border-black/12 bg-black/[0.12] text-black hover:bg-black/[0.12]',
  },
};
