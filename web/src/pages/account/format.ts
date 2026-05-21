import type { ApiAgentEntitlement, ApiEntitlementStatus } from '@/api/types';

export function formatMoney(cents: number, currency: string): string {
  return new Intl.NumberFormat(undefined, {
    style: 'currency',
    currency: currency || 'USD',
  }).format(cents / 100);
}

export function formatDate(value: string): string {
  const timestamp = Date.parse(value);
  if (Number.isNaN(timestamp)) {
    return '-';
  }
  return new Intl.DateTimeFormat(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  }).format(timestamp);
}

export function normalizeEntitlementStatus(
  entitlement: ApiAgentEntitlement,
  now = Date.now(),
): ApiEntitlementStatus {
  if (entitlement.status === 'expired') {
    return 'expired';
  }

  const expiresAt = Date.parse(entitlement.expires_at);
  if (!Number.isNaN(expiresAt) && expiresAt < now) {
    return 'expired';
  }
  return 'active';
}

export function countActiveEntitlements(entitlements: ApiAgentEntitlement[]): number {
  return entitlements.filter(entitlement => normalizeEntitlementStatus(entitlement) === 'active')
    .length;
}
