import type { ApiTaskCategory, ApiTaskStatus } from '@/api/types';
import {
  sortTaskViewsByNewest,
  type WorkspaceTaskView,
} from '@/lib/workspace-task-view';

export const DEFAULT_TASK_BOARD_REPO = 'yanghui1-arch/Nexus';

export const TASK_BOARD_STATUS_ORDER = [
  'queued',
  'running',
  'waiting_for_review',
  'merged',
  'failed',
] as const satisfies readonly ApiTaskStatus[];

export type TaskBoardStatus = (typeof TASK_BOARD_STATUS_ORDER)[number];

const TASK_BOARD_CATEGORY = 'coding' satisfies ApiTaskCategory;

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
