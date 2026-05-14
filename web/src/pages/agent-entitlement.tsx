import { useSearchParams } from 'react-router-dom';
import { useAppLayout } from '@/components/layout/AppLayout';
import {
  AgentEntitlementEmptyState,
  PostPurchaseSuccessState,
} from '@/components/entitlements/AgentEntitlementStates';

export default function AgentEntitlementPage() {
  const [searchParams] = useSearchParams();
  const isSuccess = searchParams.get('status') === 'success';

  useAppLayout({
    title: isSuccess ? 'Purchase complete' : 'Agent Entitlement',
    description: isSuccess
      ? 'Your agent entitlement is active.'
      : 'Recharge or buy an agent entitlement to keep work moving.',
  });

  return (
    <section className="flex min-h-[28rem] items-center justify-center">
      {isSuccess ? <PostPurchaseSuccessState /> : <AgentEntitlementEmptyState />}
    </section>
  );
}
