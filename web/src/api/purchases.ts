import { apiRequest, buildApiPath } from '@/api/client';
import type { ApiPurchase } from '@/api/types';

export function listPurchases(clientId: string, limit = 20): Promise<ApiPurchase[]> {
  return apiRequest<ApiPurchase[]>(
    buildApiPath('/v1/me/purchases', { client_id: clientId, limit }),
  );
}
