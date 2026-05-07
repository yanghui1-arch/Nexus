import { startTransition, useEffect, useMemo, useState } from 'react';
import { toast } from 'sonner';
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

const DEFAULT_TASK_BOARD_REPO = 'yanghui1-arch/Nexus';

export type WorkspaceData = {
  agentInstances: ApiAgentInstance[];
  agentOptions: WorkspaceAgentOption[];
  agentOptionsById: Map<string, WorkspaceAgentOption>;
  taskViews: WorkspaceTaskView[];
  repoOptions: string[];
  boardRepoFilter: string;
  setBoardRepoFilter: (filter: string) => void;
  isLoadingAgents: boolean;
  isLoading: boolean;
  reload: () => Promise<void>;
};

export function useWorkspaceData(): WorkspaceData {
  const [agentInstances, setAgentInstances] = useState<ApiAgentInstance[]>([]);
  const [tasks, setTasks] = useState<ApiTask[]>([]);
  const [isLoadingAgents, setIsLoadingAgents] = useState(true);
  const [isLoading, setIsLoading] = useState(true);
  const [boardRepoFilter, setBoardRepoFilter] = useState<string>(
    DEFAULT_TASK_BOARD_REPO,
  );

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
  const repoOptions = useMemo(
    () => [
      DEFAULT_TASK_BOARD_REPO,
      ...repoFilters.filter(repo => repo !== DEFAULT_TASK_BOARD_REPO),
    ],
    [repoFilters],
  );

  const applyResult = (result: Awaited<ReturnType<typeof loadWorkspaceData>>) => {
    if (result.agentsError) {
      toast.error('Failed to load agents', { description: result.agentsError });
    }
    if (result.tasksError) {
      toast.error('Failed to load tasks', { description: result.tasksError });
    }

    startTransition(() => {
      setAgentInstances(result.agents);
      setIsLoadingAgents(false);
      setTasks(result.tasks);
      setIsLoading(false);
    });
  };

  // Load once on mount — no polling.
  useEffect(() => {
    loadWorkspaceData().then(applyResult);
  }, []);

  // Reset board filter when the selected repo disappears from the available options.
  useEffect(() => {
    if (!repoOptions.includes(boardRepoFilter)) {
      setBoardRepoFilter(DEFAULT_TASK_BOARD_REPO);
    }
  }, [boardRepoFilter, repoOptions]);

  const reload = async () => {
    const result = await loadWorkspaceData();
    applyResult(result);
  };

  return {
    agentInstances,
    agentOptions,
    agentOptionsById,
    taskViews,
    repoOptions,
    boardRepoFilter,
    setBoardRepoFilter,
    isLoadingAgents,
    isLoading,
    reload,
  };
}
