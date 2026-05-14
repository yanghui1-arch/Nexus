import { AgentEntitlementEmptyState } from '@/components/entitlements/AgentEntitlementStates';
import { useAppLayout } from '@/components/layout/AppLayout';
import { useWorkspaceRecords } from '@/lib/useWorkspaceRecords';
import { PublishTaskComposerCard } from './components/PublishTaskComposerCard';
import { usePublishTask } from './hooks/usePublishTask';

export default function PublishTaskPage() {
  useAppLayout({
    title: 'Publish Task',
    description: 'Create and assign new work items for agents.',
    mainClassName: 'pt-3 pb-6',
  });

  const data = useWorkspaceRecords();
  const publisher = usePublishTask(data);

  if (!data.isLoadingAgents && data.agentInstances.length === 0) {
    return (
      <section className="w-full max-w-5xl">
        <AgentEntitlementEmptyState description="You need an active Tela or Sophie entitlement before you can publish tasks to an agent." />
      </section>
    );
  }

  return (
    <section className="w-full max-w-5xl">
      <PublishTaskComposerCard
        value={publisher.composerValues}
        agents={data.agentOptions}
        isSubmitting={publisher.isSubmitting}
        onValueChange={publisher.setComposerValues}
        onSubmit={publisher.publishTask}
      />
    </section>
  );
}
