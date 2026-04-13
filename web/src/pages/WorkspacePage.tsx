import { useMemo, useState, type FormEvent } from 'react';
import { Navigate, useParams } from 'react-router-dom';
import {
  AGENTS,
  INITIAL_TASKS,
  INITIAL_TRACKING,
  REPOS,
  type WorkspaceMessage,
  type WorkspaceTask,
} from '@/data/workspaceMockData';
import { DashboardShell } from '@/components/layout/DashboardShell';
import {
  WorkspaceComposerCard,
  type WorkspaceComposerValues,
} from '@/components/workspace/WorkspaceComposerCard';
import { WorkspaceTaskBoard } from '@/components/workspace/WorkspaceTaskBoard';
import { WorkspaceTrackingPanel } from '@/components/workspace/WorkspaceTrackingPanel';
import { STATUS_META, sortTasksForBoard } from '@/components/workspace/workspace-utils';
import {
  DEFAULT_WORKSPACE_PATH,
  isWorkspaceSection,
  type WorkspaceSection,
} from '@/lib/dashboard-nav';

function repoNameById(repoId: string): string {
  return REPOS.find(repo => repo.id === repoId)?.name ?? repoId;
}

function composeProcessTrackingReply(
  question: string,
  task: WorkspaceTask | undefined,
): string {
  if (!task) {
    return 'No assigned task right now. Please publish one and I can provide status updates.';
  }

  const query = question.toLowerCase();
  const statusLabel = STATUS_META[task.status].label.toLowerCase();

  let reply = `${task.title} is ${statusLabel} on ${repoNameById(task.repoId)} at ${task.progress}% progress.`;

  if (task.status === 'blocked') {
    reply += ` Blocker: ${task.notes ?? 'waiting for dependency approval.'}`;
  }
  if (query.includes('eta') || query.includes('when')) {
    reply += ' Next checkpoint is expected within about 30 minutes.';
  }
  if (query.includes('risk') || query.includes('blocker')) {
    reply +=
      task.status === 'blocked'
        ? ' Main risk is unresolved dependency.'
        : ' No critical risk reported at this checkpoint.';
  }

  return reply;
}

const SECTION_META: Record<
  WorkspaceSection,
  { title: string; description: string }
> = {
  'publish-task': {
    title: 'Publish Task',
    description: 'Create and assign new work items for agents.',
  },
  'process-tracking': {
    title: 'Process Tracking',
    description: 'One conversation panel for live checkpoints and blockers.',
  },
  'task-board': {
    title: 'Task Board',
    description: 'Single kanban board view with status columns.',
  },
};

export default function WorkspacePage() {
  const { section } = useParams<{ section: string }>();

  if (!isWorkspaceSection(section)) {
    return <Navigate to={DEFAULT_WORKSPACE_PATH} replace />;
  }

  const defaultRepoId = REPOS[0]?.id ?? '';
  const defaultAgentId = AGENTS[0]?.id ?? '';

  const [tasks, setTasks] = useState<WorkspaceTask[]>(INITIAL_TASKS);
  const [composerValues, setComposerValues] = useState<WorkspaceComposerValues>({
    title: '',
    notes: '',
    repoId: defaultRepoId,
    agentId: defaultAgentId,
    urgency: 'high',
  });
  const [boardRepoFilter, setBoardRepoFilter] = useState<string>('all');

  const [selectedAgentId, setSelectedAgentId] = useState<string>(defaultAgentId);
  const [messagesByAgent, setMessagesByAgent] =
    useState<Record<string, WorkspaceMessage[]>>(INITIAL_TRACKING);
  const [trackingInput, setTrackingInput] = useState('');

  const tasksForSelectedAgent = useMemo(() => {
    return sortTasksForBoard(
      tasks.filter(task => task.agentId === selectedAgentId),
    );
  }, [tasks, selectedAgentId]);

  const selectedTrackingTask =
    tasksForSelectedAgent.find(task => task.status !== 'done') ??
    tasksForSelectedAgent[0];

  const activeMessages = messagesByAgent[selectedAgentId] ?? [];

  const publishTask = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    const title = composerValues.title.trim();
    if (!title || !composerValues.repoId || !composerValues.agentId) return;

    const nowIso = new Date().toISOString();
    const task: WorkspaceTask = {
      id: `ws-${Date.now().toString(36)}`,
      title,
      repoId: composerValues.repoId,
      agentId: composerValues.agentId,
      urgency: composerValues.urgency,
      status: 'queued',
      progress: 8,
      notes: composerValues.notes.trim() || undefined,
      createdAt: nowIso,
    };

    setTasks(previous => [task, ...previous]);

    setMessagesByAgent(previous => ({
      ...previous,
      [composerValues.agentId]: [
        ...(previous[composerValues.agentId] ?? []),
        {
          id: `sys-${Date.now().toString(36)}`,
          role: 'system',
          text: `Task assigned from ${repoNameById(composerValues.repoId)}: ${title}`,
          time: nowIso,
        },
      ],
    }));

    setComposerValues(previous => ({
      ...previous,
      title: '',
      notes: '',
      urgency: 'high',
    }));
  };

  const sendTrackingMessage = (text: string) => {
    const content = text.trim();
    if (!content || !selectedAgentId) return;

    const nowIso = new Date().toISOString();
    setMessagesByAgent(previous => ({
      ...previous,
      [selectedAgentId]: [
        ...(previous[selectedAgentId] ?? []),
        {
          id: `usr-${Date.now().toString(36)}`,
          role: 'user',
          text: content,
          time: nowIso,
        },
      ],
    }));

    const response = composeProcessTrackingReply(content, selectedTrackingTask);

    window.setTimeout(() => {
      setMessagesByAgent(previous => ({
        ...previous,
        [selectedAgentId]: [
          ...(previous[selectedAgentId] ?? []),
          {
            id: `agt-${Date.now().toString(36)}`,
            role: 'agent',
            text: response,
            time: new Date().toISOString(),
          },
        ],
      }));
    }, 250);
  };

  const onSubmitTracking = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    sendTrackingMessage(trackingInput);
    setTrackingInput('');
  };

  const pageContent =
    section === 'publish-task' ? (
      <section className="mx-auto w-full max-w-6xl">
        <WorkspaceComposerCard
          value={composerValues}
          repos={REPOS}
          agents={AGENTS}
          onValueChange={setComposerValues}
          onSubmit={publishTask}
        />
      </section>
    ) : section === 'process-tracking' ? (
      <section className="mx-auto h-full w-full max-w-6xl min-h-0">
        <WorkspaceTrackingPanel
          agents={AGENTS}
          messages={activeMessages}
          selectedAgentId={selectedAgentId}
          selectedTask={selectedTrackingTask}
          tasksForAgent={tasksForSelectedAgent}
          repoNameById={repoNameById}
          input={trackingInput}
          onSelectedAgentChange={setSelectedAgentId}
          onInputChange={setTrackingInput}
          onSubmit={onSubmitTracking}
          onSendQuickPrompt={sendTrackingMessage}
        />
      </section>
    ) : (
      <section className="h-full min-h-0 overflow-y-auto">
        <WorkspaceTaskBoard
          tasks={tasks}
          repos={REPOS}
          agents={AGENTS}
          repoFilter={boardRepoFilter}
          onRepoFilterChange={setBoardRepoFilter}
        />
      </section>
    );

  return (
    <DashboardShell
      title={SECTION_META[section].title}
      description={SECTION_META[section].description}
    >
      <div className="h-full min-h-0 overflow-y-auto">
        {pageContent}
      </div>
    </DashboardShell>
  );
}

