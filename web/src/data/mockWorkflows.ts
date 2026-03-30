import type { AgentWorkflow, Stage } from '@/types/agent';

const now = new Date();

const createLogEntries = (stageName: string) => [
  {
    timestamp: new Date(now.getTime() - 5000).toISOString(),
    level: 'info' as const,
    message: `Starting ${stageName} stage...`,
  },
  {
    timestamp: new Date(now.getTime() - 4000).toISOString(),
    level: 'info' as const,
    message: 'Initializing environment...',
  },
  {
    timestamp: new Date(now.getTime() - 3000).toISOString(),
    level: 'success' as const,
    message: 'Environment ready',
  },
  {
    timestamp: new Date(now.getTime() - 2000).toISOString(),
    level: 'info' as const,
    message: 'Processing tasks...',
  },
  {
    timestamp: new Date(now.getTime() - 1000).toISOString(),
    level: 'info' as const,
    message: 'Validating results...',
  },
];

const createStage = (
  id: string,
  name: string,
  status: Stage['status'],
  offsetMinutes: number,
  duration?: number,
  error?: string
): Stage => {
  const baseTime = new Date(now.getTime() - offsetMinutes * 60000);
  return {
    id,
    name,
    status,
    startTime: baseTime.toISOString(),
    endTime: status === 'running' || status === 'pending' 
      ? undefined 
      : new Date(baseTime.getTime() + (duration || 30) * 1000).toISOString(),
    duration: duration || 30,
    logs: createLogEntries(name),
    error,
  };
};

export const mockWorkflows: AgentWorkflow[] = [
  {
    id: 'workflow-1',
    name: 'Feature Branch Build #124',
    status: 'running',
    repository: 'yanghui1-arch/Nexus',
    branch: 'feature/user-authentication',
    startTime: new Date(now.getTime() - 15 * 60000).toISOString(),
    stages: [
      createStage('init', 'Init', 'completed', 15, 45),
      createStage('github', 'GitHub Operations', 'completed', 14, 120),
      createStage('work', 'Work', 'completed', 12, 300),
      createStage('git', 'Git Operations', 'running', 7, undefined),
      createStage('finish', 'Finish', 'pending', 0),
    ],
  },
  {
    id: 'workflow-2',
    name: 'Main Branch Deploy #523',
    status: 'completed',
    repository: 'yanghui1-arch/Nexus',
    branch: 'main',
    startTime: new Date(now.getTime() - 45 * 60000).toISOString(),
    endTime: new Date(now.getTime() - 30 * 60000).toISOString(),
    stages: [
      createStage('init', 'Init', 'completed', 45, 60),
      createStage('github', 'GitHub Operations', 'completed', 44, 180),
      createStage('work', 'Work', 'completed', 41, 600),
      createStage('git', 'Git Operations', 'completed', 31, 120),
      createStage('finish', 'Finish', 'completed', 29, 30),
    ],
  },
  {
    id: 'workflow-3',
    name: 'Bug Fix Build #125',
    status: 'failed',
    repository: 'yanghui1-arch/Nexus',
    branch: 'fix/navigation-issue',
    startTime: new Date(now.getTime() - 60 * 60000).toISOString(),
    endTime: new Date(now.getTime() - 55 * 60000).toISOString(),
    stages: [
      createStage('init', 'Init', 'completed', 60, 50),
      createStage('github', 'GitHub Operations', 'completed', 59, 150),
      createStage('work', 'Work', 'failed', 56, 180, 'Tests failed: Component rendering issue in Navigation.test.tsx'),
      createStage('git', 'Git Operations', 'pending', 0),
      createStage('finish', 'Finish', 'pending', 0),
    ],
  },
  {
    id: 'workflow-4',
    name: 'Hotfix Deploy #524',
    status: 'error',
    repository: 'yanghui1-arch/Nexus',
    branch: 'hotfix/security-patch',
    startTime: new Date(now.getTime() - 90 * 60000).toISOString(),
    endTime: new Date(now.getTime() - 85 * 60000).toISOString(),
    stages: [
      createStage('init', 'Init', 'completed', 90, 40),
      createStage('github', 'GitHub Operations', 'error', 89, 100, 'GitHub API rate limit exceeded'),
      createStage('work', 'Work', 'pending', 0),
      createStage('git', 'Git Operations', 'pending', 0),
      createStage('finish', 'Finish', 'pending', 0),
    ],
  },
  {
    id: 'workflow-5',
    name: 'Documentation Update #42',
    status: 'running',
    repository: 'yanghui1-arch/Nexus',
    branch: 'docs/api-reference',
    startTime: new Date(now.getTime() - 5 * 60000).toISOString(),
    stages: [
      createStage('init', 'Init', 'completed', 5, 30),
      createStage('github', 'GitHub Operations', 'running', 4, undefined),
      createStage('work', 'Work', 'pending', 0),
      createStage('git', 'Git Operations', 'pending', 0),
      createStage('finish', 'Finish', 'pending', 0),
    ],
  },
];
