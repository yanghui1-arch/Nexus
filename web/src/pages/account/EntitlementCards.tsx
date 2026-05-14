import { Bot, CalendarDays } from 'lucide-react';
import type { ApiAgentEntitlement, ApiEntitlementStatus } from '@/api/types';
import { Badge } from '@/components/ui/badge';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { cn } from '@/lib/utils';
import { formatDate, normalizeEntitlementStatus } from './format';

const STATUS_LABELS: Record<ApiEntitlementStatus, string> = {
  active: 'Active',
  expired: 'Expired',
};

function EntitlementStatusBadge({ status }: { status: ApiEntitlementStatus }) {
  return (
    <Badge
      variant={status === 'active' ? 'default' : 'outline'}
      className={cn(
        status === 'active'
          ? 'bg-emerald-600 text-white hover:bg-emerald-600'
          : 'border-muted-foreground/30 text-muted-foreground',
      )}
    >
      {STATUS_LABELS[status]}
    </Badge>
  );
}

function DateRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-md border px-3 py-2 text-sm">
      <span className="inline-flex items-center gap-2 text-muted-foreground">
        <CalendarDays className="size-4" /> {label}
      </span>
      <span className="font-medium">{formatDate(value)}</span>
    </div>
  );
}

export function EntitlementCards({
  entitlements,
}: {
  entitlements: ApiAgentEntitlement[];
}) {
  if (!entitlements.length) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Agent entitlements</CardTitle>
          <CardDescription>No Agent cards have been purchased yet.</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      {entitlements.map(entitlement => {
        const status = normalizeEntitlementStatus(entitlement);

        return (
          <Card key={entitlement.id} className={status === 'expired' ? 'opacity-75' : undefined}>
            <CardHeader>
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <CardTitle className="inline-flex items-center gap-2">
                    <Bot className="size-5" /> {entitlement.display_name}
                  </CardTitle>
                  <CardDescription className="mt-1 capitalize">
                    {entitlement.agent} Agent card
                  </CardDescription>
                </div>
                <EntitlementStatusBadge status={status} />
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              <DateRow label="Purchased" value={entitlement.purchased_at} />
              <DateRow label="Expires" value={entitlement.expires_at} />
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
