import { apiRequest } from '@/api/client';
import type { ApiAccountOverview } from '@/api/types';

export function getAccountOverview(): Promise<ApiAccountOverview> {
  return apiRequest<ApiAccountOverview>('/v1/account/overview');
}
