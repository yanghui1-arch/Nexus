import type { WorkspaceTaskView } from '@/lib/workspace-task-view';

export const ALL_FAILED_TASK_REPOS = 'all';
export const ALL_FAILED_TASK_AGENTS = 'all';

export type FailedTaskSortOrder = 'newest' | 'oldest';

export type FailedTaskFilters = {
  repo: string;
  agent: string;
  errorKeyword: string;
  sortOrder: FailedTaskSortOrder;
};

export const DEFAULT_FAILED_TASK_FILTERS: FailedTaskFilters = {
  repo: ALL_FAILED_TASK_REPOS,
  agent: ALL_FAILED_TASK_AGENTS,
  errorKeyword: '',
  sortOrder: 'newest',
};

function failureTimestamp(task: WorkspaceTaskView): number {
  return new Date(task.finishedAt ?? task.updatedAt).getTime();
}

function matchesErrorKeyword(task: WorkspaceTaskView, keyword: string): boolean {
  const normalizedKeyword = keyword.trim().toLowerCase();
  if (!normalizedKeyword) {
    return true;
  }

  return (task.error ?? '').toLowerCase().includes(normalizedKeyword);
}

export function deriveFailedTaskRepoOptions(
  tasks: WorkspaceTaskView[],
): string[] {
  return Array.from(
    new Set(
      tasks
        .filter(task => task.status === 'failed' && task.repo)
        .map(task => task.repo as string),
    ),
  ).sort((a, b) => a.localeCompare(b));
}

export function deriveFailedTaskAgentOptions(
  tasks: WorkspaceTaskView[],
): string[] {
  return Array.from(
    new Set(
      tasks
        .filter(task => task.status === 'failed')
        .map(task => task.agentLabel || task.agent),
    ),
  ).sort((a, b) => a.localeCompare(b));
}

export function getVisibleFailedTasks(
  tasks: WorkspaceTaskView[],
  filters: FailedTaskFilters,
): WorkspaceTaskView[] {
  return tasks
    .filter(task => task.status === 'failed')
    .filter(task => filters.repo === ALL_FAILED_TASK_REPOS || task.repo === filters.repo)
    .filter(
      task =>
        filters.agent === ALL_FAILED_TASK_AGENTS ||
        task.agentLabel === filters.agent ||
        task.agent === filters.agent,
    )
    .filter(task => matchesErrorKeyword(task, filters.errorKeyword))
    .sort((a, b) => {
      const diff = failureTimestamp(b) - failureTimestamp(a);
      return filters.sortOrder === 'newest' ? diff : -diff;
    });
}
