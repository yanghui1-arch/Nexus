import { startTransition, useEffect, useMemo, useState, type FormEvent } from 'react';
import { toast } from 'sonner';
import { getErrorDetail } from '@/api/client';
import { consultTask } from '@/api/tasks';
import {
  selectTrackingTask,
  sortTaskViewsByNewest,
} from '@/lib/workspace-task-view';
import type {
  WorkspaceConsultMessageView,
  WorkspaceTaskView,
} from '@/lib/workspace-task-view';
import type { WorkspaceRecordsData } from '@/lib/useWorkspaceRecords';

type UseProcessTrackingInput = Pick<WorkspaceRecordsData, 'agentOptions' | 'taskViews'>;

export type ProcessTracking = {
  selectedAgentId: string;
  setSelectedAgentId: (id: string) => void;
  selectedTaskId: string;
  setSelectedTaskId: (id: string) => void;
  tasksForSelectedAgent: WorkspaceTaskView[];
  selectedTrackingTask: WorkspaceTaskView | undefined;
  trackingInput: string;
  setTrackingInput: (value: string) => void;
  activeConsultMessages: WorkspaceConsultMessageView[];
  isSendingTracking: boolean;
  consultSelectedTask: (event: FormEvent<HTMLFormElement>) => Promise<void>;
};

export function useProcessTracking({
  agentOptions,
  taskViews,
}: UseProcessTrackingInput): ProcessTracking {
  const [selectedAgentId, setSelectedAgentId] = useState<string>('');
  const [selectedTaskId, setSelectedTaskId] = useState<string>('');
  const [trackingInput, setTrackingInput] = useState<string>('');
  const [consultMessagesByTask, setConsultMessagesByTask] = useState<
    Record<string, WorkspaceConsultMessageView[]>
  >({});
  const [isSendingTracking, setIsSendingTracking] = useState(false);

  const tasksForSelectedAgent = useMemo(
    () =>
      sortTaskViewsByNewest(
        taskViews.filter(task => task.agentInstanceId === selectedAgentId),
      ),
    [selectedAgentId, taskViews],
  );

  const selectedTrackingTask = useMemo(
    () => tasksForSelectedAgent.find(task => task.id === selectedTaskId),
    [selectedTaskId, tasksForSelectedAgent],
  );

  const activeConsultMessages = useMemo(
    () => (selectedTaskId ? consultMessagesByTask[selectedTaskId] ?? [] : []),
    [consultMessagesByTask, selectedTaskId],
  );

  // Keep selectedAgentId pointing at a valid agent.
  useEffect(() => {
    if (agentOptions.length === 0) {
      if (selectedAgentId !== '') setSelectedAgentId('');
      return;
    }

    if (!agentOptions.some(agent => agent.id === selectedAgentId)) {
      setSelectedAgentId(agentOptions[0].id);
    }
  }, [agentOptions, selectedAgentId]);

  // Auto-select the best task when the agent changes or tasks reload.
  useEffect(() => {
    const preferredTask = selectTrackingTask(tasksForSelectedAgent);

    if (!preferredTask) {
      if (selectedTaskId !== '') setSelectedTaskId('');
      return;
    }

    if (!tasksForSelectedAgent.some(task => task.id === selectedTaskId)) {
      setSelectedTaskId(preferredTask.id);
    }
  }, [selectedTaskId, tasksForSelectedAgent]);

  // Clear input when the selection changes.
  useEffect(() => {
    startTransition(() => {
      setTrackingInput('');
    });
  }, [selectedAgentId, selectedTaskId]);

  const consultSelectedTask = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    const question = trackingInput.trim();
    const task = selectedTrackingTask;

    if (!question || !task) {
      return;
    }

    const timestamp = new Date().toISOString();
    const userMessage: WorkspaceConsultMessageView = {
      id: `consult-user-${Date.now().toString(36)}`,
      role: 'user',
      text: question,
      time: timestamp,
      status: null,
    };

    startTransition(() => {
      setIsSendingTracking(true);
      setTrackingInput('');
      setConsultMessagesByTask(previous => ({
        ...previous,
        [task.id]: [...(previous[task.id] ?? []), userMessage],
      }));
    });

    try {
      const response = await consultTask(task.id, { message: question });
      const agentMessage: WorkspaceConsultMessageView = {
        id: `consult-agent-${Date.now().toString(36)}`,
        role: 'agent',
        text: response.reply,
        time: response.timestamp,
        status: response.status,
      };

      startTransition(() => {
        setConsultMessagesByTask(previous => ({
          ...previous,
          [task.id]: [...(previous[task.id] ?? []), agentMessage],
        }));
      });
    } catch (error) {
      toast.error('Failed to consult agent', {
        description: getErrorDetail(error, 'Failed to consult the selected task.'),
      });
    } finally {
      startTransition(() => {
        setIsSendingTracking(false);
      });
    }
  };

  return {
    selectedAgentId,
    setSelectedAgentId,
    selectedTaskId,
    setSelectedTaskId,
    tasksForSelectedAgent,
    selectedTrackingTask,
    trackingInput,
    setTrackingInput,
    activeConsultMessages,
    isSendingTracking,
    consultSelectedTask,
  };
}
