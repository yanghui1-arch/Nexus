import { apiRequest } from '@/api/client';
import type {
  ApiTaskExecutionEvent,
  ApiTaskObservabilityMetrics,
} from '@/api/types';

export function getTaskEvents(
  taskId: string,
  init: RequestInit = {},
): Promise<ApiTaskExecutionEvent[]> {
  return apiRequest<ApiTaskExecutionEvent[]>(`/v1/tasks/${taskId}/events`, init);
}

export function getTaskMetrics(
  taskId: string,
  init: RequestInit = {},
): Promise<ApiTaskObservabilityMetrics> {
  return apiRequest<ApiTaskObservabilityMetrics>(`/v1/tasks/${taskId}/metrics`, init);
}

export async function getTaskObservability(
  taskId: string,
  init: RequestInit = {},
): Promise<{
  events: ApiTaskExecutionEvent[];
  metrics: ApiTaskObservabilityMetrics;
}> {
  const [events, metrics] = await Promise.all([
    getTaskEvents(taskId, init),
    getTaskMetrics(taskId, init),
  ]);

  return { events, metrics };
}
