import { Link } from 'react-router-dom';
import { Bot, CheckCircle2, CreditCard, PlusCircle, Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

type AgentEntitlementEmptyStateProps = {
  title?: string;
  description?: string;
};

const purchaseOptions = [
  { label: 'Buy Tela', to: '/agent-entitlement?agent=tela', description: 'Best for backend, infra, and Python delivery.' },
  { label: 'Buy Sophie', to: '/agent-entitlement?agent=sophie', description: 'Best for frontend, QA, and product polish.' },
];

export function AgentEntitlementEmptyState({
  title = 'No active Agent entitlement',
  description = 'Recharge your workspace or buy a Tela or Sophie entitlement to activate an agent and start publishing tasks.',
}: AgentEntitlementEmptyStateProps) {
  return (
    <Card className="overflow-hidden border-dashed bg-card/80">
      <CardHeader className="items-center text-center">
        <div className="mb-2 flex size-12 items-center justify-center rounded-full bg-primary/10 text-primary">
          <Bot className="size-6" />
        </div>
        <CardTitle>{title}</CardTitle>
        <CardDescription className="max-w-2xl">{description}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-col justify-center gap-2 sm:flex-row">
          <Button asChild>
            <Link to="/agent-entitlement?intent=recharge">
              <CreditCard className="size-4" />
              Recharge workspace
            </Link>
          </Button>
          {purchaseOptions.map(option => (
            <Button key={option.to} asChild variant="outline">
              <Link to={option.to}>
                <PlusCircle className="size-4" />
                {option.label}
              </Link>
            </Button>
          ))}
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          {purchaseOptions.map(option => (
            <div key={option.label} className="rounded-lg border bg-background/70 p-3">
              <p className="flex items-center gap-2 text-sm font-medium">
                <Sparkles className="size-4 text-primary" />
                {option.label}
              </p>
              <p className="mt-1 text-xs text-muted-foreground">{option.description}</p>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

export function PostPurchaseSuccessState() {
  return (
    <Card className="mx-auto w-full max-w-3xl border-primary/20 bg-card/90 text-center">
      <CardHeader className="items-center">
        <div className="mb-2 flex size-14 items-center justify-center rounded-full bg-primary/10 text-primary">
          <CheckCircle2 className="size-7" />
        </div>
        <CardTitle>Agent entitlement activated</CardTitle>
        <CardDescription>
          Your workspace is ready. Publish a task for your new agent or review current work on the task board.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col justify-center gap-2 sm:flex-row">
        <Button asChild>
          <Link to="/publish-task">Publish a task</Link>
        </Button>
        <Button asChild variant="outline">
          <Link to="/task-board">View task board</Link>
        </Button>
      </CardContent>
    </Card>
  );
}
