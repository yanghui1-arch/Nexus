import { apiRequest, buildApiPath } from '@/api/client';
import type {
  ApiReviewQueueItem,
  ApiTask,
  ApiTaskConsultRequest,
  ApiTaskConsultResponse,
  ApiTaskCreateRequest,
  ApiTaskMessage,
  ApiTaskReviewSummary,
  ApiTaskStatus,
  ApiTaskStatusUpdateRequest,
  ApiTaskSubmitResponse,
  ApiTaskWorkItem,
  ApiVirtualPullRequest,
  ApiVirtualPullRequestComment,
  ApiVirtualPullRequestCommentCreateRequest,
  ApiVirtualPullRequestDetail,
  ApiVirtualPullRequestDiff,
  ApiVirtualPullRequestReview,
  ApiVirtualPullRequestReviewRequest,
  ApiVirtualPullRequestThread,
  ApiVirtualPullRequestThreadCreateRequest,
  ApiVirtualPullRequestThreadUpdateRequest,
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

export function listTaskReviewQueue(limit = 200): Promise<ApiReviewQueueItem[]> {
  return apiRequest<ApiReviewQueueItem[]>(buildApiPath('/v1/tasks/review-queue', { limit }));
}

export function getTask(taskId: string): Promise<ApiTask> {
  return apiRequest<ApiTask>(`/v1/tasks/${taskId}`);
}

export function getTaskReviewSummary(taskId: string): Promise<ApiTaskReviewSummary> {
  return apiRequest<ApiTaskReviewSummary>(`/v1/tasks/${taskId}/review-summary`);
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

export function getTaskVirtualPullRequest(
  taskId: string,
  virtualPullRequestId: string,
): Promise<ApiVirtualPullRequestDetail> {
  return apiRequest<ApiVirtualPullRequestDetail>(
    `/v1/tasks/${taskId}/virtual-prs/${virtualPullRequestId}`,
  );
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

export function createTaskVirtualPullRequestThread(
  taskId: string,
  virtualPullRequestId: string,
  payload: ApiVirtualPullRequestThreadCreateRequest,
): Promise<ApiVirtualPullRequestThread> {
  return apiRequest<ApiVirtualPullRequestThread>(
    `/v1/tasks/${taskId}/virtual-prs/${virtualPullRequestId}/threads`,
    {
      method: 'POST',
      body: JSON.stringify(payload),
    },
  );
}

export function createTaskVirtualPullRequestComment(
  taskId: string,
  virtualPullRequestId: string,
  threadId: string,
  payload: ApiVirtualPullRequestCommentCreateRequest,
): Promise<ApiVirtualPullRequestComment> {
  return apiRequest<ApiVirtualPullRequestComment>(
    `/v1/tasks/${taskId}/virtual-prs/${virtualPullRequestId}/threads/${threadId}/comments`,
    {
      method: 'POST',
      body: JSON.stringify(payload),
    },
  );
}

export function updateTaskVirtualPullRequestThread(
  taskId: string,
  virtualPullRequestId: string,
  threadId: string,
  payload: ApiVirtualPullRequestThreadUpdateRequest,
): Promise<ApiVirtualPullRequestThread> {
  return apiRequest<ApiVirtualPullRequestThread>(
    `/v1/tasks/${taskId}/virtual-prs/${virtualPullRequestId}/threads/${threadId}`,
    {
      method: 'PATCH',
      body: JSON.stringify(payload),
    },
  );
}
