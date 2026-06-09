import { Github, WalletCards } from 'lucide-react';
import type { ApiAccountOverview } from '@/api/types';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { countActiveEntitlements, formatMoney } from './format';

type AccountSummaryCardsProps = {
  account: ApiAccountOverview;
};

export function AccountSummaryCards({ account }: AccountSummaryCardsProps) {
  const activeCount = countActiveEntitlements(account.entitlements);
  const displayName = account.user.github_name ?? account.user.github_login;

  return (
    <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
      <Card>
        <CardHeader>
          <CardTitle className="inline-flex items-center gap-2">
            <Github className="size-5" /> Signed-in GitHub user
          </CardTitle>
          <CardDescription>Purchases and entitlements are tied to this account.</CardDescription>
        </CardHeader>
        <CardContent className="flex items-center gap-4">
          {account.user.github_avatar_url ? (
            <img
              src={account.user.github_avatar_url}
              alt=""
              className="size-14 rounded-full border object-cover"
            />
          ) : (
            <div className="flex size-14 items-center justify-center rounded-full border bg-muted text-lg font-semibold">
              {account.user.github_login.slice(0, 1).toUpperCase()}
            </div>
          )}
          <div className="min-w-0">
            <p className="truncate text-lg font-semibold">{displayName}</p>
            <p className="truncate text-sm text-muted-foreground">@{account.user.github_login}</p>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="inline-flex items-center gap-2">
            <WalletCards className="size-5" /> Balance
          </CardTitle>
          <CardDescription>{activeCount} active Agent entitlement{activeCount === 1 ? '' : 's'}</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-3xl font-semibold">
            {formatMoney(account.balance_cents, account.currency)}
          </p>
          <p className="mt-2 text-sm text-muted-foreground">Available account credit.</p>
        </CardContent>
      </Card>
    </div>
  );
}
