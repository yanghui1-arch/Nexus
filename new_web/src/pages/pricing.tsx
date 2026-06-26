import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Check, Coins, Zap } from 'lucide-react';
import { toast } from 'sonner';
import { purchaseAgent, rechargeBalance } from '@/api/auth';
import { getErrorDetail } from '@/api/client';
import type { ApiAgentKind } from '@/api/types';
import { useAuth } from '@/components/AuthProvider';
import { useAppLayout } from '@/components/layout/AppLayout';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';

const PLANS = [
  {
    agent: 'tela' as const,
    name: 'Tela',
    price: '¥5,500',
    descriptionKey: 'pricing.plans.tela.description',
    featureKeys: ['pricing.plans.common.access', 'pricing.plans.tela.automation', 'pricing.plans.tela.backendSupport'],
    gradient: 'from-blue-500 to-indigo-600',
  },
  {
    agent: 'sophie' as const,
    name: 'Sophie',
    price: '¥6,000',
    descriptionKey: 'pricing.plans.sophie.description',
    featureKeys: ['pricing.plans.common.access', 'pricing.plans.sophie.reactImplementation', 'pricing.plans.sophie.designSystemFit'],
    gradient: 'from-purple-500 to-pink-600',
  },
  {
    agent: 'jules' as const,
    name: 'Jules',
    price: '¥6,200',
    descriptionKey: 'pricing.plans.jules.description',
    featureKeys: ['pricing.plans.common.access', 'pricing.plans.jules.springBootDelivery', 'pricing.plans.jules.persistenceAndApi'],
    gradient: 'from-orange-500 to-red-600',
  },
  {
    agent: 'assistant' as const,
    name: 'Assistant',
    price: '¥0',
    descriptionKey: 'pricing.plans.assistant.description',
    featureKeys: ['pricing.plans.common.access', 'pricing.plans.assistant.prReview'],
    gradient: 'from-gray-400 to-gray-600',
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
      <div className="rounded-2xl border border-gray-200/60 bg-white p-6">
        <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-sm text-gray-500">{t('pricing.availableBalance')}</p>
            <p className="mt-1 text-3xl font-bold tracking-tight text-[hsl(0,0%,8%)]">{balance}</p>
          </div>
          <div className="flex w-full flex-col gap-3 sm:flex-row md:w-auto">
            <Input
              className="md:w-56 h-10"
              value={rechargeYuan}
              onChange={event => setRechargeYuan(event.target.value)}
              inputMode="decimal"
              placeholder={t('pricing.amountPlaceholder')}
            />
            <Button onClick={handleRecharge} disabled={!user} className="h-10 rounded-lg bg-[hsl(0,0%,8%)] text-white hover:bg-[hsl(0,0%,20%)]">
              <Coins className="size-4" /> {t('pricing.recharge')}
            </Button>
          </div>
        </div>
      </div>

      <div>
        <h2 className="text-lg font-bold text-[hsl(0,0%,8%)] mb-4">{t('pricing.buyAgent')}</h2>
        <div className="grid gap-5 lg:grid-cols-2">
          {PLANS.map(plan => (
            <div
              key={plan.name}
              className="group relative overflow-hidden rounded-2xl border border-gray-200/60 bg-white transition-all duration-200 hover:shadow-lg"
            >
              <div className={cn('h-1.5 bg-gradient-to-r', plan.gradient)} />
              <div className="p-6">
                <div className="flex items-center gap-3">
                  <div className={cn('flex size-10 items-center justify-center rounded-xl bg-gradient-to-br text-white', plan.gradient)}>
                    <Zap className="size-5" />
                  </div>
                  <div>
                    <h3 className="text-lg font-bold text-[hsl(0,0%,8%)]">{plan.name}</h3>
                    <p className="text-sm text-gray-500">{t(plan.descriptionKey as never)}</p>
                  </div>
                </div>

                <div className="mt-4 flex items-baseline gap-1">
                  <span className="text-3xl font-bold text-[hsl(0,0%,8%)]">{plan.price}</span>
                  <span className="text-sm text-gray-400">{t('pricing.perMonth')}</span>
                </div>

                <ul className="mt-5 space-y-2.5">
                  {plan.featureKeys.map(featureKey => (
                    <li key={featureKey} className="flex items-center gap-2.5 text-sm text-gray-600">
                      <div className="flex size-5 items-center justify-center rounded-full bg-green-100">
                        <Check className="size-3 text-green-600" />
                      </div>
                      {t(featureKey as never)}
                    </li>
                  ))}
                </ul>

                <Button
                  className="mt-6 w-full h-10 rounded-lg bg-[hsl(0,0%,8%)] text-white hover:bg-[hsl(0,0%,20%)]"
                  onClick={() => handlePurchase(plan.agent)}
                  disabled={!user || status === 'checking' || busyAgent === plan.agent}
                >
                  {t('pricing.buyPlan' as never, { plan: plan.name })}
                </Button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
