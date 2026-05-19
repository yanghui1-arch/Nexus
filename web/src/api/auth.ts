import { apiRequest } from '@/api/client';
import type {
  ApiPurchaseAgentRequest,
  ApiPurchaseAgentResponse,
  ApiRechargeRequest,
  ApiUser,
} from '@/api/types';

export function getCurrentUser(): Promise<ApiUser> {
  return apiRequest<ApiUser>('/v1/auth/me');
}

export function logout(): Promise<void> {
  return apiRequest<void>('/v1/auth/logout', { method: 'POST' });
}

export function rechargeBalance(payload: ApiRechargeRequest): Promise<ApiUser> {
  return apiRequest<ApiUser>('/v1/billing/recharge', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function purchaseAgent(
  payload: ApiPurchaseAgentRequest,
): Promise<ApiPurchaseAgentResponse> {
  return apiRequest<ApiPurchaseAgentResponse>('/v1/billing/purchases', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}
