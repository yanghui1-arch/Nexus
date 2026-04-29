import { apiRequest, buildApiPath } from '@/api/client';
import type {
  ApiTask,
  ApiTaskConsultRequest,
  ApiTaskConsultResponse,
  ApiTaskCreateRequest,
  ApiTaskMessage,
  ApiTaskStatus,
  ApiTaskStatusUpdateRequest,
  ApiTaskSubmitResponse,
  ApiTaskWorkItem,
  ApiVirtualPullRequest,
  ApiVirtualPullRequestDiff,
  ApiVirtualPullRequestReview,
  ApiVirtualPullRequestReviewRequest,
} from '@/api/types';

export type ListTasksParams = {
  agent_instance_id?: string;
  status?: ApiTaskStatus;
  repo?: string;
  project?: string;
  limit?: number;
};

export function listTasks(params: ListTasksParams = {}): Promise<ApiTask[]> {
  return apiRequest<ApiTask[]>(buildApiPath('/v1/tasks', params));
}

export function getTask(taskId: string): Promise<ApiTask> {
  return apiRequest<ApiTask>(`/v1/tasks/${taskId}`);
}

export function createTask(
  payload: ApiTaskCreateRequest,
): Promise<ApiTaskSubmitResponse> {
  return apiRequest<ApiTaskSubmitResponse>('/v1/tasks', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function consultTask(
  taskId: string,
  payload: ApiTaskConsultRequest,
): Promise<ApiTaskConsultResponse> {
  return apiRequest<ApiTaskConsultResponse>(`/v1/tasks/${taskId}/consult`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function updateTaskStatus(
  taskId: string,
  payload: ApiTaskStatusUpdateRequest,
): Promise<ApiTask> {
  return apiRequest<ApiTask>(`/v1/tasks/${taskId}/status`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export function getTaskMessages(
  taskId: string,
  limit = 200,
): Promise<ApiTaskMessage[]> {
  return apiRequest<ApiTaskMessage[]>(
    buildApiPath(`/v1/tasks/${taskId}/messages`, { limit }),
  );
}

export function getTaskWorkItems(taskId: string): Promise<ApiTaskWorkItem[]> {
  return apiRequest<ApiTaskWorkItem[]>(`/v1/tasks/${taskId}/work-items`);
}

export function getTaskVirtualPullRequests(
  taskId: string,
): Promise<ApiVirtualPullRequest[]> {
  return apiRequest<ApiVirtualPullRequest[]>(`/v1/tasks/${taskId}/virtual-prs`);
}

export function getTaskVirtualPullRequestDiff(
  taskId: string,
  virtualPullRequestId: string,
): Promise<ApiVirtualPullRequestDiff> {
  return apiRequest<ApiVirtualPullRequestDiff>(
    `/v1/tasks/${taskId}/virtual-prs/${virtualPullRequestId}/diff`,
  );
}

export function reviewTaskVirtualPullRequest(
  taskId: string,
  virtualPullRequestId: string,
  payload: ApiVirtualPullRequestReviewRequest,
): Promise<ApiVirtualPullRequestReview> {
  return apiRequest<ApiVirtualPullRequestReview>(
    `/v1/tasks/${taskId}/virtual-prs/${virtualPullRequestId}/review`,
    {
      method: 'PATCH',
      body: JSON.stringify(payload),
    },
  );
}
