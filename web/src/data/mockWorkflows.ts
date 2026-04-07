import type { Agent, AgentTask, AgentType, Project } from '@/types/agent';

const now = new Date();

const createLogEntries = (taskName: string, duration: number = 30): AgentTask['logs'] => {
  const messages = [
    `Initializing ${taskName}...`,
    'Setting up environment...',
    'Environment ready',
    'Executing task...',
    'Task execution completed',
    'Validating results...',
    'Cleaning up...',
    'Task finished successfully',
  ];
  const levels: Array<'info' | 'warning' | 'error' | 'success'> = ['info', 'info', 'success', 'info', 'info'];
  const step = duration * 1000 / messages.length;
  return messages.map((message, i) => ({
    timestamp: new Date(now.getTime() - (messages.length - i) * step).toISOString(),
    level: levels[i % levels.length],
    message,
  }));
};

const createTask = (
  id: string,
  title: string,
  status: AgentTask['status'],
  agentType: AgentType,
  agentName: string,
  repo: string,
  offsetMinutes: number,
  duration?: number,
  error?: string,
  prUrl?: string,
): AgentTask => {
  const baseTime = new Date(now.getTime() - offsetMinutes * 60000);
  const actualDuration = duration ?? (Math.floor(Math.random() * 300) + 60);
  const isActive = status === 'running' || status === 'waiting';
  const branches = ['main', 'feature/auth', 'fix/bug-123', 'feat/api-v2'];

  return {
    id,
    title,
    status,
    agentType,
    agentName,
    agentId: agentName.toLowerCase().replace(/\s+/g, '-'),
    startTime: baseTime.toISOString(),
    endTime: isActive ? undefined : new Date(baseTime.getTime() + actualDuration * 1000).toISOString(),
    duration: isActive ? undefined : actualDuration,
    logs: createLogEntries(title, actualDuration),
    error,
    prUrl,
    metadata: {
      repository: repo,
      branch: branches[Math.floor(Math.random() * branches.length)],
      commit: Math.random().toString(36).substring(2, 10),
      command: `./scripts/${id}.sh`,
    },
  };
};

// ─── Project: Nexus (4 agents — busy, mixed Sophie + Tela) ────────────────────

const nexusRepo = 'yanghui1-arch/Nexus';

const nexusAgents: Agent[] = [
  {
    id: 'sophie-1', name: 'Sophie-1', agentType: 'Sophie', status: 'busy',
    currentTask: createTask('s1-t1', 'Implement React dashboard component', 'running', 'Sophie', 'Sophie-1', nexusRepo, 5),
    taskQueue: [
      createTask('s1-t2', 'Add unit tests for dashboard', 'waiting', 'Sophie', 'Sophie-1', nexusRepo, 0),
      createTask('s1-t3', 'Update Tailwind config for new design tokens', 'waiting', 'Sophie', 'Sophie-1', nexusRepo, 0),
    ],
    completedTasks: [
      createTask('s1-t0', 'Fix TypeScript errors in auth module', 'merged', 'Sophie', 'Sophie-1', nexusRepo, 45, 120, undefined, 'https://github.com/yanghui1-arch/Nexus/pull/14'),
    ],
  },
  {
    id: 'sophie-2', name: 'Sophie-2', agentType: 'Sophie', status: 'busy',
    currentTask: createTask('s2-t1', 'Refactor API client with React Query', 'running', 'Sophie', 'Sophie-2', nexusRepo, 12),
    taskQueue: [
      createTask('s2-t2', 'Write Storybook stories for Button component', 'waiting', 'Sophie', 'Sophie-2', nexusRepo, 0),
    ],
    completedTasks: [
      createTask('s2-t0', 'Migrate pages to new router', 'merged', 'Sophie', 'Sophie-2', nexusRepo, 90, 300, undefined, 'https://github.com/yanghui1-arch/Nexus/pull/12'),
      createTask('s2-tc', 'Experiment: SSR rendering approach', 'closed', 'Sophie', 'Sophie-2', nexusRepo, 200, 180),
    ],
  },
  {
    id: 'tela-1', name: 'Tela-1', agentType: 'Tela', status: 'busy',
    currentTask: createTask('t1-t1', 'Implement GitHub fork polling in _ensure_fork', 'running', 'Tela', 'Tela-1', nexusRepo, 3),
    taskQueue: [
      createTask('t1-t2', 'Add retry logic to sandbox pool manager', 'waiting', 'Tela', 'Tela-1', nexusRepo, 0),
    ],
    completedTasks: [
      createTask('t1-t0', 'Refactor agent base class compact method', 'merged', 'Tela', 'Tela-1', nexusRepo, 30, 180, undefined, 'https://github.com/yanghui1-arch/Nexus/pull/20'),
    ],
  },
  {
    id: 'tela-2', name: 'Tela-2', agentType: 'Tela', status: 'busy',
    currentTask: createTask('t2-t1', 'Write pytest suite for sandbox tools', 'running', 'Tela', 'Tela-2', nexusRepo, 8),
    taskQueue: [
      createTask('t2-t2', 'Profile memory usage in SandboxPoolManager', 'waiting', 'Tela', 'Tela-2', nexusRepo, 0),
      createTask('t2-t3', 'Add structured logging to agent steps', 'waiting', 'Tela', 'Tela-2', nexusRepo, 0),
    ],
    completedTasks: [
      createTask('t2-t0', 'Fix SHA-256 fingerprint for repo reuse', 'merged', 'Tela', 'Tela-2', nexusRepo, 50, 240, undefined, 'https://github.com/yanghui1-arch/Nexus/pull/19'),
    ],
  },
];

// ─── Project: Nexus-Docs (3 agents — idle, pending tasks) ─────────────────────

const docsRepo = 'yanghui1-arch/Nexus-Docs';

const docsAgents: Agent[] = [
  {
    id: 'sophie-3', name: 'Sophie-3', agentType: 'Sophie', status: 'online',
    currentTask: undefined,
    taskQueue: [
      createTask('s3-t1', 'Implement dark mode toggle', 'waiting', 'Sophie', 'Sophie-3', docsRepo, 0),
      createTask('s3-t2', 'Write component API docs page', 'waiting', 'Sophie', 'Sophie-3', docsRepo, 0),
    ],
    completedTasks: [
      createTask('s3-t0', 'Add accessibility attributes to modals', 'merged', 'Sophie', 'Sophie-3', docsRepo, 120, 90, undefined, 'https://github.com/yanghui1-arch/Nexus-Docs/pull/8'),
      createTask('s3-f', 'Integrate WebSocket live updates', 'failed', 'Sophie', 'Sophie-3', docsRepo, 60, 240, 'WebSocket connection refused: port 8080 unavailable'),
    ],
  },
  {
    id: 'tela-3', name: 'Tela-3', agentType: 'Tela', status: 'online',
    currentTask: undefined,
    taskQueue: [
      createTask('t3-t1', 'Implement token refresh for GitHub auth', 'waiting', 'Tela', 'Tela-3', docsRepo, 0),
    ],
    completedTasks: [
      createTask('t3-t0', 'Add httpx retry middleware', 'merged', 'Tela', 'Tela-3', docsRepo, 100, 150, undefined, 'https://github.com/yanghui1-arch/Nexus-Docs/pull/6'),
      createTask('t3-tc', 'Spike: replace httpx with aiohttp', 'closed', 'Tela', 'Tela-3', docsRepo, 150, 90),
      createTask('t3-f', 'Migrate to pydantic v2 validators', 'failed', 'Tela', 'Tela-3', docsRepo, 70, 300, 'ValidationError: 14 schema incompatibilities found'),
    ],
  },
  {
    id: 'sophie-4', name: 'Sophie-4', agentType: 'Sophie', status: 'online',
    currentTask: undefined,
    taskQueue: [],
    completedTasks: [
      createTask('s4-t0', 'Build pipeline overview page', 'merged', 'Sophie', 'Sophie-4', docsRepo, 180, 420, undefined, 'https://github.com/yanghui1-arch/Nexus-Docs/pull/5'),
      createTask('s4-t1', 'E2E tests with Playwright', 'closed', 'Sophie', 'Sophie-4', docsRepo, 240, 600),
      createTask('s4-f', 'Canvas rendering optimization', 'error', 'Sophie', 'Sophie-4', docsRepo, 300, 180, 'Process terminated: out of memory'),
    ],
  },
];

// ─── Project: vLLM-Analysis (2 agents — mostly done) ──────────────────────────

const vllmRepo = 'yanghui1-arch/vLLM-Analysis';

const vllmAgents: Agent[] = [
  {
    id: 'tela-4', name: 'Tela-4', agentType: 'Tela', status: 'busy',
    currentTask: createTask('t4-t1', 'Run inference benchmarks on A100 cluster', 'running', 'Tela', 'Tela-4', vllmRepo, 15),
    taskQueue: [
      createTask('t4-t2', 'Generate latency report from profiler output', 'waiting', 'Tela', 'Tela-4', vllmRepo, 0),
    ],
    completedTasks: [
      createTask('t4-t0', 'Implement sandbox Docker cleanup cron', 'merged', 'Tela', 'Tela-4', vllmRepo, 200, 360, undefined, 'https://github.com/yanghui1-arch/vLLM-Analysis/pull/4'),
      createTask('t4-m1', 'Parse multi-file diff for PR review tool', 'merged', 'Tela', 'Tela-4', vllmRepo, 260, 420, undefined, 'https://github.com/yanghui1-arch/vLLM-Analysis/pull/3'),
      createTask('t4-f', 'Docker-in-Docker GPU passthrough', 'error', 'Tela', 'Tela-4', vllmRepo, 320, 900, 'CUDA runtime error: device not found'),
    ],
  },
  {
    id: 'tela-5', name: 'Tela-5', agentType: 'Tela', status: 'online',
    currentTask: undefined,
    taskQueue: [
      createTask('t5-t1', 'Summarise token throughput across model sizes', 'waiting', 'Tela', 'Tela-5', vllmRepo, 0),
    ],
    completedTasks: [
      createTask('t5-t0', 'Scrape vLLM benchmark results from CI logs', 'merged', 'Tela', 'Tela-5', vllmRepo, 100, 270, undefined, 'https://github.com/yanghui1-arch/vLLM-Analysis/pull/2'),
      createTask('t5-tc', 'Compare TensorRT-LLM vs vLLM throughput', 'closed', 'Tela', 'Tela-5', vllmRepo, 160, 540),
    ],
  },
];

// ─── Projects ──────────────────────────────────────────────────────────────────

export const mockProjects: Project[] = [
  {
    id: 'nexus',
    name: 'Nexus',
    description: 'Core platform — web UI and Python backend',
    repo: nexusRepo,
    agents: nexusAgents,
  },
  {
    id: 'nexus-docs',
    name: 'Nexus-Docs',
    description: 'Documentation site and component library',
    repo: docsRepo,
    agents: docsAgents,
  },
  {
    id: 'vllm-analysis',
    name: 'vLLM-Analysis',
    description: 'Benchmarking and performance analysis for vLLM',
    repo: vllmRepo,
    agents: vllmAgents,
  },
];

// ─── Flat helpers ──────────────────────────────────────────────────────────────

export const mockAgents: Agent[] = mockProjects.flatMap(p => p.agents);

export function getAgentTasks(agent: Agent): AgentTask[] {
  const tasks: AgentTask[] = [];
  if (agent.currentTask) tasks.push(agent.currentTask);
  tasks.push(...agent.taskQueue, ...agent.completedTasks);
  return tasks;
}

export function getProjectTasks(project: Project): AgentTask[] {
  return project.agents.flatMap(getAgentTasks);
}

export const getTaskById = (taskId: string): AgentTask | undefined => {
  for (const agent of mockAgents) {
    if (agent.currentTask?.id === taskId) return agent.currentTask;
    const q = agent.taskQueue.find(t => t.id === taskId);
    if (q) return q;
    const c = agent.completedTasks.find(t => t.id === taskId);
    if (c) return c;
  }
  return undefined;
};

export const getProjectByTaskId = (taskId: string): Project | undefined =>
  mockProjects.find(p => p.agents.some(a =>
    a.currentTask?.id === taskId ||
    a.taskQueue.some(t => t.id === taskId) ||
    a.completedTasks.some(t => t.id === taskId)
  ));

// Legacy
export const mockWorkflows = [];
