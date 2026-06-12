import type { WorkspaceAgentOption, WorkspaceTaskView } from '@/lib/workspace-task-view';

export const agents: WorkspaceAgentOption[] = [
  { id: 'agent-1', label: 'Tela', subtitle: 'client-a', agent: 'tela', workspaceStatus: 'running', workspaceRepo: 'org/repo', workspaceProject: 'Nexus' },
  { id: 'agent-2', label: 'Sophie', subtitle: 'client-b', agent: 'sophie', workspaceStatus: 'idle', workspaceRepo: null, workspaceProject: null },
];

export function task(overrides: Partial<WorkspaceTaskView> = {}): WorkspaceTaskView {
  return {
    id: 'task-1',
    question: 'Implement observability UI tests',
    category: 'coding',
    repo: 'yanghui1-arch/Nexus',
    project: 'Nexus',
    externalIssueUrl: null,
    externalPullRequestUrl: null,
    status: 'running',
    result: null,
    error: null,
    createdAt: '2026-01-01T09:00:00.000Z',
    updatedAt: '2026-01-01T09:20:00.000Z',
    startedAt: '2026-01-01T09:05:00.000Z',
    finishedAt: null,
    agent: 'tela',
    agentInstanceId: 'agent-1',
    agentLabel: 'Tela',
    modelName: 'gpt-5',
    tokenCount: 12345,
    ...overrides,
  };
}
