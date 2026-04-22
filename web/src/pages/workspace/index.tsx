import { Navigate, useParams } from 'react-router-dom';
import { DashboardShell } from '@/components/layout/DashboardShell';
import { WorkspaceComposerCard } from './components/WorkspaceComposerCard';
import { WorkspaceTaskBoard } from './components/WorkspaceTaskBoard';
import { WorkspaceTrackingPanel } from './components/WorkspaceTrackingPanel';
import { useWorkspaceData } from './hooks/useWorkspaceData';
import { usePublishTask } from './hooks/usePublishTask';
import { useProcessTracking } from './hooks/useProcessTracking';
import {
  DEFAULT_WORKSPACE_PATH,
  isWorkspaceSection,
  type WorkspaceSection,
} from '@/lib/dashboard-nav';

const SECTION_META: Record<WorkspaceSection, { title: string; description: string }> = {
  'publish-task': {
    title: 'Publish Task',
    description: 'Create and assign new work items for agents.',
  },
  'process-tracking': {
    title: 'Process Tracking',
    description: 'Select an agent and task, then ask for the latest process.',
  },
  'task-board': {
    title: 'Task Board',
    description: 'Live task board grouped by backend task status.',
  },
};

export default function WorkspacePage() {
  const { section: routeSection } = useParams<{ section: string }>();
  const section = isWorkspaceSection(routeSection) ? routeSection : null;

  const data = useWorkspaceData();
  const publisher = usePublishTask(data);
  const tracking = useProcessTracking(data);

  if (!section) {
    return <Navigate to={DEFAULT_WORKSPACE_PATH} replace />;
  }

  const isTracking = section === 'process-tracking';

  return (
    <DashboardShell
      title={SECTION_META[section].title}
      description={SECTION_META[section].description}
    >
      <div className={isTracking ? 'flex h-full min-h-0 flex-col' : 'overflow-y-auto'}>
        {section === 'publish-task' && (
          <section className="mx-auto w-full max-w-6xl">
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
          <section className="flex h-full min-h-0 flex-col">
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

        {section === 'task-board' && (
          <section className="h-full min-h-0 overflow-y-auto">
            <WorkspaceTaskBoard
              tasks={data.taskViews}
              repoFilters={data.repoFilters}
              repoFilter={data.boardRepoFilter}
              isLoading={data.isLoading}
              onRepoFilterChange={data.setBoardRepoFilter}
            />
          </section>
        )}
      </div>
    </DashboardShell>
  );
}
