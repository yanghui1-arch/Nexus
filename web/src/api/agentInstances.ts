import { apiRequest, buildApiPath } from '@/api/client';
import type {
  ApiAgentInstance,
  ApiAgentKind,
  ApiAgentInstanceUpdateRequest,
  ApiWorkspaceUpdateRequest,
} from '@/api/types';

export type ListAgentInstancesParams = {
  agent?: ApiAgentKind;
  client_id?: string;
  is_active?: boolean;
};

export function listAgentInstances(
  params: ListAgentInstancesParams = {},
): Promise<ApiAgentInstance[]> {
  return apiRequest<ApiAgentInstance[]>(buildApiPath('/v1/agent-instances', params));
}

export function updateAgentInstance(
  agentInstanceId: string,
  payload: ApiAgentInstanceUpdateRequest,
): Promise<ApiAgentInstance> {
  return apiRequest<ApiAgentInstance>(`/v1/agent-instances/${agentInstanceId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export function updateAgentWorkspace(
  agentInstanceId: string,
  payload: ApiWorkspaceUpdateRequest,
): Promise<ApiAgentInstance> {
  return apiRequest<ApiAgentInstance>(`/v1/agent-instances/${agentInstanceId}/workspace`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}
