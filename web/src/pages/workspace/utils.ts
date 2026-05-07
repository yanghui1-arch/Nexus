import {
  AlertCircle,
  Archive,
  CheckCircle2,
  Clock3,
  GitBranch,
  Loader2,
  type LucideIcon,
} from 'lucide-react';
import type { ApiAgentInstance, ApiTask, ApiTaskStatus } from '@/api/types';

// ── Types ──────────────────────────────────────────────────────────────────

export type WorkspaceComposerValues = {
  question: string;
  repo: string;
  project: string;
  externalIssueUrl: string;
  agentInstanceId: string;
};

export type WorkspaceAgentOption = {
  id: string;
  label: string;
  subtitle: string;
  agent: ApiAgentInstance['agent'];
  workspaceStatus: NonNullable<ApiAgentInstance['workspace']>['status'] | null;
  workspaceRepo: string | null;
};

export type WorkspaceTaskView = {
  id: string;
  question: string;
  repo: string | null;
  project: string | null;
  status: ApiTask['status'];
  result: string | null;
  error: string | null;
  createdAt: string;
  updatedAt: string;
  startedAt: string | null;
  finishedAt: string | null;
  agent: ApiTask['agent'];
  agentInstanceId: string;
  agentLabel: string;
};

export type WorkspaceConsultMessageView = {
  id: string;
  role: 'user' | 'agent';
  text: string;
  time: string;
  status: ApiTask['status'] | null;
};

// ── Constants ──────────────────────────────────────────────────────────────

export type BadgeTone = 'default' | 'secondary' | 'destructive' | 'outline';

export const TASK_BOARD_STATUS_ORDER: ApiTaskStatus[] = [
  'queued',
  'running',
  'waiting_for_review',
  'merged',
];

export const STATUS_META: Record<
  ApiTaskStatus,
  { label: string; icon: LucideIcon; badgeVariant: BadgeTone }
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
  },
  waiting_for_merge: {
    label: 'Waiting for Merge',
    icon: GitBranch,
    badgeVariant: 'default',
  },
  merged: {
    label: 'Merged',
    icon: CheckCircle2,
    badgeVariant: 'outline',
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

// ── Helpers ────────────────────────────────────────────────────────────────

export function timeAgo(iso: string | null | undefined): string {
  if (!iso) {
    return '-';
  }

  const seconds = Math.max(
    1,
    Math.round((Date.now() - new Date(iso).getTime()) / 1000),
  );
  if (seconds < 60) return `${seconds}s ago`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m ago`;
  if (seconds < 86_400) return `${Math.round(seconds / 3600)}h ago`;
  return `${Math.round(seconds / 86_400)}d ago`;
}

export function sortTasksForBoard(tasks: WorkspaceTaskView[]): WorkspaceTaskView[] {
  return [...tasks].sort(
    (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime(),
  );
}

// ── View Models ────────────────────────────────────────────────────────────

const TRACKING_PRIORITY: Record<ApiTaskStatus, number> = {
  running: 0,
  waiting_for_review: 1,
  waiting_for_merge: 2,
  queued: 3,
  merged: 4,
  closed: 5,
  failed: 6,
};

function shortId(id: string): string {
  return id.slice(0, 8);
}

export function formatAgentLabel(agent: string, id: string): string {
  return `${agent} · ${shortId(id)}`;
}

export function toWorkspaceAgentOption(
  instance: ApiAgentInstance,
): WorkspaceAgentOption {
  return {
    id: instance.id,
    label: instance.display_name ?? formatAgentLabel(instance.agent, instance.id),
    subtitle: instance.client_id,
    agent: instance.agent,
    workspaceStatus: instance.workspace?.status ?? null,
    workspaceRepo: instance.workspace?.github_repo ?? null,
  };
}

export function toWorkspaceTaskView(
  task: ApiTask,
  agentOptionsById: Map<string, WorkspaceAgentOption>,
): WorkspaceTaskView {
  return {
    id: task.id,
    question: task.question,
    repo: task.repo,
    project: task.project,
    status: task.status,
    result: task.result,
    error: task.error,
    createdAt: task.created_at,
    updatedAt: task.updated_at,
    startedAt: task.started_at,
    finishedAt: task.finished_at,
    agent: task.agent,
    agentInstanceId: task.agent_instance_id,
    agentLabel:
      agentOptionsById.get(task.agent_instance_id)?.label ??
      formatAgentLabel(task.agent, task.agent_instance_id),
  };
}

export function deriveRepoFilters(tasks: WorkspaceTaskView[]): string[] {
  const seen = new Set<string>();
  const repos: string[] = [];

  for (const task of tasks) {
    if (!task.repo || seen.has(task.repo)) {
      continue;
    }
    seen.add(task.repo);
    repos.push(task.repo);
  }

  return repos;
}

export function selectTrackingTask(
  tasks: WorkspaceTaskView[],
): WorkspaceTaskView | undefined {
  if (tasks.length === 0) {
    return undefined;
  }

  return [...tasks].sort((a, b) => {
    const priorityGap = TRACKING_PRIORITY[a.status] - TRACKING_PRIORITY[b.status];
    if (priorityGap !== 0) {
      return priorityGap;
    }
    return new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime();
  })[0];
}
