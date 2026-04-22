import { startTransition, useEffect, useMemo, useState } from 'react';
import { getErrorDetail } from '@/api/client';
import { listAgentInstances } from '@/api/agentInstances';
import { listTasks } from '@/api/tasks';
import type { ApiAgentInstance, ApiTask } from '@/api/types';
import {
  deriveRepoFilters,
  toWorkspaceAgentOption,
  toWorkspaceTaskView,
} from '../utils';
import type { WorkspaceAgentOption, WorkspaceTaskView } from '../utils';

async function loadWorkspaceData(): Promise<{
  agents: ApiAgentInstance[];
  tasks: ApiTask[];
  agentsError: string | null;
  tasksError: string | null;
}> {
  const [nextAgents, nextTasks] = await Promise.allSettled([
    listAgentInstances({ is_active: true }),
    listTasks({ limit: 200 }),
  ]);

  return {
    agents: nextAgents.status === 'fulfilled' ? nextAgents.value : [],
    tasks: nextTasks.status === 'fulfilled' ? nextTasks.value : [],
    agentsError:
      nextAgents.status === 'rejected'
        ? getErrorDetail(nextAgents.reason, 'Failed to load active agent instances.')
        : null,
    tasksError:
      nextTasks.status === 'rejected'
        ? getErrorDetail(nextTasks.reason, 'Failed to load tasks.')
        : null,
  };
}

export type WorkspaceData = {
  agentInstances: ApiAgentInstance[];
  agentOptions: WorkspaceAgentOption[];
  agentOptionsById: Map<string, WorkspaceAgentOption>;
  taskViews: WorkspaceTaskView[];
  repoFilters: string[];
  boardRepoFilter: string;
  setBoardRepoFilter: (filter: string) => void;
  isLoadingAgents: boolean;
  isLoading: boolean;
  agentsError: string | null;
  tasksError: string | null;
  reload: () => Promise<void>;
};

export function useWorkspaceData(): WorkspaceData {
  const [agentInstances, setAgentInstances] = useState<ApiAgentInstance[]>([]);
  const [tasks, setTasks] = useState<ApiTask[]>([]);
  const [isLoadingAgents, setIsLoadingAgents] = useState(true);
  const [isLoading, setIsLoading] = useState(true);
  const [agentsError, setAgentsError] = useState<string | null>(null);
  const [tasksError, setTasksError] = useState<string | null>(null);
  const [boardRepoFilter, setBoardRepoFilter] = useState<string>('all');

  const agentOptions = useMemo(
    () => agentInstances.map(toWorkspaceAgentOption),
    [agentInstances],
  );

  const agentOptionsById = useMemo(
    () => new Map(agentOptions.map(agent => [agent.id, agent])),
    [agentOptions],
  );

  const taskViews = useMemo(
    () => tasks.map(task => toWorkspaceTaskView(task, agentOptionsById)),
    [tasks, agentOptionsById],
  );

  const repoFilters = useMemo(() => deriveRepoFilters(taskViews), [taskViews]);

  const applyResult = (result: Awaited<ReturnType<typeof loadWorkspaceData>>) => {
    startTransition(() => {
      setAgentInstances(result.agents);
      setAgentsError(result.agentsError);
      setIsLoadingAgents(false);
      setTasks(result.tasks);
      setTasksError(result.tasksError);
      setIsLoading(false);
    });
  };

  // Load once on mount — no polling.
  useEffect(() => {
    loadWorkspaceData().then(applyResult);
  }, []);

  // Reset board filter when the filtered repo disappears from the task list.
  useEffect(() => {
    if (boardRepoFilter !== 'all' && !repoFilters.includes(boardRepoFilter)) {
      setBoardRepoFilter('all');
    }
  }, [boardRepoFilter, repoFilters]);

  const reload = async () => {
    const result = await loadWorkspaceData();
    applyResult(result);
  };

  return {
    agentInstances,
    agentOptions,
    agentOptionsById,
    taskViews,
    repoFilters,
    boardRepoFilter,
    setBoardRepoFilter,
    isLoadingAgents,
    isLoading,
    agentsError,
    tasksError,
    reload,
  };
}
