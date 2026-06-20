import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Check, Coins } from 'lucide-react';
import { toast } from 'sonner';
import { purchaseAgent, rechargeBalance } from '@/api/auth';
import { getErrorDetail } from '@/api/client';
import type { ApiAgentKind } from '@/api/types';
import { useAuth } from '@/components/AuthProvider';
import { useAppLayout } from '@/components/layout/AppLayout';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';

const PLANS = [
  {
    agent: 'tela' as const,
    name: 'Tela',
    price: '¥5,500',
    descriptionKey: 'pricing.plans.tela.description',
    featureKeys: ['pricing.plans.common.access', 'pricing.plans.tela.automation', 'pricing.plans.tela.backendSupport'],
  },
  {
    agent: 'sophie' as const,
    name: 'Sophie',
    price: '¥6,000',
    descriptionKey: 'pricing.plans.sophie.description',
    featureKeys: ['pricing.plans.common.access', 'pricing.plans.sophie.reactImplementation', 'pricing.plans.sophie.designSystemFit'],
  },
  {
    agent: 'jules' as const,
    name: 'Jules',
    price: '¥6,200',
    descriptionKey: 'pricing.plans.jules.description',
    featureKeys: ['pricing.plans.common.access', 'pricing.plans.jules.springBootDelivery', 'pricing.plans.jules.persistenceAndApi'],
  },
  {
    agent: 'assistant' as const,
    name: 'Assistant',
    price: '¥0',
    descriptionKey: 'pricing.plans.assistant.description',
    featureKeys: ['pricing.plans.common.access', 'pricing.plans.assistant.prReview'],
  },
];

function formatCny(amount: string): string {
  return new Intl.NumberFormat('zh-CN', { style: 'currency', currency: 'CNY' }).format(Number(amount));
}

export default function PricingPage() {
  const { t } = useTranslation();
  const { status, user, refreshUser } = useAuth();
  const [rechargeYuan, setRechargeYuan] = useState('1000');
  const [busyAgent, setBusyAgent] = useState<ApiAgentKind | null>(null);

  const balance = useMemo(() => (user ? formatCny(user.balance) : '—'), [user]);

  useAppLayout({
    title: t('pricing.title'),
    mainClassName: 'gap-8',
  });

  const handleRecharge = async () => {
    const amount = Number(rechargeYuan);
    if (!Number.isFinite(amount) || amount <= 0) {
      toast.error(t('pricing.invalidRechargeAmount'));
      return;
    }
    try {
      const nextUser = await rechargeBalance({ amount: amount.toFixed(2) });
      await refreshUser();
      toast.success(t('pricing.balanceRecharged'), { description: t('pricing.currentBalance', { balance: formatCny(nextUser.balance) }) });
    } catch (error) {
      toast.error(t('pricing.rechargeFailed'), { description: getErrorDetail(error) });
    }
  };

  const handlePurchase = async (agent: ApiAgentKind) => {
    setBusyAgent(agent);
    try {
      const purchase = await purchaseAgent({ agent });
      await refreshUser();
      toast.success(t('pricing.agentPurchased', { agent }), { description: t('pricing.validUntil', { date: new Date(purchase.expires_at).toLocaleDateString() }) });
    } catch (error) {
      toast.error(t('pricing.purchaseFailed'), { description: getErrorDetail(error) });
    } finally {
      setBusyAgent(null);
    }
  };

  return (
    <div className="space-y-8">
      <section className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="text-sm text-muted-foreground">{t('pricing.availableBalance')}</p>
          <p className="mt-1 text-3xl font-semibold tracking-tight">{balance}</p>
        </div>
        <div className="flex w-full flex-col gap-3 sm:flex-row md:w-auto">
          <Input
            className="md:w-56"
            value={rechargeYuan}
            onChange={event => setRechargeYuan(event.target.value)}
            inputMode="decimal"
            placeholder={t('pricing.amountPlaceholder')}
          />
          <Button onClick={handleRecharge} disabled={!user}>
            <Coins /> {t('pricing.recharge')}
          </Button>
        </div>
      </section>

      <section className="space-y-4">
        <h2 className="text-lg font-semibold">{t('pricing.buyAgent')}</h2>
        <div className="grid gap-5 lg:grid-cols-2">
          {PLANS.map(plan => (
            <Card
              key={plan.name}
              className={cn(
                'group relative overflow-hidden transition-all duration-200',
                'hover:border-primary hover:shadow-xl hover:shadow-primary/10',
              )}
            >
              <CardHeader>
                <CardTitle>{plan.name}</CardTitle>
                <CardDescription>{t(plan.descriptionKey)}</CardDescription>
                <div className="pt-4"><span className="text-4xl font-semibold">{plan.price}</span><span className="text-muted-foreground"> {t('pricing.perMonth')}</span></div>
              </CardHeader>
              <CardContent className="space-y-5">
                <ul className="space-y-3 text-sm">
                  {plan.featureKeys.map(featureKey => <li key={featureKey} className="flex gap-2"><Check className="mt-0.5 size-4 text-primary" />{t(featureKey)}</li>)}
                </ul>
                <Button className="w-full" onClick={() => handlePurchase(plan.agent)} disabled={!user || status === 'checking' || busyAgent === plan.agent}>
                  {t('pricing.buyPlan', { plan: plan.name })}
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>
    </div>
  );
}
