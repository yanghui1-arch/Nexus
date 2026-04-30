import {
  AlertCircle,
  CheckCircle2,
  Clock3,
  Loader2,
  type LucideIcon,
} from 'lucide-react';
import type { AgentTask, Project, TaskStatus } from '@/types/agent';

export type BadgeTone = 'default' | 'secondary' | 'destructive' | 'outline';

export type FilterTab =
  | 'all'
  | 'running'
  | 'waiting_for_review'
  | 'merged'
  | 'closed'
  | 'fail';

export const FILTERS: Array<{ key: FilterTab; label: string }> = [
  { key: 'all', label: 'All' },
  { key: 'running', label: 'Running' },
  { key: 'waiting_for_review', label: 'Review' },
  { key: 'merged', label: 'Merged' },
  { key: 'closed', label: 'Closed' },
  { key: 'fail', label: 'Failed' },
];

export const STATUS_META: Record<
  TaskStatus,
  { label: string; icon: LucideIcon; badgeVariant: BadgeTone }
> = {
  running: {
    label: 'Running',
    icon: Loader2,
    badgeVariant: 'default',
  },
  waiting_for_review: {
    label: 'Waiting for Review',
    icon: Clock3,
    badgeVariant: 'secondary',
  },
  merged: {
    label: 'Merged',
    icon: CheckCircle2,
    badgeVariant: 'outline',
  },
  closed: {
    label: 'Closed',
    icon: Clock3,
    badgeVariant: 'outline',
  },
  failed: {
    label: 'Failed',
    icon: AlertCircle,
    badgeVariant: 'destructive',
  },
  error: {
    label: 'Error',
    icon: AlertCircle,
    badgeVariant: 'destructive',
  },
};

export function countTasks(tasks: AgentTask[]) {
  return {
    running: tasks.filter(task => task.status === 'running').length,
    waiting_for_review: tasks.filter(task => task.status === 'waiting_for_review').length,
    merged: tasks.filter(task => task.status === 'merged').length,
    closed: tasks.filter(task => task.status === 'closed').length,
    fail: tasks.filter(
      task => task.status === 'failed' || task.status === 'error',
    ).length,
  };
}

export function filterTasks(tasks: AgentTask[], filter: FilterTab): AgentTask[] {
  if (filter === 'all') return tasks;
  if (filter === 'fail') {
    return tasks.filter(
      task => task.status === 'failed' || task.status === 'error',
    );
  }
  return tasks.filter(task => task.status === filter);
}

export function timeAgo(iso?: string): string {
  if (!iso) return '-';

  const seconds = Math.max(
    1,
    Math.round((Date.now() - new Date(iso).getTime()) / 1000),
  );

  if (seconds < 60) return `${seconds}s ago`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m ago`;
  if (seconds < 86_400) return `${Math.round(seconds / 3600)}h ago`;
  return `${Math.round(seconds / 86_400)}d ago`;
}

export function formatDuration(seconds?: number): string {
  if (!seconds) return '-';
  if (seconds < 60) return `${seconds}s`;

  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;

  if (remainder === 0) return `${minutes}m`;
  return `${minutes}m ${remainder}s`;
}

export function projectRunningCount(project: Project): number {
  return project.agents.filter(agent => agent.status === 'busy').length;
}
