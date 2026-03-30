import type { Agent, AgentTask } from '@/types/agent';

const now = new Date();

const createLogEntries = (taskName: string, duration: number = 30): AgentTask['logs'] => {
  const entries: AgentTask['logs'] = [];
  const levels: Array<'info' | 'warning' | 'error' | 'success'> = ['info', 'info', 'success', 'info', 'info'];
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

  const stepDuration = duration * 1000 / messages.length;

  for (let i = 0; i < messages.length; i++) {
    entries.push({
      timestamp: new Date(now.getTime() - (messages.length - i) * stepDuration).toISOString(),
      level: levels[i % levels.length],
      message: messages[i],
    });
  }

  return entries;
};

const createTask = (
  id: string,
  title: string,
  status: AgentTask['status'],
  agentName: string,
  offsetMinutes: number,
  duration?: number,
  error?: string
): AgentTask => {
  const baseTime = new Date(now.getTime() - offsetMinutes * 60000);
  const actualDuration = duration || Math.floor(Math.random() * 300) + 60;

  return {
    id,
    title,
    status,
    agentName,
    agentId: agentName.toLowerCase().replace(/\s+/g, '-'),
    startTime: baseTime.toISOString(),
    endTime: status === 'running' || status === 'waiting'
      ? undefined
      : new Date(baseTime.getTime() + actualDuration * 1000).toISOString(),
    duration: status === 'running' || status === 'waiting' ? undefined : actualDuration,
    logs: createLogEntries(title, actualDuration),
    error,
    metadata: {
      repository: 'yanghui1-arch/Nexus',
      branch: ['main', 'feature/auth', 'fix/bug-123'][Math.floor(Math.random() * 3)],
      commit: Math.random().toString(36).substring(2, 10),
      command: `./scripts/${id}.sh`,
    },
  };
};

// Generate mock agents with tasks
export const mockAgents: Agent[] = [
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
      undefined
    ),
    taskQueue: [
      createTask('task-1-2', 'Running unit tests', 'waiting', 'Agent Alpha', 0),
      createTask('task-1-3', 'Deploying to staging', 'waiting', 'Agent Alpha', 0),
    ],
    completedTasks: [
      createTask('task-1-0', 'Checkout repository', 'completed', 'Agent Alpha', 30, 45),
    ],
  },
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
      undefined
    ),
    taskQueue: [
      createTask('task-2-2', 'Code quality checks', 'waiting', 'Agent Beta', 0),
    ],
    completedTasks: [
      createTask('task-2-0', 'Setup build environment', 'completed', 'Agent Beta', 25, 60),
    ],
  },
  {
    id: 'agent-3',
    name: 'Agent Gamma',
    status: 'online',
    currentTask: undefined,
    taskQueue: [
      createTask('task-3-1', 'Security scan', 'waiting', 'Agent Gamma', 0),
      createTask('task-3-2', 'Performance benchmarks', 'waiting', 'Agent Gamma', 0),
    ],
    completedTasks: [
      createTask('task-3-0', 'Install dependencies', 'completed', 'Agent Gamma', 40, 120),
    ],
  },
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
      undefined
    ),
    taskQueue: [],
    completedTasks: [
      createTask('task-4-0', 'Clone repository', 'completed', 'Agent Delta', 15, 30),
    ],
  },
  {
    id: 'agent-5',
    name: 'Agent Epsilon',
    status: 'offline',
    currentTask: undefined,
    taskQueue: [],
    completedTasks: [
      createTask('task-5-0', 'Documentation build', 'completed', 'Agent Epsilon', 60, 180),
      createTask('task-5-1', 'Lint checks', 'completed', 'Agent Epsilon', 57, 90),
    ],
  },
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
      undefined
    ),
    taskQueue: [
      createTask('task-6-2', 'Export test results', 'waiting', 'Agent Zeta', 0),
      createTask('task-6-3', 'Cleanup workspace', 'waiting', 'Agent Zeta', 0),
    ],
    completedTasks: [
      createTask('task-6-0', 'Download test data', 'completed', 'Agent Zeta', 20, 300),
    ],
  },
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
      undefined
    ),
    taskQueue: [],
    completedTasks: [],
  },
  {
    id: 'agent-8',
    name: 'Agent Theta',
    status: 'online',
    currentTask: undefined,
    taskQueue: [
      createTask('task-8-1', 'API compatibility tests', 'waiting', 'Agent Theta', 0),
    ],
    completedTasks: [
      createTask('task-8-0', 'Environment setup', 'completed', 'Agent Theta', 45, 60),
      createTask('task-8-1', 'Dependency resolution', 'completed', 'Agent Theta', 44, 30),
    ],
  },
  // Add some failed tasks
  {
    id: 'agent-9',
    name: 'Agent Iota',
    status: 'online',
    currentTask: undefined,
    taskQueue: [],
    completedTasks: [
      createTask('task-9-0', 'Syntax validation', 'completed', 'Agent Iota', 50, 45),
      createTask('task-9-1', 'Type checking', 'failed', 'Agent Iota', 49, 120, 'Type error in model.py: Invalid type annotation'),
    ],
  },
  {
    id: 'agent-10',
    name: 'Agent Kappa',
    status: 'online',
    currentTask: undefined,
    taskQueue: [],
    completedTasks: [
      createTask('task-10-0', 'Static analysis', 'completed', 'Agent Kappa', 70, 90),
      createTask('task-10-1', 'Memory leak detection', 'error', 'Agent Kappa', 68, 600, 'Process terminated unexpectedly'),
    ],
  },
];

// Helper functions to get tasks by status
export const getRunningTasks = (): AgentTask[] => {
  return mockAgents
    .filter(agent => agent.currentTask && agent.currentTask.status === 'running')
    .map(agent => agent.currentTask!);
};

export const getWaitingTasks = (): AgentTask[] => {
  return mockAgents.flatMap(agent =>
    agent.taskQueue.filter(task => task.status === 'waiting')
  );
};

export const getCompletedTasks = (): AgentTask[] => {
  return mockAgents.flatMap(agent =>
    [...agent.completedTasks].sort((a, b) =>
      new Date(b.endTime || 0).getTime() - new Date(a.endTime || 0).getTime()
    )
  );
};

export const getAllTasks = (): AgentTask[] => {
  return [
    ...getRunningTasks(),
    ...getWaitingTasks(),
    ...getCompletedTasks(),
  ];
};

export const getTaskById = (taskId: string): AgentTask | undefined => {
  for (const agent of mockAgents) {
    if (agent.currentTask?.id === taskId) return agent.currentTask;
    const waiting = agent.taskQueue.find(t => t.id === taskId);
    if (waiting) return waiting;
    const completed = agent.completedTasks.find(t => t.id === taskId);
    if (completed) return completed;
  }
  return undefined;
};

export const getAgentByTaskId = (taskId: string): Agent | undefined => {
  return mockAgents.find(agent =>
    agent.currentTask?.id === taskId ||
    agent.taskQueue.some(t => t.id === taskId) ||
    agent.completedTasks.some(t => t.id === taskId)
  );
};

// Legacy export for backward compatibility
export const mockWorkflows = [];
