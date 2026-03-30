export type StageStatus = 'pending' | 'running' | 'completed' | 'failed' | 'error';

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

export interface LogEntry {
  timestamp: string;
  level: 'info' | 'warning' | 'error' | 'success';
  message: string;
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
