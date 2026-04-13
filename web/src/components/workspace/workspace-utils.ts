import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  Loader2,
  type LucideIcon,
} from 'lucide-react';
import type {
  WorkspaceStatus,
  WorkspaceTask,
  WorkspaceUrgency,
} from '@/data/workspaceMockData';

export type BadgeTone = 'default' | 'secondary' | 'destructive' | 'outline';

export const STATUS_ORDER: WorkspaceStatus[] = [
  'queued',
  'in_progress',
  'blocked',
  'done',
];

export const STATUS_META: Record<
  WorkspaceStatus,
  { label: string; icon: LucideIcon; badgeVariant: BadgeTone }
> = {
  queued: {
    label: 'Queued',
    icon: Clock3,
    badgeVariant: 'secondary',
  },
  in_progress: {
    label: 'In Progress',
    icon: Loader2,
    badgeVariant: 'default',
  },
  blocked: {
    label: 'Blocked',
    icon: AlertTriangle,
    badgeVariant: 'destructive',
  },
  done: {
    label: 'Done',
    icon: CheckCircle2,
    badgeVariant: 'outline',
  },
};

export const URGENCY_META: Record<
  WorkspaceUrgency,
  { label: string; rank: number; badgeVariant: BadgeTone }
> = {
  critical: {
    label: 'Critical',
    rank: 3,
    badgeVariant: 'destructive',
  },
  high: {
    label: 'High',
    rank: 2,
    badgeVariant: 'default',
  },
  normal: {
    label: 'Normal',
    rank: 1,
    badgeVariant: 'secondary',
  },
};

export function timeAgo(iso: string): string {
  const seconds = Math.max(
    1,
    Math.round((Date.now() - new Date(iso).getTime()) / 1000),
  );
  if (seconds < 60) return `${seconds}s ago`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m ago`;
  if (seconds < 86_400) return `${Math.round(seconds / 3600)}h ago`;
  return `${Math.round(seconds / 86_400)}d ago`;
}

export function sortTasksForBoard(tasks: WorkspaceTask[]): WorkspaceTask[] {
  return [...tasks].sort((a, b) => {
    const urgencyGap = URGENCY_META[b.urgency].rank - URGENCY_META[a.urgency].rank;
    if (urgencyGap !== 0) return urgencyGap;
    return new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime();
  });
}
