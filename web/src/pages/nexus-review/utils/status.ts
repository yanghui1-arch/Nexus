import {
  AlertCircle,
  Archive,
  CheckCircle2,
  Clock3,
  GitBranch,
  Loader2,
  type LucideIcon,
} from 'lucide-react';
import type { ApiTaskStatus } from '@/api/types';

type BadgeTone = 'default' | 'secondary' | 'destructive' | 'outline';

export const TASK_STATUS_META: Record<
  ApiTaskStatus,
  {
    label: string;
    icon: LucideIcon;
    badgeVariant: BadgeTone;
    badgeClassName?: string;
  }
> = {
  queued: {
    label: 'Queued',
    icon: Clock3,
    badgeVariant: 'secondary',
  },
  running: {
    label: 'Running',
    icon: Loader2,
    badgeVariant: 'default',
  },
  waiting_for_review: {
    label: 'Waiting for Review',
    icon: GitBranch,
    badgeVariant: 'secondary',
    badgeClassName: 'border-transparent bg-emerald-600 text-white hover:bg-emerald-600',
  },
  waiting_for_merge: {
    label: 'Waiting for Merge',
    icon: GitBranch,
    badgeVariant: 'default',
  },
  merged: {
    label: 'Merged',
    icon: CheckCircle2,
    badgeVariant: 'secondary',
    badgeClassName: 'border-transparent bg-violet-600 text-white hover:bg-violet-600',
  },
  closed: {
    label: 'Closed',
    icon: Archive,
    badgeVariant: 'outline',
  },
  failed: {
    label: 'Failed',
    icon: AlertCircle,
    badgeVariant: 'destructive',
  },
};

export function timeAgo(iso: string | null | undefined): string {
  if (!iso) {
    return '-';
  }

  const seconds = Math.max(
    1,
    Math.round((Date.now() - new Date(iso).getTime()) / 1000),
  );
  if (seconds < 60) {
    return `${seconds}s ago`;
  }
  if (seconds < 3600) {
    return `${Math.round(seconds / 60)}m ago`;
  }
  if (seconds < 86_400) {
    return `${Math.round(seconds / 3600)}h ago`;
  }
  return `${Math.round(seconds / 86_400)}d ago`;
}
