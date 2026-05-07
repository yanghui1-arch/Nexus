import { Navigate, useParams } from 'react-router-dom';
import { useAppLayout } from '@/components/layout/AppLayout';
import { WorkspaceComposerCard } from './components/WorkspaceComposerCard';
import { WorkspaceTrackingPanel } from './components/WorkspaceTrackingPanel';
import { useWorkspaceData } from './hooks/useWorkspaceData';
import { usePublishTask } from './hooks/usePublishTask';
import { useProcessTracking } from './hooks/useProcessTracking';
import {
  DEFAULT_WORKSPACE_PATH,
  isWorkspaceSection,
} from '@/lib/dashboard-nav';

export default function WorkspacePage() {
  const { section: routeSection } = useParams<{ section: string }>();
  const section = isWorkspaceSection(routeSection) ? routeSection : null;

  const data = useWorkspaceData();
  const publisher = usePublishTask(data);
  const tracking = useProcessTracking(data);

  const title =
    section === 'publish-task'
      ? 'Publish Task'
      : section === 'process-tracking'
        ? 'Process Tracking'
        : 'Workspace';
  const description =
    section === 'publish-task'
      ? 'Create and assign new work items for agents.'
      : section === 'process-tracking'
        ? 'Select an agent and task, then ask for the latest process.'
        : 'Workspace tools and task flows.';
  const mainClassName =
    section === 'publish-task'
      ? 'pt-3 pb-6'
      : section === 'process-tracking'
        ? 'overflow-hidden p-0'
        : undefined;

  useAppLayout({
    title,
    description,
    mainClassName,
  });

  if (!section) {
    return <Navigate to={DEFAULT_WORKSPACE_PATH} replace />;
  }

  if (section === 'task-board') {
    return <Navigate to="/workspace/task-board" replace />;
  }

  if (section === 'code-review') {
    return <Navigate to="/workspace/code-review/nexus" replace />;
  }

  return (
    <>
      {section === 'publish-task' && (
        <section className="w-full max-w-5xl">
          <WorkspaceComposerCard
            value={publisher.composerValues}
            agents={data.agentOptions}
            isSubmitting={publisher.isSubmitting}
            onValueChange={publisher.setComposerValues}
            onSubmit={publisher.publishTask}
          />
        </section>
      )}

      {section === 'process-tracking' && (
        <section className="flex min-h-0 flex-1 flex-col px-6 py-6">
          <WorkspaceTrackingPanel
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
      )}
    </>
  );
}
