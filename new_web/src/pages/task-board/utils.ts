import type { ApiTaskCategory, ApiTaskStatus } from '@/api/types';
import type { ApiAgentKind } from '@/api/types';
import {
  sortTaskViewsByNewest,
  type WorkspaceTaskView,
} from '@/lib/workspace-task-view';

export const DEFAULT_TASK_BOARD_REPO = 'yanghui1-arch/Nexus';

export const TASK_BOARD_STATUS_ORDER = [
  'queued',
  'running',
  'waiting_for_review',
  'failed',
  'merged',
] as const satisfies readonly ApiTaskStatus[];

export type TaskBoardStatus = (typeof TASK_BOARD_STATUS_ORDER)[number];

export const TASK_BOARD_TABS = [
  'allTasks',
  'myTasks',
  'backend',
  'frontend',
  'devops',
] as const;

export type TaskBoardTab = (typeof TASK_BOARD_TABS)[number];
export type TaskBoardStatusFilter = 'all' | TaskBoardStatus;
export type TaskBoardAgentFilter = 'all' | ApiAgentKind;

const TASK_BOARD_CATEGORY = 'coding' satisfies ApiTaskCategory;

const TAB_KEYWORDS: Partial<Record<TaskBoardTab, string[]>> = {
  backend: ['backend', 'api', 'server', 'service', 'database', 'spring'],
  frontend: ['frontend', 'ui', 'react', 'page', 'component', 'view'],
  devops: ['devops', 'deploy', 'deployment', 'docker', 'ci', 'infra', 'pipeline'],
};

const TAB_AGENT_FALLBACK: Partial<Record<TaskBoardTab, ApiAgentKind[]>> = {
  backend: ['tela', 'jules'],
  frontend: ['sophie'],
};

export function isTaskBoardTask(task: WorkspaceTaskView): boolean {
  return task.category === TASK_BOARD_CATEGORY;
}

export function isTaskBoardStatus(
  status: ApiTaskStatus,
): status is TaskBoardStatus {
  return TASK_BOARD_STATUS_ORDER.includes(status as TaskBoardStatus);
}

export function deriveTaskBoardRepoOptions(
  tasks: WorkspaceTaskView[],
): string[] {
  const seen = new Set<string>();
  const repoOptions = [DEFAULT_TASK_BOARD_REPO];

  for (const task of tasks) {
    if (
      !isTaskBoardTask(task) ||
      !task.repo ||
      seen.has(task.repo) ||
      task.repo === DEFAULT_TASK_BOARD_REPO
    ) {
      continue;
    }

    seen.add(task.repo);
    repoOptions.push(task.repo);
  }

  return repoOptions;
}

export function getVisibleTaskBoardTasks(
  tasks: WorkspaceTaskView[],
  repoFilter: string,
): WorkspaceTaskView[] {
  return sortTaskViewsByNewest(
    tasks.filter(task => isTaskBoardTask(task) && task.repo === repoFilter),
  ).filter(task => isTaskBoardStatus(task.status));
}

export function groupTaskBoardTasks(
  tasks: WorkspaceTaskView[],
): Record<TaskBoardStatus, WorkspaceTaskView[]> {
  const groups = Object.fromEntries(
    TASK_BOARD_STATUS_ORDER.map(status => [status, [] as WorkspaceTaskView[]]),
  ) as Record<TaskBoardStatus, WorkspaceTaskView[]>;

  tasks.forEach(task => {
    if (isTaskBoardTask(task) && isTaskBoardStatus(task.status)) {
      groups[task.status].push(task);
    }
  });

  return groups;
}

function taskMatchesTab(task: WorkspaceTaskView, tab: TaskBoardTab): boolean {
  if (tab === 'allTasks') {
    return true;
  }

  if (tab === 'myTasks') {
    return task.status === 'waiting_for_review' || task.status === 'failed';
  }

  const searchableText = [
    task.project,
    task.repo,
    task.title,
    task.question,
    task.agentLabel,
  ]
    .filter(Boolean)
    .join(' ')
    .toLowerCase();
  const keywords = TAB_KEYWORDS[tab] ?? [];
  const agents = TAB_AGENT_FALLBACK[tab] ?? [];

  return (
    keywords.some(keyword => searchableText.includes(keyword)) ||
    agents.includes(task.agent)
  );
}

export function filterTaskBoardTasks(
  tasks: WorkspaceTaskView[],
  filters: {
    tab: TaskBoardTab;
    status: TaskBoardStatusFilter;
    agent: TaskBoardAgentFilter;
  },
): WorkspaceTaskView[] {
  return tasks.filter(task => {
    if (!taskMatchesTab(task, filters.tab)) {
      return false;
    }
    if (filters.status !== 'all' && task.status !== filters.status) {
      return false;
    }
    if (filters.agent !== 'all' && task.agent !== filters.agent) {
      return false;
    }
    return true;
  });
}

export function deriveTaskBoardAgentOptions(
  tasks: WorkspaceTaskView[],
): ApiAgentKind[] {
  const preferredOrder: ApiAgentKind[] = ['tela', 'jules', 'sophie', 'marc', 'assistant'];
  const agents = new Set(tasks.map(task => task.agent));

  return preferredOrder.filter(agent => agents.has(agent));
}
