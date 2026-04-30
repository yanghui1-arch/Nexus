export type TaskStatus = 'running' | 'waiting_for_review' | 'merged' | 'closed' | 'failed' | 'error';
export type AgentType = 'Tela' | 'Sophie';

export interface LogEntry {
  timestamp: string;
  level: 'info' | 'warning' | 'error' | 'success';
  message: string;
}

export interface AgentTask {
  id: string;
  title: string;        // What the agent is doing
  status: TaskStatus;
  agentType: AgentType; // Which agent handles this task
  agentName: string;    // Agent identifier
  agentId: string;
  startTime?: string;
  endTime?: string;
  duration?: number;    // in seconds
  logs: LogEntry[];
  error?: string;
  prUrl?: string;       // GitHub PR URL if applicable
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
  agentType: AgentType;
  status: 'online' | 'offline' | 'busy';
  currentTask?: AgentTask;
  taskQueue: AgentTask[];
  completedTasks: AgentTask[];
}

export interface Project {
  id: string;
  name: string;
  description: string;
  repo: string;        // e.g. "yanghui1-arch/Nexus"
  agents: Agent[];
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
