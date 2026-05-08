import { useEffect, useMemo, useState } from 'react';
import { Check, Loader2, LogOut, Sparkles, Wand2 } from 'lucide-react';
import { buyAgent, getCurrentUser, logout } from '@/api/auth';
import { getErrorDetail } from '@/api/client';
import type { ApiAgentKind, ApiUser } from '@/api/types';
import { useAppLayout } from '@/components/layout/AppLayout';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardFooter, CardHeader } from '@/components/ui/card';
import { cn } from '@/lib/utils';

const tiers: Array<{
  id: string;
  agent?: ApiAgentKind;
  name: string;
  price: string;
  description: string;
  cta: string;
  highlighted?: boolean;
  features: string[];
}> = [
  {
    id: 'starter',
    name: 'Explorer',
    price: 'Free',
    description: 'Understand Nexus and prepare your first agent-assisted workflow.',
    cta: 'Current plan',
    features: ['GitHub OAuth account', 'Task board access', 'Review queue preview'],
  },
  {
    id: 'tela',
    agent: 'tela' as ApiAgentKind,
    name: 'Tela',
    price: '$5,500',
    description: 'A focused coding agent for implementation-heavy work and repository changes.',
    cta: 'Buy Tela',
    highlighted: true,
    features: ['Implementation planning', 'Repository edits', 'Issue and PR workflow', 'One month subscription'],
  },
  {
    id: 'sophie',
    agent: 'sophie' as ApiAgentKind,
    name: 'Sophie',
    price: '$6,000',
    description: 'A senior React and interface design agent for polished product experiences.',
    cta: 'Buy Sophie',
    features: ['React UI implementation', 'shadcn component craft', 'Accessibility-minded design', 'One month subscription'],
  },
];

export function PricingPage() {
  const [user, setUser] = useState<ApiUser | null>(null);
  const [isLoadingUser, setIsLoadingUser] = useState(true);
  const [pendingAgent, setPendingAgent] = useState<ApiAgentKind | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useAppLayout({
    title: 'Agent pricing',
    description: 'Choose the right Nexus agent for implementation and review work.',
    mainClassName: 'bg-transparent',
    topActions: user ? (
      <div className="flex items-center gap-3">
        <div className="hidden text-right sm:block">
          <p className="text-sm font-medium">@{user.github_login}</p>
          <p className="text-xs text-muted-foreground">Balance ${Number(user.balance).toLocaleString()}</p>
        </div>
        <Button variant="outline" size="sm" onClick={() => { logout().then(() => window.location.assign('/login')); }}>
          <LogOut className="size-4" aria-hidden="true" />
          Sign out
        </Button>
      </div>
    ) : null,
  });

  useEffect(() => {
    let cancelled = false;
    getCurrentUser()
      .then(currentUser => {
        if (!cancelled) setUser(currentUser);
      })
      .catch(error => {
        if (!cancelled) setErrorMessage(getErrorDetail(error, 'Unable to load your account.'));
      })
      .finally(() => {
        if (!cancelled) setIsLoadingUser(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const balance = useMemo(() => Number(user?.balance ?? 0), [user?.balance]);

  async function handleBuyAgent(agent: ApiAgentKind) {
    setPendingAgent(agent);
    setErrorMessage(null);
    setStatusMessage(null);
    try {
      const subscription = await buyAgent({ agent, months: 1 });
      const refreshedUser = await getCurrentUser();
      setUser(refreshedUser);
      setStatusMessage(`${subscription.agent[0].toUpperCase()}${subscription.agent.slice(1)} is active until ${new Date(subscription.expires_at).toLocaleDateString()}.`);
    } catch (error) {
      setErrorMessage(getErrorDetail(error, 'Unable to purchase this agent.'));
    } finally {
      setPendingAgent(null);
    }
  }

  return (
    <section className="relative overflow-hidden rounded-3xl border bg-card/80 px-5 py-10 shadow-sm sm:px-8 lg:px-10">
      <div className="absolute inset-x-12 top-0 h-px bg-gradient-to-r from-transparent via-primary/50 to-transparent" />
      <div className="mx-auto max-w-3xl space-y-4 text-center">
        <Badge variant="secondary" className="rounded-full px-3 py-1">Simple monthly access</Badge>
        <h1 className="text-3xl font-semibold tracking-tight sm:text-5xl">Scale your product work with Nexus agents</h1>
        <p className="text-base leading-7 text-muted-foreground sm:text-lg">
          Start with your GitHub identity, then subscribe to Tela or Sophie for focused agent capabilities. Purchases use your Nexus balance.
        </p>
      </div>

      <div className="mx-auto mt-8 max-w-3xl">
        {isLoadingUser ? (
          <div className="flex items-center justify-center gap-3 rounded-xl border bg-background/70 p-4 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" /> Loading account…
          </div>
        ) : user ? (
          <div className="grid gap-3 rounded-2xl border bg-background/80 p-4 sm:grid-cols-3">
            <AccountMetric label="GitHub" value={`@${user.github_login}`} />
            <AccountMetric label="Balance" value={`$${balance.toLocaleString()}`} />
            <AccountMetric label="Billing" value="Monthly" />
          </div>
        ) : null}
        {statusMessage ? <p role="status" className="mt-4 rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-4 text-sm text-emerald-700">{statusMessage}</p> : null}
        {errorMessage ? <p role="alert" className="mt-4 rounded-xl border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">{errorMessage}</p> : null}
      </div>

      <div className="mx-auto mt-10 grid max-w-6xl gap-5 lg:grid-cols-3 lg:items-stretch">
        {tiers.map(tier => {
          const isPurchasable = Boolean(tier.agent);
          const isPending = tier.agent ? pendingAgent === tier.agent : false;
          return (
            <Card key={tier.id} className={cn('relative overflow-hidden transition-all', tier.highlighted ? 'border-primary shadow-xl shadow-primary/10 lg:scale-[1.02]' : 'bg-background/70')}>
              {tier.highlighted ? <div className="absolute inset-x-0 top-0 h-1 bg-primary" /> : null}
              <CardHeader className="gap-4 px-6 pt-7">
                <div className="flex items-center justify-between gap-3">
                  <div className="flex size-11 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                    {tier.id === 'sophie' ? <Sparkles className="size-5" /> : <Wand2 className="size-5" />}
                  </div>
                  {tier.highlighted ? <Badge>Popular</Badge> : null}
                </div>
                <div className="space-y-2">
                  <h2 className="text-2xl font-semibold">{tier.name}</h2>
                  <p className="min-h-12 text-sm leading-6 text-muted-foreground">{tier.description}</p>
                </div>
                <div className="flex items-end gap-2">
                  <span className="text-4xl font-semibold tracking-tight">{tier.price}</span>
                  {isPurchasable ? <span className="pb-1 text-sm text-muted-foreground">/ month</span> : null}
                </div>
              </CardHeader>
              <CardContent className="px-6">
                <ul className="space-y-3 text-sm">
                  {tier.features.map(feature => (
                    <li key={feature} className="flex gap-3">
                      <Check className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden="true" />
                      <span>{feature}</span>
                    </li>
                  ))}
                </ul>
              </CardContent>
              <CardFooter className="mt-auto px-6 pb-7">
                <Button
                  className="w-full"
                  variant={tier.highlighted ? 'default' : 'outline'}
                  disabled={!isPurchasable || Boolean(pendingAgent)}
                  onClick={() => { if (tier.agent) void handleBuyAgent(tier.agent); }}
                >
                  {isPending ? <Loader2 className="size-4 animate-spin" /> : null}
                  {tier.cta}
                </Button>
              </CardFooter>
            </Card>
          );
        })}
      </div>
    </section>
  );
}

function AccountMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl bg-muted/50 p-3 text-center">
      <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">{label}</p>
      <p className="mt-1 truncate text-sm font-semibold">{value}</p>
    </div>
  );
}
