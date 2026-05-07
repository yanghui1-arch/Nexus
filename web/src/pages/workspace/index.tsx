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
  'code-review': {
    title: 'Code Review',
    description: 'Open the Nexus review queue and inspect agent pull requests.',
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

  if (section === 'code-review') {
    return <Navigate to="/workspace/code-review/nexus" replace />;
  }

  const mainClassName =
    section === 'publish-task'
      ? 'pt-3 pb-6'
      : section === 'process-tracking'
        ? 'overflow-hidden p-0'
        : undefined;

  return (
    <DashboardShell
      title={SECTION_META[section].title}
      description={SECTION_META[section].description}
      mainClassName={mainClassName}
    >
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

      {section === 'task-board' && (
        <WorkspaceTaskBoard
          tasks={data.taskViews}
          repoOptions={data.repoOptions}
          repoFilter={data.boardRepoFilter}
          isLoading={data.isLoading}
          onRepoFilterChange={data.setBoardRepoFilter}
        />
      )}
    </DashboardShell>
  );
}
