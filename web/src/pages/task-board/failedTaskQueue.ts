import type { WorkspaceTaskView } from '@/lib/workspace-task-view';

export type FailedTaskSortOrder = 'newest' | 'oldest';

export type FailedTaskQueueFilters = {
  repo: string;
  agent: string;
  keyword: string;
  sortOrder: FailedTaskSortOrder;
};

export const FAILED_TASK_QUEUE_ALL_REPOSITORIES = 'All repositories';
export const FAILED_TASK_QUEUE_ALL_AGENTS = 'All agents';

export const DEFAULT_FAILED_TASK_QUEUE_FILTERS: FailedTaskQueueFilters = {
  repo: FAILED_TASK_QUEUE_ALL_REPOSITORIES,
  agent: FAILED_TASK_QUEUE_ALL_AGENTS,
  keyword: '',
  sortOrder: 'newest',
};

export function getFailedTaskQueueTasks(
  tasks: WorkspaceTaskView[],
  filters: FailedTaskQueueFilters = DEFAULT_FAILED_TASK_QUEUE_FILTERS,
): WorkspaceTaskView[] {
  const normalizedKeyword = filters.keyword.trim().toLowerCase();

  return tasks
    .filter(task => task.category === 'coding' && task.status === 'failed')
    .filter(task =>
      filters.repo === FAILED_TASK_QUEUE_ALL_REPOSITORIES
        ? true
        : task.repo === filters.repo,
    )
    .filter(task =>
      filters.agent === FAILED_TASK_QUEUE_ALL_AGENTS
        ? true
        : task.agentLabel === filters.agent || task.agent === filters.agent,
    )
    .filter(task => {
      if (!normalizedKeyword) {
        return true;
      }

      return [task.question, task.repo ?? '', task.project ?? '', task.error ?? '']
        .join(' ')
        .toLowerCase()
        .includes(normalizedKeyword);
    })
    .sort((left, right) => {
      const getFailureTimestamp = (task: WorkspaceTaskView) => {
        const finishedAt = task.finishedAt;
        return finishedAt ?? task.updatedAt;
      };
      const compared = getFailureTimestamp(right).localeCompare(
        getFailureTimestamp(left),
      );
      return filters.sortOrder === 'newest' ? compared : -compared;
    });
}

export function deriveFailedTaskQueueRepoOptions(
  tasks: WorkspaceTaskView[],
): string[] {
  const repos = new Set<string>();

  tasks.forEach(task => {
    if (task.category === 'coding' && task.status === 'failed' && task.repo) {
      repos.add(task.repo);
    }
  });

  return [FAILED_TASK_QUEUE_ALL_REPOSITORIES, ...Array.from(repos).sort()];
}

export function deriveFailedTaskQueueAgentOptions(
  tasks: WorkspaceTaskView[],
): string[] {
  const agents = new Set<string>();

  tasks.forEach(task => {
    if (task.category === 'coding' && task.status === 'failed') {
      agents.add(task.agentLabel);
    }
  });

  return [FAILED_TASK_QUEUE_ALL_AGENTS, ...Array.from(agents).sort()];
}
