import { useAppLayout } from '@/components/layout/AppLayout';
import { useWorkspaceRecords } from '@/lib/useWorkspaceRecords';
import { ProcessTrackingPanel } from './components/ProcessTrackingPanel';
import { useProcessTracking } from './hooks/useProcessTracking';

export default function ProcessTrackingPage() {
  useAppLayout({
    title: 'Process Tracking',
    description: 'Select an agent and task, then ask for the latest process.',
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
