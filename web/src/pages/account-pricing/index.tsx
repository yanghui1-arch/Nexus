import { useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { listPurchases } from '@/api/purchases';
import type { ApiPurchase } from '@/api/types';
import { useAppLayout } from '@/components/layout/AppLayout';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

const CLIENT_ID = 'default';
const money = new Intl.NumberFormat(undefined, { style: 'currency', currency: 'USD' });

function formatDate(value: string | null): string {
  if (!value) return 'Never';
  const timestamp = Date.parse(value);
  return Number.isNaN(timestamp) ? '-' : new Date(timestamp).toLocaleString();
}

function PurchaseRows({ purchases }: { purchases: ApiPurchase[] }) {
  return (
    <tbody className="divide-y">
      {purchases.map(purchase => (
        <tr key={purchase.id} className="bg-card">
          <td className="px-4 py-3 font-medium capitalize">{purchase.agent}</td>
          <td className="px-4 py-3">{money.format(purchase.price_cents / 100)}</td>
          <td className="px-4 py-3 text-muted-foreground">{formatDate(purchase.purchased_at)}</td>
          <td className="px-4 py-3 text-muted-foreground">{formatDate(purchase.expires_at)}</td>
          <td className="px-4 py-3">
            <Badge
              variant="outline"
              className={
                purchase.status === 'active'
                  ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                  : 'border-slate-200 bg-slate-50 text-slate-600'
              }
            >
              {purchase.status === 'active' ? 'Active' : 'Expired'}
            </Badge>
          </td>
        </tr>
      ))}
    </tbody>
  );
}

export default function AccountPricingPage() {
  useAppLayout({
    title: 'Account / Pricing',
    description: 'Review agent purchases and entitlement status.',
  });

  const [purchases, setPurchases] = useState<ApiPurchase[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    listPurchases(CLIENT_ID)
      .then(items => isMounted && setPurchases(items))
      .catch(() => isMounted && setError('Unable to load purchase history.'))
      .finally(() => isMounted && setIsLoading(false));
    return () => {
      isMounted = false;
    };
  }, []);

  return (
    <section className="w-full max-w-5xl space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Purchase history</CardTitle>
          <CardDescription>
            Recent purchases show the agent, charged amount, purchase time, expiry, and current state.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex items-center gap-2 py-8 text-sm text-muted-foreground">
              <Loader2 className="size-4 animate-spin" /> Loading purchases…
            </div>
          ) : error ? (
            <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">{error}</div>
          ) : purchases.length === 0 ? (
            <div className="rounded-lg border border-dashed px-4 py-8 text-center text-sm text-muted-foreground">
              No purchases yet. Completed purchases will appear here for verification.
            </div>
          ) : (
            <div className="overflow-x-auto rounded-lg border">
              <table className="w-full min-w-[720px] text-sm">
                <thead className="bg-muted/60 text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <tr>{['Agent', 'Price', 'Purchased', 'Expires', 'State'].map(label => <th key={label} className="px-4 py-3 font-medium">{label}</th>)}</tr>
                </thead>
                <PurchaseRows purchases={purchases} />
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </section>
  );
}
