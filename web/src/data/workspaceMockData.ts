export type WorkspaceUrgency = 'critical' | 'high' | 'normal';
export type WorkspaceStatus = 'queued' | 'in_progress' | 'blocked' | 'done';

export type AgentProfile = {
  id: string;
  name: string;
  role: string;
};

export type RepoProfile = {
  id: string;
  name: string;
  fullName: string;
};

export type WorkspaceTask = {
  id: string;
  title: string;
  repoId: string;
  agentId: string;
  urgency: WorkspaceUrgency;
  status: WorkspaceStatus;
  progress: number;
  notes?: string;
  createdAt: string;
};

export type WorkspaceMessage = {
  id: string;
  role: 'user' | 'agent' | 'system';
  text: string;
  time: string;
};

const minutesAgo = (minutes: number) => new Date(Date.now() - minutes * 60_000).toISOString();

export const REPOS: RepoProfile[] = [
  { id: 'nexus-core', name: 'Nexus Core', fullName: 'yanghui1-arch/Nexus' },
  { id: 'nexus-web', name: 'Nexus Web', fullName: 'yanghui1-arch/Nexus-Web' },
  { id: 'ops-bot', name: 'Ops Bot', fullName: 'yanghui1-arch/Nexus-Ops' },
  { id: 'agent-tools', name: 'Agent Tools', fullName: 'yanghui1-arch/Agent-Tools' },
];

export const AGENTS: AgentProfile[] = [
  { id: 'sophie-1', name: 'Sophie-1', role: 'UI delivery' },
  { id: 'tela-1', name: 'Tela-1', role: 'Backend rescue' },
  { id: 'sophie-2', name: 'Sophie-2', role: 'QA and polish' },
  { id: 'tela-2', name: 'Tela-2', role: 'Infra support' },
];

export const INITIAL_TASKS: WorkspaceTask[] = [
  {
    id: 'ws-101',
    title: 'Hotfix API timeout on payment confirmation',
    repoId: 'nexus-core',
    agentId: 'tela-1',
    urgency: 'critical',
    status: 'in_progress',
    progress: 64,
    notes: 'Timeout spikes after deploy 84.2',
    createdAt: minutesAgo(18),
  },
  {
    id: 'ws-102',
    title: 'Patch task board sorting regression',
    repoId: 'nexus-web',
    agentId: 'sophie-1',
    urgency: 'high',
    status: 'queued',
    progress: 14,
    createdAt: minutesAgo(36),
  },
  {
    id: 'ws-103',
    title: 'Recover missing worker logs in nightly jobs',
    repoId: 'ops-bot',
    agentId: 'tela-2',
    urgency: 'high',
    status: 'blocked',
    progress: 36,
    notes: 'Waiting for storage policy approval.',
    createdAt: minutesAgo(51),
  },
  {
    id: 'ws-104',
    title: 'Improve command input helper readability',
    repoId: 'agent-tools',
    agentId: 'sophie-2',
    urgency: 'normal',
    status: 'done',
    progress: 100,
    createdAt: minutesAgo(87),
  },
];

export const INITIAL_TRACKING: Record<string, WorkspaceMessage[]> = {
  'sophie-1': [{ id: 'm-1001', role: 'agent', text: 'Tracking update: UI patch is queued and ready for execution handoff.', time: minutesAgo(14) }],
  'sophie-2': [{ id: 'm-1002', role: 'agent', text: 'Tracking update: QA slot is open, waiting for next active task.', time: minutesAgo(22) }],
  'tela-1': [{ id: 'm-1003', role: 'agent', text: 'Tracking update: retry saturation identified, mitigation patch under verification.', time: minutesAgo(8) }],
  'tela-2': [{ id: 'm-1004', role: 'agent', text: 'Tracking update: task is blocked by storage policy dependency.', time: minutesAgo(6) }],
};
