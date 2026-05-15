import { startTransition, useEffect, useMemo, useState } from 'react';
import { Bot, Check, Coins, Sparkles } from 'lucide-react';
import { toast } from 'sonner';
import { getCurrentUser, purchaseAgent, rechargeBalance } from '@/api/auth';
import { getErrorDetail } from '@/api/client';
import type { ApiAgentKind, ApiUser } from '@/api/types';
import { useAppLayout } from '@/components/layout/AppLayout';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';

const PLANS = [
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

function formatCny(amount: string): string {
  return new Intl.NumberFormat('zh-CN', { style: 'currency', currency: 'CNY' }).format(Number(amount));
}

export default function PricingPage() {
  const [user, setUser] = useState<ApiUser | null>(null);
  const [isLoadingUser, setIsLoadingUser] = useState(true);
  const [rechargeYuan, setRechargeYuan] = useState('1000');
  const [busyAgent, setBusyAgent] = useState<ApiAgentKind | null>(null);

  const balance = useMemo(() => (user ? formatCny(user.balance) : '—'), [user]);

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
    const amount = Number(rechargeYuan);
    if (!Number.isFinite(amount) || amount <= 0) {
      toast.error('Please enter a valid recharge amount.');
      return;
    }
    try {
      const nextUser = await rechargeBalance({ amount: amount.toFixed(2) });
      setUser(nextUser);
      toast.success('Balance recharged', { description: `Current balance: ${formatCny(nextUser.balance)}` });
    } catch (error) {
      toast.error('Recharge failed', { description: getErrorDetail(error) });
    }
  };

  const handlePurchase = async (agent: ApiAgentKind) => {
    setBusyAgent(agent);
    try {
      const purchase = await purchaseAgent({ agent });
      setUser(current => current ? { ...current, balance: purchase.balance } : current);
      toast.success(`${agent} purchased`, { description: `Valid until ${new Date(purchase.expires_at).toLocaleDateString()}` });
    } catch (error) {
      toast.error('Purchase failed', { description: getErrorDetail(error) });
    } finally {
      setBusyAgent(null);
    }
  };

  return (
    <div className="space-y-6">
      <section className="rounded-3xl border bg-card p-6 shadow-sm">
        <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div className="max-w-2xl space-y-3">
            <div className="inline-flex items-center gap-2 rounded-full bg-primary/10 px-3 py-1 text-sm font-medium text-primary">
              <Sparkles className="size-4" /> Agent subscriptions
            </div>
            <h1 className="text-3xl font-semibold tracking-tight md:text-4xl">Choose an agent subscription.</h1>
            <p className="text-muted-foreground">Recharge once, then activate Tela or Sophie monthly from a single GitHub-backed wallet.</p>
          </div>
          <div className="rounded-2xl border bg-muted/50 px-4 py-3 text-sm">
            <p className="text-muted-foreground">Available balance</p>
            <p className="mt-1 text-2xl font-semibold">{balance}</p>
          </div>
        </div>
      </section>

      <section className="rounded-3xl border bg-card p-5 shadow-sm">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h2 className="text-lg font-semibold">Recharge balance</h2>
            <p className="text-sm text-muted-foreground">Demo recharge credits your wallet directly. Server stores money as Decimal.</p>
          </div>
          <div className="flex flex-col gap-3 sm:w-[360px] sm:flex-row">
            <Input value={rechargeYuan} onChange={event => setRechargeYuan(event.target.value)} inputMode="decimal" placeholder="Amount in CNY" />
            <Button onClick={handleRecharge} disabled={!user}><Coins /> Recharge</Button>
          </div>
        </div>
      </section>

      <div className="grid gap-5 lg:grid-cols-2">
        {PLANS.map(plan => (
          <section
            key={plan.name}
            className={cn(
              'group relative overflow-hidden rounded-3xl border bg-card p-6 shadow-sm transition-all duration-200',
              'hover:border-primary hover:shadow-xl hover:shadow-primary/10',
            )}
          >
            <div className="absolute right-4 top-4 rounded-full bg-primary/10 px-3 py-1 text-xs font-medium text-primary opacity-0 transition-opacity group-hover:opacity-100">
              Select
            </div>
            <div className="mb-4 flex size-11 items-center justify-center rounded-2xl bg-primary/10 text-primary">
              <Bot className="size-5" />
            </div>
            <div className="space-y-2">
              <h2 className="text-2xl font-semibold">{plan.name}</h2>
              <p className="text-sm text-muted-foreground">{plan.description}</p>
              <div className="pt-3"><span className="text-4xl font-semibold">{plan.price}</span><span className="text-muted-foreground"> / month</span></div>
            </div>
            <ul className="mt-6 space-y-3 text-sm">
              {plan.features.map(feature => <li key={feature} className="flex gap-2"><Check className="mt-0.5 size-4 text-primary" />{feature}</li>)}
            </ul>
            <Button className="mt-6 w-full" onClick={() => handlePurchase(plan.agent)} disabled={!user || isLoadingUser || busyAgent === plan.agent}>
              Buy {plan.name}
            </Button>
          </section>
        ))}
      </div>
    </div>
  );
}
