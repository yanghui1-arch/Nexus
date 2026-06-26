import { startTransition, useEffect, useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { getErrorDetail } from '@/api/client';
import { createTask } from '@/api/tasks';
import type { WorkspaceRecordsData } from '@/lib/useWorkspaceRecords';
import type { WorkspaceAgentOption } from '@/lib/workspace-task-view';
import type { WorkspaceComposerValues } from '../types';

const EMPTY_COMPOSER_VALUES: WorkspaceComposerValues = {
  question: '',
  externalIssueUrl: '',
  agentInstanceId: '',
};

type UsePublishTaskInput = Pick<
  WorkspaceRecordsData,
  'agentInstances' | 'agentOptions' | 'reload'
>;

export type PublishTask = {
  composerValues: WorkspaceComposerValues;
  setComposerValues: (next: WorkspaceComposerValues) => void;
  selectedAgent: WorkspaceAgentOption | null;
  hasWorkspaceContext: boolean;
  isSubmitting: boolean;
  publishTask: (event: FormEvent<HTMLFormElement>) => Promise<void>;
};

export function usePublishTask({
  agentInstances,
  agentOptions,
  reload,
}: UsePublishTaskInput): PublishTask {
  const { t } = useTranslation();
  const [composerValues, setComposerValues] =
    useState<WorkspaceComposerValues>(EMPTY_COMPOSER_VALUES);
  const [isSubmitting, setIsSubmitting] = useState(false);

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

  const selectedAgent = agentOptions.find(
    agent => agent.id === composerValues.agentInstanceId,
  ) ?? null;
  const selectedAgentInstance = agentInstances.find(
    agent => agent.id === composerValues.agentInstanceId,
  );
  const hasWorkspaceContext = Boolean(
    selectedAgentInstance?.workspace?.github_repo &&
      selectedAgentInstance?.workspace?.project,
  );

  const publishTask = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    const question = composerValues.question.trim();
    const externalIssueUrl = composerValues.externalIssueUrl.trim();

    if (!question || !selectedAgentInstance || !hasWorkspaceContext) {
      return;
    }

    startTransition(() => {
      setIsSubmitting(true);
    });

    try {
      await createTask({
        agent_instance_id: selectedAgentInstance.id,
        agent: selectedAgentInstance.agent,
        question,
        external_issue_url: externalIssueUrl || null,
      });

      startTransition(() => {
        setComposerValues({
          ...EMPTY_COMPOSER_VALUES,
          agentInstanceId: selectedAgentInstance.id,
        });
      });

      await reload();

      toast.success(t('publishTask.toastPublished'), {
        description: t('publishTask.toastPublishedDescription'),
      });
    } catch (error) {
      toast.error(t('publishTask.toastPublishFailed'), {
        description: getErrorDetail(error, t('publishTask.toastPublishFailed')),
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
    selectedAgent,
    hasWorkspaceContext,
    isSubmitting,
    publishTask,
  };
}
