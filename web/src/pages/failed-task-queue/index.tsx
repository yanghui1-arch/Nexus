import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { GitPullRequest, Loader2 } from 'lucide-react';
import { getErrorDetail } from '@/api/client';
import { listTasks } from '@/api/tasks';
import type { ApiTask } from '@/api/types';
import { Badge } from '@/components/ui/badge';
import { useAppLayout } from '@/components/layout/AppLayout';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';

function formatTimestamp(value: string | null): string {
  if (!value) return '-';
  const timestamp = Date.parse(value);
  return Number.isNaN(timestamp) ? '-' : new Date(timestamp).toLocaleString();
}

function summarizeError(error: string | null): string {
  if (!error) return '-';
  const compact = error.replace(/\s+/g, ' ').trim();
  return compact.length > 140 ? `${compact.slice(0, 137)}...` : compact;
}

function sortFailedTasks(tasks: ApiTask[]): ApiTask[] {
  return [...tasks].sort((left, right) =>
    Date.parse(right.finished_at ?? right.updated_at) - Date.parse(left.finished_at ?? left.updated_at),
  );
}

export default function FailedTaskQueuePage() {
  const { t } = useTranslation();
  const [tasks, setTasks] = useState<ApiTask[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useAppLayout({ title: t('failedTaskQueue.title'), description: t('failedTaskQueue.description') });

  useEffect(() => {
    let cancelled = false;
    async function loadFailedTasks() {
      setIsLoading(true);
      setError(null);
      try {
        const failedTasks = await listTasks({ category: 'coding', status: 'failed' });
        if (!cancelled) setTasks(failedTasks);
      } catch (reason) {
        if (!cancelled) setError(getErrorDetail(reason, t('failedTaskQueue.loadFailed')));
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }
    void loadFailedTasks();
    return () => { cancelled = true; };
  }, [t]);

  const sortedTasks = useMemo(() => sortFailedTasks(tasks), [tasks]);
  if (isLoading) return <div className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="size-4 animate-spin" />{t('failedTaskQueue.loading')}</div>;
  if (error) return <p className="text-sm text-destructive">{error}</p>;
  if (sortedTasks.length === 0) return <p className="text-sm text-muted-foreground">{t('failedTaskQueue.empty')}</p>;

  return <div className="rounded-md border bg-background"><Table><TableHeader><TableRow>
    <TableHead>{t('common.title')}</TableHead>
    <TableHead>{t('common.repository')}</TableHead>
    <TableHead>{t('common.project')}</TableHead>
    <TableHead>{t('common.agent')}</TableHead>
    <TableHead>{t('failedTaskQueue.failedAt')}</TableHead>
    <TableHead>{t('failedTaskQueue.errorSummary')}</TableHead>
    <TableHead>{t('failedTaskQueue.prStatus')}</TableHead>
    <TableHead>{t('common.updated')}</TableHead>
  </TableRow></TableHeader><TableBody>{sortedTasks.map(task => (
    <TableRow key={task.id}>
      <TableCell className="max-w-[18rem] font-medium"><span className="line-clamp-2">{task.question}</span></TableCell>
      <TableCell className="font-mono text-xs">{task.repo ?? '-'}</TableCell>
      <TableCell>{task.project ?? '-'}</TableCell>
      <TableCell className="capitalize">{task.agent}</TableCell>
      <TableCell>{formatTimestamp(task.finished_at)}</TableCell>
      <TableCell className="max-w-[20rem] text-muted-foreground"><span className="line-clamp-2">{summarizeError(task.error)}</span></TableCell>
      <TableCell>{task.external_pull_request_url ? (
        <a href={task.external_pull_request_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-foreground underline-offset-4 hover:underline">
          <GitPullRequest className="size-3.5" />{t('failedTaskQueue.prLinked')}
        </a>
      ) : <Badge variant="outline">{t('failedTaskQueue.noPr')}</Badge>}</TableCell>
      <TableCell>{formatTimestamp(task.updated_at)}</TableCell>
    </TableRow>
  ))}</TableBody></Table></div>;
}
