export type ApiAgentKind = 'tela' | 'sophie';

export type ApiTaskStatus =
  | 'queued'
  | 'running'
  | 'waiting_for_merge'
  | 'merged'
  | 'closed'
  | 'failed';

export type ApiWorkspaceStatus = 'idle' | 'running' | 'inactive';

export interface ApiTaskCreateRequest {
  agent_instance_id: string;
  agent: ApiAgentKind;
  question: string;
  repo: string;
  project?: string | null;
}

export interface ApiTaskConsultRequest {
  message: string;
}

export interface ApiTaskSubmitResponse {
  task_id: string;
  agent_instance_id: string;
  status: ApiTaskStatus;
}

export interface ApiTaskConsultResponse {
  task_id: string;
  status: ApiTaskStatus;
  reply: string;
  timestamp: string;
}

export interface ApiTaskStatusUpdateRequest {
  status: Extract<ApiTaskStatus, 'merged' | 'closed'>;
}

export interface ApiTask {
  id: string;
  agent: ApiAgentKind;
  agent_instance_id: string;
  question: string;
  repo: string | null;
  project: string | null;
  status: ApiTaskStatus;
  result: string | null;
  error: string | null;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface ApiTaskMessage {
  timestamp: string;
  status: string;
  description: string | null;
  data: Record<string, unknown> | null;
  meta: Record<string, unknown> | null;
}

export interface ApiWorkspace {
  id: string;
  agent_instance_id: string;
  workspace_key: string;
  github_repo: string | null;
  docker_container_id: string | null;
  docker_volume_name: string | null;
  status: ApiWorkspaceStatus;
  last_used_at: string;
  created_at: string;
  updated_at: string;
}

export interface ApiAgentInstanceCreateRequest {
  agent: ApiAgentKind;
  client_id: string;
  display_name?: string | null;
  is_active?: boolean;
}

export interface ApiAgentInstanceStatusUpdateRequest {
  is_active: boolean;
}

export interface ApiAgentInstance {
  id: string;
  agent: ApiAgentKind;
  client_id: string;
  display_name: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  workspace: ApiWorkspace | null;
}