import { startTransition, useCallback, useEffect, useState } from 'react';
import { Loader2, RefreshCw } from 'lucide-react';
import { toast } from 'sonner';
import { getAccountOverview } from '@/api/account';
import { getErrorDetail } from '@/api/client';
import type { ApiAccountOverview } from '@/api/types';
import { useAppLayout } from '@/components/layout/AppLayout';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { AccountSummaryCards } from './AccountSummaryCards';
import { EntitlementCards } from './EntitlementCards';

export default function AccountPage() {
  const [account, setAccount] = useState<ApiAccountOverview | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadAccount = useCallback(async () => {
    setIsLoading(true);
    try {
      const nextAccount = await getAccountOverview();
      startTransition(() => {
        setAccount(nextAccount);
        setError(null);
        setIsLoading(false);
      });
    } catch (nextError) {
      const detail = getErrorDetail(nextError, 'Failed to load account overview.');
      startTransition(() => {
        setError(detail);
        setIsLoading(false);
      });
      toast.error('Failed to load account', { description: detail });
    }
  }, []);

  useEffect(() => {
    void loadAccount();
  }, [loadAccount]);

  useAppLayout({
    title: 'Account & Pricing',
    description: 'Review your GitHub account, balance, and Agent entitlement status.',
    topActions: (
      <Button variant="outline" size="sm" disabled={isLoading} onClick={() => void loadAccount()}>
        {isLoading ? <Loader2 className="size-4 animate-spin" /> : <RefreshCw className="size-4" />}
        Refresh
      </Button>
    ),
  });

  if (isLoading && !account) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="inline-flex items-center gap-2">
            <Loader2 className="size-5 animate-spin" /> Loading account
          </CardTitle>
          <CardDescription>Fetching your balance and Agent cards.</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  if (error && !account) {
    return (
      <Card className="border-destructive/30 bg-destructive/5">
        <CardHeader>
          <CardTitle>Unable to load account</CardTitle>
          <CardDescription>{error}</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  if (!account) {
    return null;
  }

  return (
    <section className="space-y-6">
      <AccountSummaryCards account={account} />
      <div className="space-y-3">
        <div>
          <h2 className="text-lg font-semibold">Agent cards</h2>
          <p className="text-sm text-muted-foreground">
            Purchase and expiry dates with current active or expired status.
          </p>
        </div>
        <EntitlementCards entitlements={account.entitlements} />
      </div>
    </section>
  );
}
