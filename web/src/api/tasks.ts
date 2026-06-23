import { apiRequest, buildApiPath } from '@/api/client';
import type {
  ApiTask,
  ApiTaskConsultRequest,
  ApiTaskConsultResponse,
  ApiTaskCreateRequest,
  ApiTaskRetryRequest,
  ApiTaskExecutionEvent,
  ApiTaskCategory,
  ApiTaskStatus,
  ApiTaskSubmitResponse,
} from '@/api/types';

export type ListTasksParams = {
  agent_instance_id?: string;
  status?: ApiTaskStatus;
  category?: ApiTaskCategory;
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

export function retryTask(
  taskId: string,
  payload: ApiTaskRetryRequest,
): Promise<ApiTaskSubmitResponse> {
  return apiRequest<ApiTaskSubmitResponse>(`/v1/tasks/${taskId}/retry`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function getTaskEvents(
  taskId: string,
  limit = 200,
): Promise<ApiTaskExecutionEvent[]> {
  return apiRequest<ApiTaskExecutionEvent[]>(
    buildApiPath(`/v1/tasks/${taskId}/events`, { limit }),
  );
}
