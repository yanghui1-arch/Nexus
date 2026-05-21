import { startTransition, useEffect, useMemo, useState } from 'react';
import { toast } from 'sonner';
import { getErrorDetail } from '@/api/client';
import { listAgentInstances } from '@/api/agentInstances';
import { listTasks } from '@/api/tasks';
import type { ApiAgentInstance, ApiTask } from '@/api/types';
import type { ListTasksParams } from '@/api/tasks';
import {
  toWorkspaceAgentOption,
  toWorkspaceTaskView,
  type WorkspaceAgentOption,
  type WorkspaceTaskView,
} from './workspace-task-view';

type WorkspaceRecordsLoadResult = {
  agents: ApiAgentInstance[];
  tasks: ApiTask[];
  agentsError: string | null;
  tasksError: string | null;
};

async function loadWorkspaceRecords(
  taskParams: ListTasksParams = { limit: 200 },
): Promise<WorkspaceRecordsLoadResult> {
  const [nextAgents, nextTasks] = await Promise.allSettled([
    listAgentInstances({ is_active: true }),
    listTasks(taskParams),
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

export type WorkspaceRecordsData = {
  agentInstances: ApiAgentInstance[];
  agentOptions: WorkspaceAgentOption[];
  agentOptionsById: Map<string, WorkspaceAgentOption>;
  taskViews: WorkspaceTaskView[];
  isLoadingAgents: boolean;
  isLoading: boolean;
  reload: () => Promise<void>;
};

export function useWorkspaceRecords(
  taskParams: ListTasksParams = { limit: 200 },
): WorkspaceRecordsData {
  const [agentInstances, setAgentInstances] = useState<ApiAgentInstance[]>([]);
  const [tasks, setTasks] = useState<ApiTask[]>([]);
  const [isLoadingAgents, setIsLoadingAgents] = useState(true);
  const [isLoading, setIsLoading] = useState(true);

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

  const applyResult = (result: WorkspaceRecordsLoadResult) => {
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

  useEffect(() => {
    void loadWorkspaceRecords(taskParams).then(applyResult);
  }, [taskParams]);

  const reload = async () => {
    const result = await loadWorkspaceRecords(taskParams);
    applyResult(result);
  };

  return {
    agentInstances,
    agentOptions,
    agentOptionsById,
    taskViews,
    isLoadingAgents,
    isLoading,
    reload,
  };
}
