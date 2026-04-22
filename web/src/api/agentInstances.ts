import { apiRequest, buildApiPath } from '@/api/client';
import type { ApiAgentInstance, ApiAgentKind } from '@/api/types';

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
