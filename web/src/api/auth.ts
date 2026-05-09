import { apiRequest, buildApiPath } from './client';

const TOKEN_KEY = 'nexus_access_token';

export type UserProfile = {
  id: string;
  github_login: string;
  email: string | null;
  balance: string;
  currency: string;
};

export function getAccessToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function saveAccessToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function authHeaders() {
  const token = getAccessToken();
  return token ? { Authorization: `Bearer ${token}` } : undefined;
}

export function getGitHubLoginUrl(state: string, redirectUri: string) {
  return apiRequest<{ authorization_url: string }>(
    buildApiPath('/v1/auth/github/login', { state, redirect_uri: redirectUri }),
  );
}

export async function completeGitHubLogin(code: string) {
  const token = await apiRequest<{ access_token: string }>(buildApiPath('/v1/auth/github/callback', { code }));
  saveAccessToken(token.access_token);
  return token;
}

export async function logout() {
  await apiRequest('/v1/auth/logout', { method: 'POST', headers: authHeaders() });
  localStorage.removeItem(TOKEN_KEY);
}

export function getProfile() {
  return apiRequest<UserProfile>('/v1/users/me', { headers: authHeaders() });
}

export function rechargeBalance(amount: string) {
  return apiRequest<UserProfile>('/v1/users/me/balance/recharge', {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ amount }),
  });
}

export function purchaseAgent(agent: 'tela' | 'sophie') {
  return apiRequest('/v1/users/me/agents/purchase', {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ agent, months: 1 }),
  });
}
