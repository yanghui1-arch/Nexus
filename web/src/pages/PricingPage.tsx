import { useEffect, useState } from 'react';
import { Check, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { getProfile, purchaseAgent, rechargeBalance, type UserProfile } from '@/api/auth';
import { getErrorDetail } from '@/api/client';
import { useAppLayout } from '@/components/layout/AppLayout';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';

const plans = [
  { name: 'Free', price: '￥0', agent: null, description: 'Browse Nexus and prepare your workspace.', features: ['GitHub login', 'Profile and balance view', 'Manual recharge'] },
  { name: 'Tela', price: '￥5500', agent: 'tela' as const, description: 'Senior Python engineer agent for implementation work.', features: ['1 month Tela access', 'Backend and tests focused', 'Nexus workflow support'], highlighted: true },
  { name: 'Sophie', price: '￥6000', agent: 'sophie' as const, description: 'Product-focused coding agent for broader feature work.', features: ['1 month Sophie access', 'Frontend and product polish', 'Nexus workflow support'] },
];

export default function PricingPage() {
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [amount, setAmount] = useState('');
  const [busy, setBusy] = useState<string | null>(null);

  useAppLayout({ title: 'Agent Pricing', description: 'Recharge your CNY balance and buy a monthly Tela or Sophie subscription.' });

  useEffect(() => {
    getProfile().then(setProfile).catch(() => setProfile(null));
  }, []);

  async function handleRecharge() {
    setBusy('recharge');
    try {
      setProfile(await rechargeBalance(amount));
      setAmount('');
      toast.success('Balance recharged.');
    } catch (err) {
      toast.error(getErrorDetail(err, 'Recharge failed.'));
    } finally {
      setBusy(null);
    }
  }

  async function handlePurchase(agent: 'tela' | 'sophie') {
    setBusy(agent);
    try {
      await purchaseAgent(agent);
      setProfile(await getProfile());
      toast.success(`${agent} purchased for one month.`);
    } catch (err) {
      toast.error(getErrorDetail(err, 'Purchase failed.'));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="space-y-8">
      <Card className="border-primary/20 bg-primary/5">
        <CardContent className="flex flex-col gap-4 pt-6 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-sm text-muted-foreground">Current account</p>
            <p className="text-lg font-semibold">{profile ? `${profile.github_login} · ${profile.email ?? 'No public email'}` : 'Not logged in'}</p>
            <p className="text-sm text-muted-foreground">Balance: {profile ? `￥${profile.balance}` : 'Login required'}</p>
          </div>
          <div className="flex w-full gap-2 md:w-auto">
            <Input value={amount} onChange={event => setAmount(event.target.value)} placeholder="Amount, e.g. 6000" />
            <Button onClick={handleRecharge} disabled={!amount || busy === 'recharge'}>
              {busy === 'recharge' ? <Loader2 className="size-4 animate-spin" /> : null}
              Recharge
            </Button>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-6 lg:grid-cols-3">
        {plans.map(plan => (
          <Card key={plan.name} className={cn('relative', plan.highlighted && 'border-primary shadow-lg')}>
            {plan.highlighted ? <span className="absolute right-4 top-4 rounded-full bg-primary px-3 py-1 text-xs font-medium text-primary-foreground">Popular</span> : null}
            <CardHeader>
              <CardTitle className="text-xl">{plan.name}</CardTitle>
              <CardDescription>{plan.description}</CardDescription>
              <div className="pt-4"><span className="text-4xl font-bold">{plan.price}</span><span className="text-muted-foreground"> / month</span></div>
            </CardHeader>
            <CardContent className="space-y-3">
              {plan.features.map(feature => <div key={feature} className="flex items-center gap-2 text-sm"><Check className="size-4 text-primary" />{feature}</div>)}
            </CardContent>
            <CardFooter>
              {plan.agent ? <Button className="w-full" variant={plan.highlighted ? 'default' : 'outline'} onClick={() => handlePurchase(plan.agent)} disabled={busy === plan.agent}>{busy === plan.agent ? <Loader2 className="size-4 animate-spin" /> : null}Buy {plan.name}</Button> : <Button className="w-full" variant="outline" disabled>Included</Button>}
            </CardFooter>
          </Card>
        ))}
      </div>
    </div>
  );
}
