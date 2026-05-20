import { useTranslation } from 'react-i18next';
import { useAppLayout } from '@/components/layout/AppLayout';
import { useWorkspaceRecords } from '@/lib/useWorkspaceRecords';
import { ProcessTrackingPanel } from './components/ProcessTrackingPanel';
import { useProcessTracking } from './hooks/useProcessTracking';

export default function ProcessTrackingPage() {
  const { t } = useTranslation();

  useAppLayout({
    title: t('processTracking.title'),
    description: t('processTracking.description'),
    mainClassName: 'overflow-hidden p-0',
  });

  const data = useWorkspaceRecords();
  const tracking = useProcessTracking(data);

  return (
    <section className="flex min-h-0 flex-1 flex-col px-6 py-6">
      <ProcessTrackingPanel
        agents={data.agentOptions}
        tasksForAgent={tracking.tasksForSelectedAgent}
        messages={tracking.activeConsultMessages}
        selectedAgentId={tracking.selectedAgentId}
        selectedTaskId={tracking.selectedTaskId}
        selectedTask={tracking.selectedTrackingTask}
        input={tracking.trackingInput}
        isLoadingAgents={data.isLoadingAgents}
        isSending={tracking.isSendingTracking}
        onSelectedAgentChange={tracking.setSelectedAgentId}
        onSelectedTaskChange={tracking.setSelectedTaskId}
        onInputChange={tracking.setTrackingInput}
        onSubmit={tracking.consultSelectedTask}
      />
    </section>
  );
}
