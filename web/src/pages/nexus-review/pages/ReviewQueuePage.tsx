import { startTransition, useEffect, useMemo, useState } from 'react';
import { Loader2 } from 'lucide-react';
import type { ApiReviewQueueItem, ApiTaskStatus } from '@/api/types';
import { getErrorDetail } from '@/api/client';
import { listTaskReviewQueue } from '@/api/tasks';
import { useAppLayout } from '@/components/layout/AppLayout';
import { Badge } from '@/components/ui/badge';
import { usePolling } from '@/lib/usePolling';
import { cn } from '@/lib/utils';
import { Link } from 'react-router-dom';
import { TASK_STATUS_META, timeAgo } from '../utils/status';

type QueueTab = {
  id: 'review' | 'merge' | 'close';
  label: string;
  statuses: ApiTaskStatus[];
};

const REVIEW_TAB_STATUS_PRIORITY: Partial<Record<ApiTaskStatus, number>> = {
  waiting_for_merge: 0,
  waiting_for_review: 1,
};

const QUEUE_TABS: QueueTab[] = [
  { id: 'review', label: 'Review', statuses: ['waiting_for_review', 'waiting_for_merge'] },
  { id: 'merge', label: 'Merge', statuses: ['merged'] },
  { id: 'close', label: 'Close', statuses: ['closed'] },
];

function truncateWords(value: string, maxWords = 150): string {
  const words = value.trim().split(/\s+/);
  return words.length > maxWords ? `${words.slice(0, maxWords).join(' ')}...` : value;
}

export function ReviewQueuePage() {
  useAppLayout({
    title: 'Nexus Review Queue',
    description: 'Reviewable Nexus tasks grouped into dedicated pull request flows.',
  });

  const [queueItems, setQueueItems] = useState<ApiReviewQueueItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<QueueTab['id']>('review');

  const refreshQueue = async () => {
    try {
      const nextItems = await listTaskReviewQueue();
      startTransition(() => {
        setQueueItems(nextItems);
        setError(null);
        setIsLoading(false);
      });
    } catch (nextError) {
      startTransition(() => {
        setError(getErrorDetail(nextError, 'Failed to load review queue.'));
        setIsLoading(false);
      });
    }
  };

  useEffect(() => {
    void refreshQueue();
  }, []);

  usePolling(refreshQueue, 5_000, {
    enabled: true,
    runImmediately: false,
  });

  const activeQueueTab = QUEUE_TABS.find(tab => tab.id === activeTab) ?? QUEUE_TABS[0];
  const filteredQueueItems = useMemo(() => {
    const items = queueItems.filter(({ task }) => activeQueueTab.statuses.includes(task.status));
    if (activeQueueTab.id !== 'review') {
      return items;
    }
    return [...items].sort(
      (left, right) =>
        (REVIEW_TAB_STATUS_PRIORITY[left.task.status] ?? Number.MAX_SAFE_INTEGER) -
        (REVIEW_TAB_STATUS_PRIORITY[right.task.status] ?? Number.MAX_SAFE_INTEGER),
    );
  }, [activeQueueTab.id, activeQueueTab.statuses, queueItems]);

  return (
    <div className="flex flex-col gap-4">
      <div className="border-b">
        <div className="-mb-px flex flex-wrap items-center gap-5">
          {QUEUE_TABS.map(tab => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                'inline-flex items-center gap-2 border-b-2 px-0 pb-3 text-sm font-medium transition-colors',
                activeTab === tab.id
                  ? 'border-foreground font-semibold text-foreground'
                  : 'border-transparent text-muted-foreground hover:text-foreground',
              )}
            >
              <span>{tab.label}</span>
              <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                {queueItems.filter(({ task }) => tab.statuses.includes(task.status)).length}
              </span>
            </button>
          ))}
        </div>
      </div>

      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      {isLoading ? (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="size-4 animate-spin" />
          Loading review queue...
        </div>
      ) : filteredQueueItems.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No Nexus tasks are in {activeQueueTab.label}.
        </p>
      ) : (
        <div className="grid gap-3">
          {filteredQueueItems.map(({ task, virtual_pr_count: virtualPrCount }) => {
            const statusMeta = TASK_STATUS_META[task.status];
            const StatusIcon = statusMeta.icon;
            return (
              <Link
                key={task.id}
                to={`/workspace/code-review/nexus/tasks/${task.id}`}
                className="rounded-xl border bg-card px-5 py-4 transition-colors hover:bg-accent/20"
              >
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge
                        variant={statusMeta.badgeVariant}
                        className={cn('gap-1', statusMeta.badgeClassName)}
                      >
                        <StatusIcon className="size-3" />
                        {statusMeta.label}
                      </Badge>
                      <Badge variant="outline">{virtualPrCount} PRs</Badge>
                    </div>
                    <h2 className="mt-3 text-base font-semibold leading-snug">
                      {truncateWords(task.question)}
                    </h2>
                    <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted-foreground">
                      <span>{task.repo ?? 'No repo'}</span>
                      <span>{task.project ?? 'No project'}</span>
                      <span>{task.agent}</span>
                    </div>
                  </div>
                  <div className="shrink-0 text-sm text-muted-foreground">
                    Updated {timeAgo(task.updated_at)}
                  </div>
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
