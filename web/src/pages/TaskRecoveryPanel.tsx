import { useState, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { RotateCcw, ShieldAlert } from 'lucide-react';
import { getErrorDetail } from '@/api/client';
import { retryTask } from '@/api/tasks';
import type { ApiTask } from '@/api/types';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';

type RecoveryMode = 'checkpoint' | 'new';

type RecoveryPanelProps = {
  task: ApiTask;
  onRetried: () => Promise<void>;
};

export function TaskRecoveryPanel({ task, onRetried }: RecoveryPanelProps) {
  const { t } = useTranslation();
  const recovery = task.recovery;
  const [confirmMode, setConfirmMode] = useState<RecoveryMode | null>(null);
  const [isRetrying, setIsRetrying] = useState(false);
  const [retryError, setRetryError] = useState<string | null>(null);

  if (!recovery?.visible) return null;

  const startRetry = async (mode: RecoveryMode) => {
    if (recovery.duplicate_side_effects_confirmation_required && confirmMode !== mode) {
      setConfirmMode(mode);
      return;
    }

    setIsRetrying(true);
    setRetryError(null);
    try {
      await retryTask(task.id, {
        from_checkpoint: mode === 'checkpoint',
        confirm_duplicate_side_effects: recovery.duplicate_side_effects_confirmation_required,
      });
      setConfirmMode(null);
      await onRetried();
    } catch (error) {
      setRetryError(getErrorDetail(error, t('taskDetail.recovery.retryFailed')));
    } finally {
      setIsRetrying(false);
    }
  };

  return (
    <Card className="h-fit max-w-3xl border-amber-500/40 bg-amber-500/5">
      <CardHeader>
        <CardTitle className="flex items-center gap-2"><ShieldAlert className="size-4 text-amber-600" />{t('taskDetail.recovery.title')}</CardTitle>
        <CardDescription>{t('taskDetail.recovery.description')}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <div className="grid gap-3 md:grid-cols-2">
          <Block title={t('taskDetail.recovery.failureSummary')}>{recovery.failure_summary || '-'}</Block>
          <Block title={t('taskDetail.recovery.checkpointSummary')}>{recovery.checkpoint_summary || '-'}</Block>
        </div>
        <Block title={t('taskDetail.recovery.recommendedAction')}>{recovery.recommended_action}</Block>
        <List title={t('taskDetail.recovery.unrecoverableReasons')} items={recovery.unrecoverable_reasons} />
        <List title={t('taskDetail.recovery.riskWarnings')} items={recovery.risk_warnings} />
        {retryError ? <p className="text-sm text-destructive">{retryError}</p> : null}
        <div className="flex flex-wrap gap-2">
          <Button type="button" onClick={() => startRetry('checkpoint')} disabled={!recovery.can_retry_from_checkpoint || isRetrying}>
            <RotateCcw className="size-4" />{t('taskDetail.recovery.retryFromCheckpoint')}
          </Button>
          <Button type="button" variant="outline" onClick={() => startRetry('new')} disabled={!recovery.can_retry_as_new_task || isRetrying}>
            {t('taskDetail.recovery.retryAsNewTask')}
          </Button>
        </div>
      </CardContent>
      <Dialog open={confirmMode !== null} onOpenChange={open => !open && setConfirmMode(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('taskDetail.recovery.confirmTitle')}</DialogTitle>
            <DialogDescription>{t('taskDetail.recovery.confirmDescription')}</DialogDescription>
          </DialogHeader>
          <List title={t('taskDetail.recovery.riskWarnings')} items={recovery.risk_warnings} />
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setConfirmMode(null)} disabled={isRetrying}>{t('taskDetail.recovery.cancel')}</Button>
            <Button type="button" onClick={() => confirmMode && startRetry(confirmMode)} disabled={isRetrying}>{t('taskDetail.recovery.confirmRetry')}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}

function Block({ title, children }: { title: string; children: ReactNode }) {
  return <div className="rounded-md border bg-background/70 px-3 py-2"><p className="text-xs font-medium uppercase tracking-[0.16em] text-muted-foreground">{title}</p><div className="mt-2 break-words">{children}</div></div>;
}

function List({ title, items }: { title: string; items: string[] }) {
  if (!items.length) return null;
  return <Block title={title}><ul className="list-disc space-y-1 pl-5">{items.map(item => <li key={item}>{item}</li>)}</ul></Block>;
}
