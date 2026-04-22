import { startTransition, useEffect, useState, type FormEvent } from 'react';
import { toast } from 'sonner';
import { getErrorDetail } from '@/api/client';
import { createTask } from '@/api/tasks';
import type { WorkspaceComposerValues } from '../utils';
import type { WorkspaceData } from './useWorkspaceData';

const EMPTY_COMPOSER_VALUES: WorkspaceComposerValues = {
  question: '',
  repo: '',
  project: '',
  agentInstanceId: '',
};

type UsePublishTaskInput = Pick<
  WorkspaceData,
  'agentInstances' | 'agentOptions' | 'reload'
>;

export type PublishTask = {
  composerValues: WorkspaceComposerValues;
  setComposerValues: (next: WorkspaceComposerValues) => void;
  isSubmitting: boolean;
  publishTask: (event: FormEvent<HTMLFormElement>) => Promise<void>;
};

export function usePublishTask({
  agentInstances,
  agentOptions,
  reload,
}: UsePublishTaskInput): PublishTask {
  const [composerValues, setComposerValues] =
    useState<WorkspaceComposerValues>(EMPTY_COMPOSER_VALUES);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Keep composerValues.agentInstanceId pointing at a valid agent.
  useEffect(() => {
    if (agentOptions.length === 0) {
      if (composerValues.agentInstanceId !== '') {
        setComposerValues(previous => ({ ...previous, agentInstanceId: '' }));
      }
      return;
    }

    if (!agentOptions.some(agent => agent.id === composerValues.agentInstanceId)) {
      setComposerValues(previous => ({
        ...previous,
        agentInstanceId: agentOptions[0].id,
      }));
    }
  }, [agentOptions, composerValues.agentInstanceId]);

  const publishTask = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    const question = composerValues.question.trim();
    const repo = composerValues.repo.trim();
    const project = composerValues.project.trim();
    const selectedAgent = agentInstances.find(
      agent => agent.id === composerValues.agentInstanceId,
    );

    if (!question || !repo || !selectedAgent) {
      return;
    }

    startTransition(() => {
      setIsSubmitting(true);
    });

    try {
      await createTask({
        agent_instance_id: selectedAgent.id,
        agent: selectedAgent.agent,
        question,
        repo,
        project: project || null,
      });

      startTransition(() => {
        setComposerValues({
          ...EMPTY_COMPOSER_VALUES,
          agentInstanceId: selectedAgent.id,
        });
      });

      await reload();

      toast.success('Task published', {
        description: 'The task has been submitted to the backend queue.',
      });
    } catch (error) {
      toast.error('Failed to publish task', {
        description: getErrorDetail(error, 'Failed to publish task.'),
      });
    } finally {
      startTransition(() => {
        setIsSubmitting(false);
      });
    }
  };

  return {
    composerValues,
    setComposerValues,
    isSubmitting,
    publishTask,
  };
}
