import type {
  ApiFeatureItemStatus,
  ApiFeatureStatus,
  ApiProductProposalStatus,
} from '@/api/types';
import type {
  ProposalFilter,
  ProposalPlanningDisplayStatus,
  StatusBadgeMeta,
} from './types';

export const POLL_INTERVAL_MS = 15_000;
export const ALL_PROJECTS = '__all_projects__';
export const NO_PROJECT = '__no_project__';
export const PAGE_SIZE = 10;

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
    className: 'border-gray-800 bg-gray-800 text-white hover:bg-gray-800',
  },
  approved: {
    label: 'Approved',
    variant: 'outline',
    className: 'border-gray-700 bg-gray-700 text-white hover:bg-gray-700',
  },
  rejected: {
    label: 'Rejected',
    variant: 'outline',
    className: 'border-gray-200 bg-gray-100 text-gray-600 hover:bg-gray-100',
  },
  planned: {
    label: 'Planned',
    variant: 'outline',
    className: 'border-gray-200 bg-gray-50 text-gray-600 hover:bg-gray-100',
  },
  completed: {
    label: 'Completed',
    variant: 'outline',
    className: 'border-green-200 bg-green-50 text-green-700 hover:bg-green-50',
  },
};

export const PROPOSAL_PLANNING_STATUS_META: Record<
  ProposalPlanningDisplayStatus,
  StatusBadgeMeta
> = {
  queued: {
    label: 'Planning queued',
    variant: 'outline',
    className: 'border-gray-200 bg-gray-50 text-gray-500 hover:bg-gray-50',
  },
  running: {
    label: 'Planning running',
    variant: 'outline',
    className: 'border-gray-800 bg-gray-800 text-white hover:bg-gray-800',
  },
  failed: {
    label: 'Planning failed',
    variant: 'outline',
    className: 'border-red-200 bg-red-50 text-red-700 hover:bg-red-50',
  },
  completed: {
    label: 'Planning completed',
    variant: 'outline',
    className: 'border-green-200 bg-green-50 text-green-700 hover:bg-green-50',
  },
  missing_run: {
    label: 'Planning run missing',
    variant: 'outline',
    className: 'border-red-200 bg-red-50 text-red-700 hover:bg-red-50',
  },
  missing_task: {
    label: 'Planning task missing',
    variant: 'outline',
    className: 'border-red-200 bg-red-50 text-red-700 hover:bg-red-50',
  },
};

export const FEATURE_STATUS_META: Record<ApiFeatureStatus, StatusBadgeMeta> = {
  planned: {
    label: 'Planned',
    variant: 'outline',
    className: 'border-gray-200 bg-gray-50 text-gray-600 hover:bg-gray-100',
  },
  in_progress: {
    label: 'In Progress',
    variant: 'outline',
    className: 'border-gray-800 bg-gray-800 text-white hover:bg-gray-800',
  },
  completed: {
    label: 'Completed',
    variant: 'outline',
    className: 'border-green-200 bg-green-50 text-green-700 hover:bg-green-50',
  },
  closed: {
    label: 'Closed',
    variant: 'outline',
    className: 'border-gray-200 bg-gray-100 text-gray-500 hover:bg-gray-100',
  },
};

export const FEATURE_ITEM_STATUS_META: Record<
  ApiFeatureItemStatus,
  StatusBadgeMeta
> = {
  pending: {
    label: 'Pending',
    variant: 'outline',
    className: 'border-gray-200 bg-gray-50 text-gray-600 hover:bg-gray-100',
  },
  in_progress: {
    label: 'In Progress',
    variant: 'outline',
    className: 'border-gray-800 bg-gray-800 text-white hover:bg-gray-800',
  },
  failed: {
    label: 'Failed',
    variant: 'outline',
    className: 'border-red-200 bg-red-50 text-red-700 hover:bg-red-50',
  },
  completed: {
    label: 'Completed',
    variant: 'outline',
    className: 'border-green-200 bg-green-50 text-green-700 hover:bg-green-50',
  },
  closed: {
    label: 'Closed',
    variant: 'outline',
    className: 'border-gray-200 bg-gray-100 text-gray-500 hover:bg-gray-100',
  },
};
