import { useEffect, useMemo, useState } from 'react';
import { useWorkspaceRecords } from '@/lib/useWorkspaceRecords';
import type { WorkspaceTaskView } from '@/lib/workspace-task-view';
import {
  DEFAULT_TASK_BOARD_REPO,
  deriveTaskBoardRepoOptions,
  getVisibleTaskBoardTasks,
  groupTaskBoardTasks,
  type TaskBoardStatus,
} from '../utils';

export type TaskBoardData = {
  groupedTasks: Record<TaskBoardStatus, WorkspaceTaskView[]>;
  repoOptions: string[];
  repoFilter: string;
  setRepoFilter: (repo: string) => void;
  isLoading: boolean;
};

export function useTaskBoardData(): TaskBoardData {
  const { taskViews, isLoading } = useWorkspaceRecords();
  const [repoFilter, setRepoFilter] = useState(DEFAULT_TASK_BOARD_REPO);

  const repoOptions = useMemo(
    () => deriveTaskBoardRepoOptions(taskViews),
    [taskViews],
  );

  useEffect(() => {
    if (!repoOptions.includes(repoFilter)) {
      setRepoFilter(DEFAULT_TASK_BOARD_REPO);
    }
  }, [repoFilter, repoOptions]);

  const visibleTasks = useMemo(
    () => getVisibleTaskBoardTasks(taskViews, repoFilter),
    [repoFilter, taskViews],
  );

  const groupedTasks = useMemo(
    () => groupTaskBoardTasks(visibleTasks),
    [visibleTasks],
  );

  return {
    groupedTasks,
    repoOptions,
    repoFilter,
    setRepoFilter,
    isLoading,
  };
}
