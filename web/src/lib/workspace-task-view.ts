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

export type WorkspaceAgentOption = {
  id: string;
  label: string;
  subtitle: string;
  agent: ApiAgentInstance['agent'];
  workspaceStatus: NonNullable<ApiAgentInstance['workspace']>['status'] | null;
  workspaceRepo: string | null;
  workspaceProject: string | null;
};

export type WorkspaceTaskView = {
  id: string;
  question: string;
  category: ApiTask['category'];
  repo: string | null;
  project: string | null;
  externalIssueUrl: string | null;
  externalPullRequestUrl: string | null;
  status: ApiTask['status'];
  result: string | null;
  error: string | null;
  totalTokens: number | null;
  toolCallCount: number | null;
  lastEventAt: string | null;
  lastCheckpointAt: string | null;
  latestErrorRetrySummary: string | null;
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

export type BadgeTone = 'default' | 'secondary' | 'destructive' | 'outline';

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

const TRACKING_PRIORITY: Record<ApiTaskStatus, number> = {
  running: 0,
  waiting_for_review: 1,
  queued: 2,
  merged: 3,
  closed: 4,
  failed: 5,
};

function shortId(id: string): string {
  return id.slice(0, 8);
}

export function formatAgentLabel(agent: string, id: string): string {
  return `${agent} · ${shortId(id)}`;
}

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

export function sortTaskViewsByNewest(
  tasks: WorkspaceTaskView[],
): WorkspaceTaskView[] {
  return [...tasks].sort(
    (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime(),
  );
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
    workspaceProject: instance.workspace?.project ?? null,
  };
}

export function toWorkspaceTaskView(
  task: ApiTask,
  agentOptionsById: Map<string, WorkspaceAgentOption>,
): WorkspaceTaskView {
  return {
    id: task.id,
    question: task.question,
    category: task.category,
    repo: task.repo,
    project: task.project,
    externalIssueUrl: task.external_issue_url,
    externalPullRequestUrl: task.external_pull_request_url,
    status: task.status,
    result: task.result,
    error: task.error,
    totalTokens: task.total_tokens ?? null,
    toolCallCount: task.tool_call_count ?? null,
    lastEventAt: task.last_event_at ?? null,
    lastCheckpointAt: task.last_checkpoint_at ?? null,
    latestErrorRetrySummary: task.latest_error_retry_summary ?? null,
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
