import { apiRequest, buildApiPath } from '@/api/client';
import type {
  ApiAgentInstance,
  ApiAgentInstanceCreateRequest,
  ApiAgentInstanceStatusUpdateRequest,
  ApiAgentInstanceUpdateRequest,
} from '@/api/types';

export type ListAgentInstancesParams = {
  is_active?: boolean;
};

export function listAgentInstances(
  params: ListAgentInstancesParams = {},
): Promise<ApiAgentInstance[]> {
  return apiRequest<ApiAgentInstance[]>(
    buildApiPath('/v1/agent-instances', params),
  );
}

export function getAgentInstance(
  instanceId: string,
): Promise<ApiAgentInstance> {
  return apiRequest<ApiAgentInstance>(`/v1/agent-instances/${instanceId}`);
}

export function createAgentInstance(
  payload: ApiAgentInstanceCreateRequest,
): Promise<ApiAgentInstance> {
  return apiRequest<ApiAgentInstance>('/v1/agent-instances', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function updateAgentInstance(
  instanceId: string,
  payload: ApiAgentInstanceUpdateRequest,
): Promise<ApiAgentInstance> {
  return apiRequest<ApiAgentInstance>(`/v1/agent-instances/${instanceId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export function updateAgentInstanceStatus(
  instanceId: string,
  payload: ApiAgentInstanceStatusUpdateRequest,
): Promise<ApiAgentInstance> {
  return apiRequest<ApiAgentInstance>(
    `/v1/agent-instances/${instanceId}/status`,
    {
      method: 'PATCH',
      body: JSON.stringify(payload),
    },
  );
}
