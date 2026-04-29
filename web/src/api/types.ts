export type ApiAgentKind = 'tela' | 'sophie';

export type ApiTaskStatus =
  | 'queued'
  | 'running'
  | 'waiting'
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

export type ApiTaskWorkItemStatus =
  | 'pending'
  | 'running'
  | 'ready_for_review'
  | 'approved'
  | 'changes_requested';

export interface ApiTaskWorkItem {
  id: string;
  task_id: string;
  order_index: number;
  title: string;
  description: string;
  status: ApiTaskWorkItemStatus;
  summary: string | null;
  base_commit: string | null;
  head_commit: string | null;
  local_path: string | null;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export type ApiVirtualPullRequestStatus =
  | 'ready_for_review'
  | 'approved'
  | 'changes_requested';

export interface ApiVirtualPullRequest {
  id: string;
  task_id: string;
  work_item_id: string;
  status: ApiVirtualPullRequestStatus;
  base_commit: string;
  head_commit: string;
  summary: string;
  changed_files: string[];
  additions: number;
  deletions: number;
  created_at: string;
  updated_at: string;
}

export interface ApiVirtualPullRequestDiff {
  id: string;
  task_id: string;
  work_item_id: string;
  base_commit: string;
  head_commit: string;
  diff: string;
}

export interface ApiVirtualPullRequestReviewRequest {
  decision: 'approved' | 'changes_requested';
  reviewer?: string | null;
  comment?: string | null;
}

export interface ApiVirtualPullRequestReview {
  id: string;
  task_id: string;
  virtual_pr_id: string;
  decision: 'approved' | 'changes_requested';
  reviewer: string | null;
  comment: string | null;
  created_at: string;
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
