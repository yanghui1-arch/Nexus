export type ApiAgentKind = 'tela' | 'sophie' | 'jules' | 'marc' | 'assistant';

export type ApiTaskCategory = 'coding' | 'product discovery' | 'review';

export type ApiTaskStatus =
  | 'queued'
  | 'running'
  | 'waiting_for_review'
  | 'merged'
  | 'closed'
  | 'failed';

export type ApiWorkspaceStatus = 'idle' | 'running' | 'inactive';

export interface ApiTaskRecovery {
  visible: boolean;
  has_checkpoint: boolean;
  checkpoint_summary: string | null;
  failure_summary: string | null;
  recommended_action: string;
  unrecoverable_reasons: string[];
  risk_warnings: string[];
  duplicate_side_effects_confirmation_required: boolean;
  can_retry_from_checkpoint: boolean;
  can_retry_as_new_task: boolean;
}

export interface ApiTaskRetryRequest {
  from_checkpoint: boolean;
  confirm_duplicate_side_effects: boolean;
}

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
  recovery: ApiTaskRecovery | null;
}

export interface ApiTaskExecutionEvent {
  id: string;
  task_id: string;
  event_type: string;
  agent: ApiAgentKind | null;
  message: string | null;
  safe_metadata: Record<string, unknown> | null;
  tokens: number | null;
  model: string | null;
  created_at: string;
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
  | 'failed'
  | 'completed'
  | 'closed';

export interface ApiProductProposalStatusUpdateRequest {
  status: Extract<ApiProductProposalStatus, 'approved' | 'rejected' | 'planned'>;
}

export interface ApiFeatureItemRetryTaskRequest {
  reason?: string | null;
}

export interface ApiFeatureItemRetryTaskResponse {
  feature_item: ApiFeatureItem;
  task: ApiTaskSubmitResponse;
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
