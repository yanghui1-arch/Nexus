export type TaskStatus = 'running' | 'waiting' | 'completed' | 'failed' | 'error';

export interface LogEntry {
  timestamp: string;
  level: 'info' | 'warning' | 'error' | 'success';
  message: string;
}

export interface AgentTask {
  id: string;
  title: string;        // What the agent is doing
  status: TaskStatus;
  agentName: string;    // Agent identifier
  agentId: string;
  startTime?: string;
  endTime?: string;
  duration?: number;    // in seconds
  logs: LogEntry[];
  error?: string;
  metadata?: {
    repository?: string;
    branch?: string;
    commit?: string;
    command?: string;
  };
}

export interface Agent {
  id: string;
  name: string;
  status: 'online' | 'offline' | 'busy';
  currentTask?: AgentTask;
  taskQueue: AgentTask[];
  completedTasks: AgentTask[];
}

// Legacy types for backward compatibility
export type StageStatus = TaskStatus;

export interface Stage {
  id: string;
  name: string;
  status: StageStatus;
  startTime?: string;
  endTime?: string;
  duration?: number;
  logs: LogEntry[];
  error?: string;
}

export interface AgentWorkflow {
  id: string;
  name: string;
  status: StageStatus;
  stages: Stage[];
  startTime: string;
  endTime?: string;
  repository: string;
  branch: string;
}
