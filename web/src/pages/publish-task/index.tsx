import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { useAppLayout } from '@/components/layout/AppLayout';
import { useWorkspaceRecords } from '@/lib/useWorkspaceRecords';
import { PublishTaskComposerCard } from './components/PublishTaskComposerCard';
import { usePublishTask } from './hooks/usePublishTask';

export default function PublishTaskPage() {
  const { t } = useTranslation();

  useAppLayout({
    title: t('publishTask.title'),
    description: t('publishTask.description'),
    mainClassName: 'pt-3 pb-6',
  });

  const data = useWorkspaceRecords();
  const codingAgentOptions = useMemo(
    () => data.agentOptions.filter(agent => agent.agent !== 'assistant'),
    [data.agentOptions],
  );
  const codingAgentInstances = useMemo(
    () => data.agentInstances.filter(instance => instance.agent !== 'assistant'),
    [data.agentInstances],
  );
  const publisher = usePublishTask({
    ...data,
    agentInstances: codingAgentInstances,
    agentOptions: codingAgentOptions,
  });

  return (
    <section className="w-full max-w-5xl">
      <PublishTaskComposerCard
        value={publisher.composerValues}
        agents={codingAgentOptions}
        selectedAgent={publisher.selectedAgent}
        hasWorkspaceContext={publisher.hasWorkspaceContext}
        isSubmitting={publisher.isSubmitting}
        onValueChange={publisher.setComposerValues}
        onSubmit={publisher.publishTask}
      />
    </section>
  );
}
