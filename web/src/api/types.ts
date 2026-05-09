export type ApiAgentKind = 'tela' | 'sophie';

export type ApiTaskStatus =
  | 'queued'
  | 'running'
  | 'waiting_for_review'
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
  external_issue_url?: string | null;
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

export interface ApiTask {
  id: string;
  agent: ApiAgentKind;
  agent_instance_id: string;
  question: string;
  repo: string | null;
  project: string | null;
  external_issue_url: string | null;
  external_pull_request_url: string | null;
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

export interface ApiUser {
  id: string;
  github_login: string;
  email: string | null;
  balance_cents: number;
}

export interface ApiRechargeRequest {
  amount_cents: number;
}

export interface ApiPurchaseAgentRequest {
  agent: ApiAgentKind;
}

export interface ApiPurchaseAgentResponse {
  id: string;
  agent: ApiAgentKind;
  price_cents: number;
  balance_cents: number;
  purchased_at: string;
  expires_at: string;
}
