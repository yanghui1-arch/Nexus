import { startTransition, useCallback, useEffect, useState } from 'react';
import {
  ArrowLeft,
  ExternalLink,
  Loader2,
} from 'lucide-react';
import type { ApiTaskReviewSummary } from '@/api/types';
import { getErrorDetail } from '@/api/client';
import { getTaskReviewSummary, updateTaskStatus } from '@/api/tasks';
import { DashboardShell } from '@/components/layout/DashboardShell';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { usePolling } from '@/lib/usePolling';
import {
  Link,
  Navigate,
  useNavigate,
  useParams,
} from 'react-router-dom';
import { REVIEW_STATUS_META } from '../utils/constants';
import { TASK_STATUS_META } from '../utils/status';

function formatAgentLabel(value: string): string {
  if (!value) {
    return '-';
  }
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function formatSubmittedAt(value: string): string {
  const timestamp = Date.parse(value);
  if (Number.isNaN(timestamp)) {
    return '-';
  }
  return new Date(timestamp).toLocaleString();
}

function truncateTitle(value: string, maxWords = 150): string {
  const words = value.trim().split(/\s+/);
  return words.length > maxWords ? `${words.slice(0, maxWords).join(' ')}...` : value;
}

function latestSubmittedAt(summary: ApiTaskReviewSummary): string | null {
  return summary.virtual_prs.reduce<string | null>((latest, virtualPr) => {
    if (!latest) {
      return virtualPr.created_at;
    }
    return Date.parse(virtualPr.created_at) > Date.parse(latest)
      ? virtualPr.created_at
      : latest;
  }, null);
}

function mergeBlockReason(summary: ApiTaskReviewSummary): string | null {
  if (summary.task.status === 'waiting_for_merge') {
    return null;
  }
  if (summary.task.status === 'merged') {
    return 'This pull request is already merged.';
  }

  const blockedPullRequests = summary.virtual_prs
    .map(virtualPr => {
      if (virtualPr.status === 'approved' || virtualPr.status === 'closed') {
        return null;
      }
      const workItem = summary.work_items.find(item => item.id === virtualPr.work_item_id);
      const title = workItem?.title ?? 'Virtual pull request';
      const statusLabel = REVIEW_STATUS_META[virtualPr.status].label;
      return `${title} (${statusLabel})`;
    })
    .filter((value): value is string => value !== null);

  if (blockedPullRequests.length > 0) {
    return `Cannot merge because:\n${blockedPullRequests.join('\n')}`;
  }

  if (summary.task.status === 'closed') {
    return 'This pull request is closed.';
  }

  return `Merge is unavailable while the task status is ${TASK_STATUS_META[summary.task.status].label}.`;
}

export function TaskReviewSummaryPage() {
  const navigate = useNavigate();
  const { taskId } = useParams<{ taskId: string }>();
  const [summary, setSummary] = useState<ApiTaskReviewSummary | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isMerging, setIsMerging] = useState(false);
  const [isClosing, setIsClosing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refreshSummary = useCallback(async () => {
    if (!taskId) {
      return;
    }

    try {
      const nextSummary = await getTaskReviewSummary(taskId);
      startTransition(() => {
        setSummary(nextSummary);
        setError(null);
        setIsLoading(false);
      });
    } catch (nextError) {
      startTransition(() => {
        setError(getErrorDetail(nextError, 'Failed to load review summary.'));
        setIsLoading(false);
      });
    }
  }, [taskId]);

  useEffect(() => {
    void refreshSummary();
  }, [refreshSummary]);

  usePolling(refreshSummary, 5_000, {
    enabled: Boolean(taskId),
    runImmediately: false,
  });

  useEffect(() => {
    if (!summary || summary.virtual_prs.length !== 1) {
      return;
    }

    navigate(
      `/workspace/code-review/nexus/tasks/${summary.task.id}/pull-requests/${summary.virtual_prs[0].id}`,
      { replace: true },
    );
  }, [navigate, summary]);

  if (!taskId) {
    return <Navigate to="/workspace/code-review/nexus" replace />;
  }

  const taskStatusMeta = summary ? TASK_STATUS_META[summary.task.status] : null;
  const lastSubmittedAt = summary ? latestSubmittedAt(summary) : null;
  const mergeDisabledReason = summary ? mergeBlockReason(summary) : 'Task review summary is unavailable.';
  const canMerge = summary?.task.status === 'waiting_for_merge';
  const canClose = summary?.task.status === 'waiting_for_review' || summary?.task.status === 'waiting_for_merge';

  const handleMerge = useCallback(async () => {
    if (!taskId || !canMerge || isMerging) {
      return;
    }

    try {
      setIsMerging(true);
      const updatedTask = await updateTaskStatus(taskId, { status: 'merged' });
      startTransition(() => {
        setSummary(current => (current ? { ...current, task: updatedTask } : current));
        setError(null);
      });
    } catch (nextError) {
      startTransition(() => {
        setError(getErrorDetail(nextError, 'Failed to merge task.'));
      });
    } finally {
      setIsMerging(false);
    }
  }, [canMerge, isMerging, taskId]);

  const handleClose = useCallback(async () => {
    if (!taskId || !canClose || isClosing) {
      return;
    }

    try {
      setIsClosing(true);
      const updatedTask = await updateTaskStatus(taskId, { status: 'closed' });
      startTransition(() => {
        setSummary(current => (current ? { ...current, task: updatedTask } : current));
        setError(null);
      });
    } catch (nextError) {
      startTransition(() => {
        setError(getErrorDetail(nextError, 'Failed to close task.'));
      });
    } finally {
      setIsClosing(false);
    }
  }, [canClose, isClosing, taskId]);

  return (
    <DashboardShell
      title="Nexus Pull Requests"
      description="Choose which agent-created pull request to review for this task."
    >
      <div className="flex flex-col gap-4">
        <div className="flex items-center gap-2">
          <Button asChild variant="ghost" size="sm">
            <Link to="/workspace/code-review/nexus">
              <ArrowLeft className="size-4" />
              Back to queue
            </Link>
          </Button>
        </div>

        <section className="space-y-6">
          <div className="space-y-3">
            <h1 className="text-2xl font-semibold tracking-tight">
              {summary?.task.question
                ? truncateTitle(summary.task.question)
                : 'Loading task review summary'}
            </h1>
          </div>

          {error ? <p className="text-sm text-destructive">{error}</p> : null}
          {isLoading ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="size-4 animate-spin" />
              Loading pull request options...
            </div>
          ) : !summary ? (
            <p className="text-sm text-muted-foreground">Task review summary is unavailable.</p>
          ) : (
            <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_300px] lg:items-start">
              <div className="space-y-3">
                {summary.virtual_prs.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No pull requests are ready for review yet.</p>
                ) : (
                  summary.virtual_prs.map((virtualPr) => {
                    const workItem =
                      summary.work_items.find(item => item.id === virtualPr.work_item_id) ?? null;

                    return (
                      <Link
                        key={virtualPr.id}
                        to={`/workspace/code-review/nexus/tasks/${summary.task.id}/pull-requests/${virtualPr.id}`}
                        className="block overflow-hidden rounded-xl border bg-card px-5 py-4 transition-colors hover:bg-accent/20"
                      >
                        <div className="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
                          <div className="min-w-0 flex-1">
                            <div className="flex flex-wrap items-center gap-2">
                              <Badge
                                variant={REVIEW_STATUS_META[virtualPr.status].badgeVariant}
                                className={REVIEW_STATUS_META[virtualPr.status].badgeClassName}
                              >
                                {REVIEW_STATUS_META[virtualPr.status].label}
                              </Badge>
                              <span className="truncate text-sm font-medium">
                                {workItem?.title ?? 'Virtual pull request'}
                              </span>
                            </div>
                            {virtualPr.summary ? (
                              <p className="mt-2 line-clamp-2 text-sm text-muted-foreground">
                                {virtualPr.summary}
                              </p>
                            ) : null}
                          </div>
                          <div className="shrink-0 xl:text-right">
                            <div className="mt-2 flex items-center gap-2 font-mono text-xs xl:justify-end">
                              <span className="text-emerald-600">+{virtualPr.additions}</span>
                              <span className="text-muted-foreground">/</span>
                              <span className="text-red-600">-{virtualPr.deletions}</span>
                              <span className="text-muted-foreground">
                                {virtualPr.changed_files.length} files
                              </span>
                            </div>
                          </div>
                        </div>
                      </Link>
                    );
                  })
                )}
              </div>

              <aside className="space-y-4 self-start">
                <div className="rounded-md border bg-background">
                  <div className="border-b px-4 py-3 text-sm font-semibold">Details</div>
                  <div className="space-y-3 px-4 py-4 text-sm">
                    {taskStatusMeta ? (
                      <div className="flex items-center justify-between gap-3">
                        <span className="text-muted-foreground">Status</span>
                        <Badge
                          variant={taskStatusMeta.badgeVariant}
                          className={taskStatusMeta.badgeClassName}
                        >
                          {taskStatusMeta.label}
                        </Badge>
                      </div>
                    ) : null}
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-muted-foreground">Pull requests</span>
                      <span>{summary.virtual_prs.length}</span>
                    </div>
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-muted-foreground">Agents</span>
                      <span className="font-mono text-xs">{formatAgentLabel(summary.task.agent)}</span>
                    </div>
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-muted-foreground">Latest submission</span>
                      <span className="text-right text-xs">
                        {lastSubmittedAt ? formatSubmittedAt(lastSubmittedAt) : '-'}
                      </span>
                    </div>
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-muted-foreground">Repo</span>
                      <span className="truncate font-mono text-xs">{summary.task.repo ?? '—'}</span>
                    </div>
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-muted-foreground">Project</span>
                      <span className="truncate text-xs">{summary.task.project ?? '—'}</span>
                    </div>
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-muted-foreground">GitHub PR</span>
                      <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                        <ExternalLink className="size-3" />
                        Unavailable
                      </span>
                    </div>
                  </div>
                  <div className="border-t px-4 py-4">
                    {!canMerge && mergeDisabledReason ? (
                      <p className="mb-2 text-xs text-muted-foreground whitespace-pre-line">
                        {mergeDisabledReason}
                      </p>
                    ) : null}
                    <div
                      className={canMerge ? 'w-full' : 'w-full cursor-not-allowed'}
                      title={mergeDisabledReason ?? undefined}
                    >
                      <Button
                        type="button"
                        onClick={() => void handleMerge()}
                        disabled={!canMerge || isMerging}
                        className="w-full cursor-pointer"
                      >
                        {isMerging ? <Loader2 className="size-4 animate-spin" /> : null}
                        {summary.task.status === 'merged' ? 'Merged' : 'Merge'}
                      </Button>
                    </div>
                    <Button
                      type="button"
                      variant="destructive"
                      onClick={() => void handleClose()}
                      disabled={!canClose || isClosing}
                      className="mt-2 w-full cursor-pointer"
                    >
                      {isClosing ? <Loader2 className="size-4 animate-spin" /> : null}
                      {summary.task.status === 'closed' ? 'Closed' : 'Close'}
                    </Button>
                  </div>
                </div>
                {summary.task.external_issue_url ? (
                  <Button asChild variant="outline" size="sm" className="w-full justify-start">
                    <a
                      href={summary.task.external_issue_url}
                      target="_blank"
                      rel="noreferrer"
                    >
                      <ExternalLink className="size-4" />
                      Open issue
                    </a>
                  </Button>
                ) : null}
              </aside>
            </div>
          )}
        </section>
      </div>
    </DashboardShell>
  );
}
