import type { Agent, AgentTask } from '@/types/agent';

const now = new Date();

// ─── Log entries ──────────────────────────────────────────────────────────────

const createLogEntries = (
  taskName: string,
  duration: number = 30,
  hasError = false,
): AgentTask['logs'] => {
  const entries: AgentTask['logs'] = [];

  const baseMessages: Array<{ msg: string; level: AgentTask['logs'][number]['level'] }> = [
    { msg: `Initializing ${taskName}...`,          level: 'info'    },
    { msg: 'Setting up environment...',            level: 'info'    },
    { msg: 'Fetching dependencies...',             level: 'info'    },
    { msg: 'Environment ready',                    level: 'success' },
    { msg: 'Executing task...',                    level: 'info'    },
    { msg: 'Progress: 40%',                        level: 'info'    },
    { msg: 'Progress: 80%',                        level: 'info'    },
    { msg: hasError
        ? 'Unexpected error occurred during execution'
        : 'Task execution completed',              level: hasError ? 'error' : 'success' },
    { msg: hasError
        ? 'Traceback (most recent call last): ...'
        : 'Validating results...',                 level: hasError ? 'error' : 'info'    },
    { msg: hasError
        ? 'AssertionError: Expected value did not match'
        : 'All checks passed',                     level: hasError ? 'error' : 'success' },
    { msg: 'Cleaning up...',                       level: 'info'    },
    { msg: hasError
        ? 'Task failed — see errors above'
        : 'Task finished successfully',            level: hasError ? 'error' : 'success' },
  ];

  const stepDuration = (duration * 1000) / baseMessages.length;
  baseMessages.forEach((m, i) => {
    entries.push({
      timestamp: new Date(now.getTime() - (baseMessages.length - i) * stepDuration).toISOString(),
      level: m.level,
      message: m.msg,
    });
  });

  return entries;
};

// ─── Task factory ─────────────────────────────────────────────────────────────

type Branch = 'main' | 'feature/auth' | 'fix/bug-123' | 'feature/perf' | 'release/v2';

const createTask = (
  id: string,
  title: string,
  status: AgentTask['status'],
  agentName: string,
  offsetMinutes: number,
  duration?: number,
  branch: Branch = 'main',
  error?: string,
): AgentTask => {
  const actualDuration = duration ?? Math.floor(Math.random() * 300) + 60;
  const baseTime = new Date(now.getTime() - offsetMinutes * 60_000);
  const hasError = !!error;

  return {
    id,
    title,
    status,
    agentName,
    agentId: agentName.toLowerCase().replace(/\s+/g, '-'),
    startTime: baseTime.toISOString(),
    endTime:
      status === 'running' || status === 'waiting'
        ? undefined
        : new Date(baseTime.getTime() + actualDuration * 1_000).toISOString(),
    duration: status === 'running' || status === 'waiting' ? undefined : actualDuration,
    logs: createLogEntries(title, actualDuration, hasError),
    error,
    metadata: {
      repository: 'yanghui1-arch/Nexus',
      branch,
      commit: Math.random().toString(36).substring(2, 10),
      command: `./scripts/${id}.sh`,
    },
  };
};

// ─── Mock agents ──────────────────────────────────────────────────────────────
// Every agent intentionally carries tasks in multiple states so all section
// headers (Running / Pending / Merged / Closed / Failed / Error) appear.

export const mockAgents: Agent[] = [
  // ── Agent Alpha ─────────────────────────────────────────────────────────
  {
    id: 'agent-1',
    name: 'Agent Alpha',
    status: 'busy',
    currentTask: createTask(
      'task-1-1',
      'Building Docker image for vLLM inference',
      'running',
      'Agent Alpha',
      5,
      undefined,
      'main',
    ),
    taskQueue: [
      createTask('task-1-2', 'Running unit tests',    'waiting', 'Agent Alpha', 0, undefined, 'feature/auth'),
      createTask('task-1-3', 'Deploying to staging',  'waiting', 'Agent Alpha', 0, undefined, 'feature/auth'),
    ],
    completedTasks: [
      createTask('task-1-0', 'Checkout repository',        'completed', 'Agent Alpha', 30,  45, 'main'),
      createTask('task-1-4', 'Lint source files',          'completed', 'Agent Alpha', 55,  70, 'feature/auth'),
      createTask('task-1-5', 'Publish release artifacts',  'completed', 'Agent Alpha', 80, 200, 'main'),
      createTask('task-1-6', 'Type-check PR diff',         'failed',    'Agent Alpha', 70, 120, 'fix/bug-123',
        'TypeError: Cannot read property "length" of undefined at validator.ts:42'),
    ],
  },

  // ── Agent Beta ──────────────────────────────────────────────────────────
  {
    id: 'agent-2',
    name: 'Agent Beta',
    status: 'busy',
    currentTask: createTask(
      'task-2-1',
      'Running integration tests',
      'running',
      'Agent Beta',
      10,
      undefined,
      'feature/perf',
    ),
    taskQueue: [
      createTask('task-2-2', 'Code quality checks', 'waiting', 'Agent Beta', 0, undefined, 'feature/perf'),
    ],
    completedTasks: [
      createTask('task-2-0', 'Setup build environment', 'completed', 'Agent Beta',  25,  60, 'main'),
      createTask('task-2-3', 'Merge feature/perf',      'completed', 'Agent Beta',  50, 180, 'main'),
      createTask('task-2-4', 'Rollback canary deploy',  'error',     'Agent Beta',  45,  90, 'feature/perf',
        'Process terminated unexpectedly: exit code 137 (OOM)'),
    ],
  },

  // ── Agent Gamma ─────────────────────────────────────────────────────────
  {
    id: 'agent-3',
    name: 'Agent Gamma',
    status: 'online',
    currentTask: undefined,
    taskQueue: [
      createTask('task-3-1', 'Security vulnerability scan', 'waiting', 'Agent Gamma', 0, undefined, 'main'),
      createTask('task-3-2', 'Performance benchmarks',      'waiting', 'Agent Gamma', 0, undefined, 'feature/perf'),
    ],
    completedTasks: [
      createTask('task-3-0', 'Install production deps',   'completed', 'Agent Gamma',  40, 120, 'main'),
      createTask('task-3-3', 'Merge hotfix/auth-patch',   'completed', 'Agent Gamma',  65, 150, 'main'),
      createTask('task-3-4', 'Close stale PR #441',       'completed', 'Agent Gamma',  90,  30, 'fix/bug-123'),
      createTask('task-3-5', 'SAST scan — medium-risk',   'failed',    'Agent Gamma', 100, 240, 'feature/auth',
        'CVE-2024-1234 detected in dependency chain'),
    ],
  },

  // ── Agent Delta ─────────────────────────────────────────────────────────
  {
    id: 'agent-4',
    name: 'Agent Delta',
    status: 'busy',
    currentTask: createTask(
      'task-4-1',
      'Compiling CUDA kernels',
      'running',
      'Agent Delta',
      2,
      undefined,
      'feature/perf',
    ),
    taskQueue: [],
    completedTasks: [
      createTask('task-4-0', 'Clone repository',       'completed', 'Agent Delta', 15,  30, 'main'),
      createTask('task-4-2', 'Publish Python wheel',   'completed', 'Agent Delta', 35, 150, 'main'),
      createTask('task-4-3', 'Merge feature/cuda',     'completed', 'Agent Delta', 60, 200, 'main'),
      createTask('task-4-4', 'GPU memory leak check',  'error',     'Agent Delta', 55, 400, 'feature/perf',
        'CUDA error: device-side assert triggered'),
    ],
  },

  // ── Agent Epsilon (offline) ──────────────────────────────────────────────
  {
    id: 'agent-5',
    name: 'Agent Epsilon',
    status: 'offline',
    currentTask: undefined,
    taskQueue: [],
    completedTasks: [
      createTask('task-5-0', 'Documentation build',    'completed', 'Agent Epsilon',  60, 180, 'main'),
      createTask('task-5-1', 'Lint checks',            'completed', 'Agent Epsilon',  57,  90, 'fix/bug-123'),
      createTask('task-5-2', 'Merge docs update',      'completed', 'Agent Epsilon',  75, 120, 'main'),
      createTask('task-5-3', 'Broken link checker',    'failed',    'Agent Epsilon', 110,  60, 'main',
        '404 detected: /api/v2/reference#deprecated'),
    ],
  },

  // ── Agent Zeta ──────────────────────────────────────────────────────────
  {
    id: 'agent-6',
    name: 'Agent Zeta',
    status: 'busy',
    currentTask: createTask(
      'task-6-1',
      'Running model inference tests',
      'running',
      'Agent Zeta',
      8,
      undefined,
      'release/v2',
    ),
    taskQueue: [
      createTask('task-6-2', 'Export test results',  'waiting', 'Agent Zeta', 0, undefined, 'release/v2'),
      createTask('task-6-3', 'Cleanup workspace',    'waiting', 'Agent Zeta', 0, undefined, 'release/v2'),
    ],
    completedTasks: [
      createTask('task-6-0', 'Download test dataset',       'completed', 'Agent Zeta',  20, 300, 'main'),
      createTask('task-6-4', 'Merge release/v2 candidate',  'completed', 'Agent Zeta',  50, 240, 'main'),
      createTask('task-6-5', 'Close release/v1 branch',     'completed', 'Agent Zeta',  70,  20, 'fix/bug-123'),
    ],
  },

  // ── Agent Eta ───────────────────────────────────────────────────────────
  {
    id: 'agent-7',
    name: 'Agent Eta',
    status: 'busy',
    currentTask: createTask(
      'task-7-1',
      'Packaging Python wheel',
      'running',
      'Agent Eta',
      3,
      undefined,
      'release/v2',
    ),
    taskQueue: [],
    completedTasks: [
      createTask('task-7-0', 'Merge feature/streaming', 'completed', 'Agent Eta',  25, 180, 'main'),
      createTask('task-7-2', 'Close fix/bug-123',        'completed', 'Agent Eta',  45,  15, 'fix/bug-123'),
      createTask('task-7-3', 'Signature verification',   'error',     'Agent Eta',  30,  60, 'release/v2',
        'GPG key not found for release signing'),
    ],
  },

  // ── Agent Theta ─────────────────────────────────────────────────────────
  {
    id: 'agent-8',
    name: 'Agent Theta',
    status: 'online',
    currentTask: undefined,
    taskQueue: [
      createTask('task-8-2', 'API compatibility tests', 'waiting', 'Agent Theta', 0, undefined, 'feature/auth'),
    ],
    completedTasks: [
      createTask('task-8-0', 'Environment setup',        'completed', 'Agent Theta',  45,  60, 'main'),
      createTask('task-8-1', 'Dependency resolution',    'completed', 'Agent Theta',  44,  30, 'main'),
      createTask('task-8-3', 'Merge feature/auth',       'completed', 'Agent Theta',  80, 180, 'main'),
      createTask('task-8-4', 'Auth regression test',     'failed',    'Agent Theta',  75,  90, 'feature/auth',
        'AssertionError: JWT refresh token expiry mismatch'),
    ],
  },

  // ── Agent Iota ──────────────────────────────────────────────────────────
  {
    id: 'agent-9',
    name: 'Agent Iota',
    status: 'online',
    currentTask: undefined,
    taskQueue: [],
    completedTasks: [
      createTask('task-9-0', 'Syntax validation',       'completed', 'Agent Iota',  50,  45, 'main'),
      createTask('task-9-1', 'Type checking',           'failed',    'Agent Iota',  49, 120, 'fix/bug-123',
        'Type error in model.py: Invalid type annotation for parameter `logits`'),
      createTask('task-9-2', 'Merge syntax fixes',      'completed', 'Agent Iota',  90, 150, 'main'),
      createTask('task-9-3', 'Close stale fix/bug-123', 'completed', 'Agent Iota', 100,  10, 'fix/bug-123'),
    ],
  },

  // ── Agent Kappa ─────────────────────────────────────────────────────────
  {
    id: 'agent-10',
    name: 'Agent Kappa',
    status: 'online',
    currentTask: undefined,
    taskQueue: [],
    completedTasks: [
      createTask('task-10-0', 'Static analysis',         'completed', 'Agent Kappa',  70,  90, 'main'),
      createTask('task-10-1', 'Memory leak detection',   'error',     'Agent Kappa',  68, 600, 'feature/perf',
        'Process terminated unexpectedly after 600s (watchdog timeout)'),
      createTask('task-10-2', 'Merge perf optimizations','completed', 'Agent Kappa', 120, 240, 'main'),
      createTask('task-10-3', 'Close feature/perf',      'completed', 'Agent Kappa', 140,  10, 'feature/perf'),
    ],
  },
];

// ─── Selector helpers ─────────────────────────────────────────────────────────

export const getRunningTasks = (): AgentTask[] =>
  mockAgents
    .filter(a => a.currentTask?.status === 'running')
    .map(a => a.currentTask!);

export const getWaitingTasks = (): AgentTask[] =>
  mockAgents.flatMap(a => a.taskQueue.filter(t => t.status === 'waiting'));

export const getCompletedTasks = (): AgentTask[] =>
  mockAgents.flatMap(a =>
    [...a.completedTasks].sort(
      (x, y) =>
        new Date(y.endTime ?? 0).getTime() - new Date(x.endTime ?? 0).getTime()
    )
  );

export const getAllTasks = (): AgentTask[] => [
  ...getRunningTasks(),
  ...getWaitingTasks(),
  ...getCompletedTasks(),
];

export const getTaskById = (taskId: string): AgentTask | undefined => {
  for (const agent of mockAgents) {
    if (agent.currentTask?.id === taskId) return agent.currentTask;
    const queued = agent.taskQueue.find(t => t.id === taskId);
    if (queued) return queued;
    const done = agent.completedTasks.find(t => t.id === taskId);
    if (done) return done;
  }
  return undefined;
};

export const getAgentByTaskId = (taskId: string): Agent | undefined =>
  mockAgents.find(
    a =>
      a.currentTask?.id === taskId ||
      a.taskQueue.some(t => t.id === taskId) ||
      a.completedTasks.some(t => t.id === taskId)
  );

// Legacy export for backward compatibility
export const mockWorkflows = [];
