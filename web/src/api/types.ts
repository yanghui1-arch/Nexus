export type ApiAgentKind = 'tela' | 'sophie' | 'jules' | 'marc';

export type ApiTaskCategory = 'coding' | 'product discovery';

export type ApiTaskStatus =
  | 'queued'
  | 'running'
  | 'waiting_for_review'
  | 'merged'
  | 'closed'
  | 'failed';

export type ApiWorkspaceStatus = 'idle' | 'running' | 'inactive';

export interface ApiTaskCreateRequest {
  agent_instance_id: string;
  agent: ApiAgentKind;
  question: string;
  external_issue_url?: string | null;
}

export interface ApiTaskConsultRequest {
  message: string;
}

export interface ApiTaskSubmitResponse {
  task_id: string;
  agent_instance_id: string;
  category: ApiTaskCategory;
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
  category: ApiTaskCategory;
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

// Business-level proposal status. `approved` only means human approval happened;
// the actual planning attempt is tracked separately by `latest_planning_run`.
export type ApiProductProposalStatus =
  | 'proposed'
  | 'approved'
  | 'rejected'
  | 'planned'
  | 'completed';

export type ApiFeatureStatus =
  | 'planned'
  | 'in_progress'
  | 'completed'
  | 'closed';

export type ApiFeatureItemStatus =
  | 'pending'
  | 'in_progress'
  | 'completed'
  | 'closed';

export interface ApiProductProposalStatusUpdateRequest {
  status: Extract<ApiProductProposalStatus, 'approved' | 'rejected' | 'planned'>;
}

export interface ApiProductProposal {
  id: string;
  title: string;
  plan_type: string;
  summary: string;
  answer: string;
  project: string | null;
  repo: string | null;
  status: ApiProductProposalStatus;
  source_task_id: string | null;
  latest_planning_run: ApiProposalPlanningRun | null;
  latest_planning_task_exists: boolean | null;
  created_at: string;
  updated_at: string;
}

export type ApiProposalPlanningRunStatus =
  | 'queued'
  | 'running'
  | 'failed'
  | 'completed';

export interface ApiProposalPlanningRun {
  id: string;
  proposal_id: string;
  task_id: string;
  attempt: number;
  // Operational status of one planning attempt for the approved proposal.
  status: ApiProposalPlanningRunStatus;
  error: string | null;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface ApiFeatureItem {
  id: string;
  feature_id: string;
  order_index: number;
  title: string;
  description: string;
  status: ApiFeatureItemStatus;
  task_id: string | null;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface ApiFeature {
  id: string;
  proposal_id: string | null;
  title: string;
  description: string;
  project: string | null;
  status: ApiFeatureStatus;
  created_at: string;
  updated_at: string;
  items: ApiFeatureItem[] | null;
}

export interface ApiWorkspace {
  id: string;
  agent_instance_id: string;
  workspace_key: string;
  github_repo: string | null;
  project: string | null;
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

export interface ApiAgentInstanceUpdateRequest {
  display_name?: string | null;
}

export interface ApiAgentInstanceStatusUpdateRequest {
  is_active: boolean;
}

export interface ApiWorkspaceUpdateRequest {
  github_repo?: string | null;
  project?: string | null;
}

export interface ApiAgentInstance {
  id: string;
  agent: ApiAgentKind;
  client_id: string;
  display_name: string | null;
  expires_at: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  workspace: ApiWorkspace | null;
}

export interface ApiUser {
  id: string;
  github_login: string;
  email: string | null;
  balance: string;
}

export interface ApiRechargeRequest {
  amount: string;
}

export interface ApiPurchaseAgentRequest {
  agent: ApiAgentKind;
}

export interface ApiPurchaseAgentResponse {
  id: string;
  agent_instance_id: string;
  agent: ApiAgentKind;
  price: string;
  balance: string;
  purchased_at: string;
  expires_at: string;
}
