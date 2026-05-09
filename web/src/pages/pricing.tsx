import { startTransition, useEffect, useMemo, useState } from 'react';
import { Bot, Check, Coins, Github, LogOut, Wallet } from 'lucide-react';
import { toast } from 'sonner';
import { getCurrentUser, logout, purchaseAgent, rechargeBalance } from '@/api/auth';
import { getErrorDetail } from '@/api/client';
import type { ApiAgentKind, ApiUser } from '@/api/types';
import { useAppLayout } from '@/components/layout/AppLayout';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';

const PLANS = [
  {
    agent: null,
    name: 'Starter',
    price: '¥0',
    description: 'Explore Nexus and review existing task flow.',
    features: ['GitHub login', 'User profile', 'Balance wallet'],
  },
  {
    agent: 'tela' as const,
    name: 'Tela',
    price: '¥5,500',
    description: 'Backend, infra, tests, and reliability work.',
    features: ['30 days access', 'Virtual PR workflow', 'Repository automation'],
  },
  {
    agent: 'sophie' as const,
    name: 'Sophie',
    price: '¥6,000',
    description: 'Frontend delivery, UI polish, and product pages.',
    features: ['30 days access', 'React implementation', 'Design-system fit'],
  },
];

function formatCny(cents: number): string {
  return new Intl.NumberFormat('zh-CN', { style: 'currency', currency: 'CNY' }).format(cents / 100);
}

export default function PricingPage() {
  const [user, setUser] = useState<ApiUser | null>(null);
  const [isLoadingUser, setIsLoadingUser] = useState(true);
  const [rechargeYuan, setRechargeYuan] = useState('1000');
  const [busyAgent, setBusyAgent] = useState<ApiAgentKind | null>(null);

  const balance = useMemo(() => (user ? formatCny(user.balance_cents) : '—'), [user]);

  useAppLayout({
    title: 'Pricing',
    description: 'Recharge balance and buy monthly access for Tela or Sophie.',
    mainClassName: 'gap-6',
  });

  useEffect(() => {
    void getCurrentUser()
      .then(nextUser => startTransition(() => setUser(nextUser)))
      .catch(() => startTransition(() => setUser(null)))
      .finally(() => startTransition(() => setIsLoadingUser(false)));
  }, []);

  const handleRecharge = async () => {
    const amountCents = Math.round(Number(rechargeYuan) * 100);
    if (!Number.isSafeInteger(amountCents) || amountCents <= 0) {
      toast.error('Please enter a valid recharge amount.');
      return;
    }
    try {
      const nextUser = await rechargeBalance({ amount_cents: amountCents });
      setUser(nextUser);
      toast.success('Balance recharged', { description: `Current balance: ${formatCny(nextUser.balance_cents)}` });
    } catch (error) {
      toast.error('Recharge failed', { description: getErrorDetail(error) });
    }
  };

  const handlePurchase = async (agent: ApiAgentKind) => {
    setBusyAgent(agent);
    try {
      const purchase = await purchaseAgent({ agent });
      setUser(current => current ? { ...current, balance_cents: purchase.balance_cents } : current);
      toast.success(`${agent} purchased`, { description: `Valid until ${new Date(purchase.expires_at).toLocaleDateString()}` });
    } catch (error) {
      toast.error('Purchase failed', { description: getErrorDetail(error) });
    } finally {
      setBusyAgent(null);
    }
  };

  const handleLogout = async () => {
    await logout();
    window.location.href = '/login';
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardContent className="flex flex-col gap-4 p-5 md:flex-row md:items-center md:justify-between">
          <div className="flex items-center gap-3">
            <div className="flex size-11 items-center justify-center rounded-full bg-primary/10 text-primary">
              <Github className="size-5" />
            </div>
            <div>
              <p className="font-medium">{user?.github_login ?? (isLoadingUser ? 'Loading user…' : 'Not signed in')}</p>
              <p className="text-sm text-muted-foreground">{user?.email ?? 'GitHub email is unavailable or private'}</p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <div className="inline-flex items-center gap-2 rounded-full border px-3 py-2 text-sm">
              <Wallet className="size-4 text-primary" /> Balance {balance}
            </div>
            {user ? <Button variant="outline" onClick={handleLogout}><LogOut /> Logout</Button> : <Button asChild><a href="/login">Login</a></Button>}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Recharge balance</CardTitle>
          <CardDescription>Demo recharge credits your wallet directly. Server stores money as integer cents.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3 sm:flex-row">
          <Input value={rechargeYuan} onChange={event => setRechargeYuan(event.target.value)} inputMode="decimal" placeholder="Amount in CNY" />
          <Button onClick={handleRecharge} disabled={!user}><Coins /> Recharge</Button>
        </CardContent>
      </Card>

      <div className="grid gap-5 lg:grid-cols-3">
        {PLANS.map(plan => (
          <Card key={plan.name} className={plan.agent === 'tela' ? 'border-primary shadow-md' : ''}>
            <CardHeader>
              <div className="mb-3 flex size-10 items-center justify-center rounded-xl bg-primary/10 text-primary">
                <Bot className="size-5" />
              </div>
              <CardTitle>{plan.name}</CardTitle>
              <CardDescription>{plan.description}</CardDescription>
              <div className="pt-4"><span className="text-4xl font-semibold">{plan.price}</span><span className="text-muted-foreground"> / month</span></div>
            </CardHeader>
            <CardContent className="space-y-5">
              <ul className="space-y-3 text-sm">
                {plan.features.map(feature => <li key={feature} className="flex gap-2"><Check className="mt-0.5 size-4 text-primary" />{feature}</li>)}
              </ul>
              {plan.agent ? (
                <Button className="w-full" onClick={() => handlePurchase(plan.agent)} disabled={!user || busyAgent === plan.agent}>
                  Buy {plan.name}
                </Button>
              ) : <Button asChild variant="outline" className="w-full"><a href="/login">Start with GitHub</a></Button>}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
