import { apiRequest } from './client';
import { clearStoredAuthToken, getStoredAuthToken } from '@/lib/auth';
import type {
  ApiAuthTokenResponse,
  ApiBuyAgentRequest,
  ApiGithubLoginResponse,
  ApiUser,
  ApiUserAgentSubscription,
} from './types';

function authHeaders(): HeadersInit {
  const token = getStoredAuthToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export function getGithubLoginUrl(state: string) {
  return apiRequest<ApiGithubLoginResponse>(
    `/v1/auth/github/login?state=${encodeURIComponent(state)}`,
  );
}

export function exchangeGithubCode(code: string) {
  return apiRequest<ApiAuthTokenResponse>(
    `/v1/auth/github/callback?code=${encodeURIComponent(code)}`,
  );
}

export function getCurrentUser() {
  return apiRequest<ApiUser>('/v1/auth/me', {
    headers: authHeaders(),
  });
}

export async function logout() {
  try {
    await apiRequest<{ message: string }>('/v1/auth/logout', {
      method: 'POST',
      headers: authHeaders(),
    });
  } finally {
    clearStoredAuthToken();
  }
}

export function buyAgent(payload: ApiBuyAgentRequest) {
  return apiRequest<ApiUserAgentSubscription>('/v1/auth/buy-agent', {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify(payload),
  });
}
