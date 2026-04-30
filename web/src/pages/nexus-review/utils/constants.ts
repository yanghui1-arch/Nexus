import type { ApiVirtualPullRequestReviewDecision } from '@/api/types';
import type { BundledTheme } from 'shiki';

export const REVIEW_STATUS_META = {
  ready_for_review: {
    label: 'Open',
    badgeVariant: 'secondary' as const,
    badgeClassName: 'border-transparent bg-emerald-600 text-white hover:bg-emerald-600',
  },
  approved: {
    label: 'Approved',
    badgeVariant: 'secondary' as const,
    badgeClassName: 'border-transparent bg-violet-600 text-white hover:bg-violet-600',
  },
  closed: {
    label: 'Closed',
    badgeVariant: 'destructive' as const,
    badgeClassName: 'border-transparent bg-destructive text-destructive-foreground hover:bg-destructive',
  },
};

export const REVIEW_DECISION_LABEL: Record<ApiVirtualPullRequestReviewDecision, string> = {
  approved: 'approved this pull request',
  closed: 'closed this pull request',
  reopened: 'reopened this pull request',
  commented: 'commented',
};

export const TAB_OPTIONS = [
  { id: 'conversation', label: 'Conversation' },
  { id: 'files', label: 'Files Changed' },
] as const;

export const SHIKI_THEME: BundledTheme = 'github-light';
