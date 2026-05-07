import { startTransition, useEffect, useMemo, useState } from 'react';
import {
  CheckCircle2,
  ChevronsUpDown,
  FileCode2,
  GitBranch,
  Loader2,
  MessageSquare,
} from 'lucide-react';
import { getErrorDetail } from '@/api/client';
import {
  getTaskVirtualPullRequestDiff,
  getTaskVirtualPullRequests,
  getTaskWorkItems,
  reviewTaskVirtualPullRequest,
} from '@/api/tasks';
import type {
  ApiTaskWorkItem,
  ApiVirtualPullRequest,
  ApiVirtualPullRequestReviewRequest,
  ApiVirtualPullRequestStatus,
} from '@/api/types';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Textarea } from '@/components/ui/textarea';
import {
  STATUS_META,
  timeAgo,
  type WorkspaceTaskView,
} from '@/lib/workspace-task-view';
import { cn } from '@/lib/utils';
import { usePolling } from '@/lib/usePolling';
import { parseUnifiedDiff, type ParsedDiffLineKind } from '@/lib/reviewDiff';

type WorkspaceCodeReviewProps = {
  tasks: WorkspaceTaskView[];
  isLoading: boolean;
  onTasksReload: () => Promise<void>;
};

type ReviewTarget = {
  task: WorkspaceTaskView;
  workItem: ApiTaskWorkItem | null;
  virtualPr: ApiVirtualPullRequest;
};

type ReviewStatusTone = 'secondary' | 'destructive';

const REVIEW_STATUS_META: Record<
  ApiVirtualPullRequestStatus,
  { label: string; badgeVariant: ReviewStatusTone; badgeClassName: string }
> = {
  ready_for_review: {
    label: 'Open',
    badgeVariant: 'secondary',
    badgeClassName: 'border-transparent bg-emerald-600 text-white hover:bg-emerald-600',
  },
  approved: {
    label: 'Approved',
    badgeVariant: 'secondary',
    badgeClassName: 'border-transparent bg-violet-600 text-white hover:bg-violet-600',
  },
  closed: {
    label: 'Closed',
    badgeVariant: 'destructive',
    badgeClassName: 'border-transparent bg-destructive text-destructive-foreground hover:bg-destructive',
  },
};

function shortCommit(value: string | null | undefined): string {
  if (!value) {
    return '-';
  }
  return value.slice(0, 8);
}

function lineNumberValue(value: number | null): string {
  return value == null ? '' : String(value);
}

function fileChangeTone(kind: ParsedDiffLineKind): string {
  switch (kind) {
    case 'add':
      return 'bg-emerald-50/80 text-emerald-950 dark:bg-emerald-950/35 dark:text-emerald-100';
    case 'remove':
      return 'bg-red-50/80 text-red-950 dark:bg-red-950/35 dark:text-red-100';
    case 'note':
      return 'bg-muted/50 text-muted-foreground';
    default:
      return 'bg-background text-foreground';
  }
}

export function WorkspaceCodeReview({
  tasks,
  isLoading,
  onTasksReload,
}: WorkspaceCodeReviewProps) {
  const reviewableTasks = useMemo(
    () => tasks.filter(task => task.status === 'waiting_for_review' || task.status === 'waiting_for_merge'),
    [tasks],
  );

  const [selectedTaskId, setSelectedTaskId] = useState('');
  const [workItems, setWorkItems] = useState<ApiTaskWorkItem[]>([]);
  const [virtualPrs, setVirtualPrs] = useState<ApiVirtualPullRequest[]>([]);
  const [reviewError, setReviewError] = useState<string | null>(null);
  const [isLoadingReview, setIsLoadingReview] = useState(false);
  const [selectedVirtualPrId, setSelectedVirtualPrId] = useState('');
  const [activeFilePath, setActiveFilePath] = useState('');
  const [reviewComment, setReviewComment] = useState('');
  const [activeReviewAction, setActiveReviewAction] = useState<'approved' | null>(null);
  const [activeReviewId, setActiveReviewId] = useState<string | null>(null);
  const [diffByVirtualPrId, setDiffByVirtualPrId] = useState<Record<string, string>>({});
  const [diffLoadingId, setDiffLoadingId] = useState<string | null>(null);

  useEffect(() => {
    if (!reviewableTasks.length) {
      setSelectedTaskId('');
      return;
    }

    setSelectedTaskId(current => {
      if (current && reviewableTasks.some(task => task.id === current)) {
        return current;
      }
      return reviewableTasks[0].id;
    });
  }, [reviewableTasks]);

  const selectedTask = useMemo(
    () => reviewableTasks.find(task => task.id === selectedTaskId) ?? null,
    [reviewableTasks, selectedTaskId],
  );

  const refreshReviewData = async () => {
    if (!selectedTask) {
      startTransition(() => {
        setWorkItems([]);
        setVirtualPrs([]);
        setDiffByVirtualPrId({});
        setReviewError(null);
        setIsLoadingReview(false);
      });
      return;
    }

    try {
      const [nextWorkItems, nextVirtualPrs] = await Promise.all([
        getTaskWorkItems(selectedTask.id),
        getTaskVirtualPullRequests(selectedTask.id),
      ]);

      startTransition(() => {
        setWorkItems(nextWorkItems);
        setVirtualPrs(nextVirtualPrs);
        setReviewError(null);
        setIsLoadingReview(false);
      });
    } catch (error) {
      startTransition(() => {
        setReviewError(getErrorDetail(error, 'Failed to load review data.'));
        setIsLoadingReview(false);
      });
    }
  };

  useEffect(() => {
    if (!selectedTask) {
      startTransition(() => {
        setWorkItems([]);
        setVirtualPrs([]);
        setDiffByVirtualPrId({});
        setSelectedVirtualPrId('');
        setActiveFilePath('');
        setReviewComment('');
        setReviewError(null);
        setIsLoadingReview(false);
        setDiffLoadingId(null);
        setActiveReviewAction(null);
        setActiveReviewId(null);
      });
      return;
    }

    startTransition(() => {
      setWorkItems([]);
      setVirtualPrs([]);
      setDiffByVirtualPrId({});
      setSelectedVirtualPrId('');
      setActiveFilePath('');
      setReviewComment('');
      setReviewError(null);
      setIsLoadingReview(true);
      setDiffLoadingId(null);
      setActiveReviewAction(null);
      setActiveReviewId(null);
    });

    void refreshReviewData();
  }, [selectedTask?.id]);

  usePolling(refreshReviewData, 5_000, {
    enabled: Boolean(selectedTask),
    runImmediately: false,
  });

  useEffect(() => {
    if (!virtualPrs.length) {
      setSelectedVirtualPrId('');
      return;
    }

    setSelectedVirtualPrId(current => {
      if (current && virtualPrs.some(virtualPr => virtualPr.id === current)) {
        return current;
      }
      return virtualPrs[0].id;
    });
  }, [virtualPrs]);

  const reviewTargets = useMemo<ReviewTarget[]>(() => {
    if (!selectedTask) {
      return [];
    }

    const workItemById = new Map(workItems.map(item => [item.id, item]));
    return virtualPrs.map(virtualPr => ({
      task: selectedTask,
      workItem: workItemById.get(virtualPr.work_item_id) ?? null,
      virtualPr,
    }));
  }, [selectedTask, virtualPrs, workItems]);

  const selectedTarget = useMemo(
    () => reviewTargets.find(target => target.virtualPr.id === selectedVirtualPrId) ?? null,
    [reviewTargets, selectedVirtualPrId],
  );

  const selectedRawDiff = selectedTarget
    ? diffByVirtualPrId[selectedTarget.virtualPr.id] ?? ''
    : '';

  const parsedDiff = useMemo(() => parseUnifiedDiff(selectedRawDiff), [selectedRawDiff]);

  useEffect(() => {
    if (!parsedDiff.files.length) {
      setActiveFilePath('');
      return;
    }

    setActiveFilePath(current => {
      if (current && parsedDiff.files.some(file => file.displayPath === current)) {
        return current;
      }
      return parsedDiff.files[0].displayPath;
    });
  }, [parsedDiff.files]);

  const activeFile = useMemo(
    () =>
      parsedDiff.files.find(file => file.displayPath === activeFilePath) ??
      parsedDiff.files[0] ??
      null,
    [activeFilePath, parsedDiff.files],
  );

  const loadSelectedDiff = async (virtualPrId: string) => {
    if (!selectedTask) {
      return;
    }

    setDiffLoadingId(virtualPrId);
    try {
      const payload = await getTaskVirtualPullRequestDiff(selectedTask.id, virtualPrId);
      startTransition(() => {
        setDiffByVirtualPrId(current => ({
          ...current,
          [virtualPrId]: payload.diff || 'No diff recorded.',
        }));
        setReviewError(null);
        setDiffLoadingId(null);
      });
    } catch (error) {
      startTransition(() => {
        setReviewError(getErrorDetail(error, 'Failed to load virtual PR diff.'));
        setDiffLoadingId(null);
      });
    }
  };

  useEffect(() => {
    if (!selectedTarget) {
      return;
    }

    if (diffByVirtualPrId[selectedTarget.virtualPr.id] !== undefined) {
      return;
    }

    void loadSelectedDiff(selectedTarget.virtualPr.id);
  }, [selectedTarget?.virtualPr.id, diffByVirtualPrId]);

  const submitReview = async (decision: 'approved') => {
    if (!selectedTask || !selectedTarget) {
      return;
    }

    setActiveReviewAction(decision);
    setActiveReviewId(selectedTarget.virtualPr.id);
    try {
      const payload: ApiVirtualPullRequestReviewRequest = {
        decision,
        comment: reviewComment.trim() || null,
      };
      await reviewTaskVirtualPullRequest(selectedTask.id, selectedTarget.virtualPr.id, payload);
      await Promise.all([refreshReviewData(), onTasksReload()]);
      startTransition(() => {
        setReviewComment('');
        setReviewError(null);
        setActiveReviewAction(null);
        setActiveReviewId(null);
      });
    } catch (error) {
      startTransition(() => {
        setReviewError(getErrorDetail(error, 'Failed to submit code review.'));
        setActiveReviewAction(null);
        setActiveReviewId(null);
      });
    }
  };

  const selectedFiles = selectedTarget?.virtualPr.changed_files ?? [];
  const canSubmitReview =
    Boolean(selectedTarget) &&
    selectedTarget?.virtualPr.status === 'ready_for_review' &&
    activeReviewId !== selectedTarget.virtualPr.id;

  return (
    <div className="grid min-h-0 flex-1 gap-4 xl:grid-cols-[320px_280px_minmax(0,1fr)]">
      <Card className="min-h-0 gap-0 overflow-hidden py-0 xl:flex xl:flex-col">
        <div className="flex items-start justify-between gap-3 border-b px-4 py-3">
          <div>
            <p className="text-sm font-semibold">Review Queue</p>
            <p className="mt-1 text-xs text-muted-foreground">
              Reviewable tasks from the current workspace.
            </p>
          </div>
          <Badge variant="outline">{reviewableTasks.length}</Badge>
        </div>

        <ScrollArea className="min-h-0 flex-1">
          <div className="divide-y">
            {isLoading ? (
              <div className="flex items-center gap-2 px-4 py-4 text-sm text-muted-foreground">
                <Loader2 className="size-4 animate-spin" />
                Loading review queue...
              </div>
            ) : reviewableTasks.length === 0 ? (
              <div className="px-4 py-4 text-sm text-muted-foreground">
                No reviewable agent changes yet.
              </div>
            ) : (
              reviewableTasks.map(task => {
                const isActive = task.id === selectedTaskId;
                const statusMeta = STATUS_META[task.status];
                const StatusIcon = statusMeta.icon;

                return (
                  <button
                    key={task.id}
                    type="button"
                    onClick={() => setSelectedTaskId(task.id)}
                    className={cn(
                      'w-full border-l-2 px-4 py-3 text-left transition-colors',
                      isActive
                        ? 'border-l-primary bg-accent/40'
                        : 'border-l-transparent hover:bg-accent/20',
                    )}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <p className="line-clamp-2 text-sm font-medium leading-snug">{task.question}</p>
                      <Badge variant={statusMeta.badgeVariant} className="gap-1 whitespace-nowrap">
                        <StatusIcon className="size-3" />
                        {statusMeta.label}
                      </Badge>
                    </div>
                    <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
                      <span>{task.repo ?? 'No repo'}</span>
                      <span>•</span>
                      <span>{task.agentLabel}</span>
                    </div>
                    <p className="mt-1 text-xs text-muted-foreground">Updated {timeAgo(task.updatedAt)}</p>
                  </button>
                );
              })
            )}
          </div>
        </ScrollArea>
      </Card>

      <Card className="min-h-0 gap-0 overflow-hidden py-0 xl:flex xl:flex-col">
        <div className="flex items-start justify-between gap-3 border-b px-4 py-3">
          <div>
            <p className="text-sm font-semibold">Changed Files</p>
            <p className="mt-1 text-xs text-muted-foreground">
              Files included in the selected agent change.
            </p>
          </div>
          <Badge variant="outline">{selectedFiles.length}</Badge>
        </div>

        <ScrollArea className="min-h-0 flex-1">
          <div className="divide-y">
            {!selectedTarget ? (
              <div className="px-4 py-4 text-sm text-muted-foreground">
                Select a review target from the queue.
              </div>
            ) : isLoadingReview && reviewTargets.length === 0 ? (
              <div className="flex items-center gap-2 px-4 py-4 text-sm text-muted-foreground">
                <Loader2 className="size-4 animate-spin" />
                Loading changed files...
              </div>
            ) : selectedFiles.length === 0 ? (
              <div className="px-4 py-4 text-sm text-muted-foreground">
                No changed files available yet.
              </div>
            ) : (
              selectedFiles.map(path => {
                const file =
                  parsedDiff.files.find(entry => entry.displayPath === path) ??
                  parsedDiff.files.find(entry => entry.displayPath.endsWith(path));
                const nextPath = file?.displayPath ?? path;
                const isActive = nextPath === activeFile?.displayPath;

                return (
                  <button
                    key={path}
                    type="button"
                    onClick={() => setActiveFilePath(nextPath)}
                    className={cn(
                      'w-full border-l-2 px-4 py-3 text-left transition-colors',
                      isActive
                        ? 'border-l-primary bg-accent/40'
                        : 'border-l-transparent hover:bg-accent/20',
                    )}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <FileCode2 className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
                          <p className="truncate font-mono text-xs text-foreground">{nextPath}</p>
                        </div>
                      </div>
                      {file ? (
                        <div className="flex shrink-0 items-center gap-2 text-xs">
                          <span className="text-emerald-600">+{file.additions}</span>
                          <span className="text-red-600">-{file.deletions}</span>
                        </div>
                      ) : null}
                    </div>
                  </button>
                );
              })
            )}
          </div>
        </ScrollArea>
      </Card>

      <Card className="min-h-0 gap-0 overflow-hidden py-0 xl:flex xl:flex-col">
        <div className="border-b px-5 py-4">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
            <div className="min-w-0">
              <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-[0.16em] text-muted-foreground">
                <GitBranch className="size-3.5" />
                Code review
              </div>
              <h2 className="mt-2 text-lg font-semibold leading-snug">
                {selectedTarget?.workItem?.title ?? selectedTask?.question ?? 'Select a review item'}
              </h2>
              <p className="mt-2 max-w-4xl whitespace-pre-wrap text-sm leading-relaxed text-muted-foreground">
                {selectedTarget?.virtualPr.summary ??
                  selectedTarget?.workItem?.description ??
                  'Choose a task from the review queue to inspect the agent-generated patch.'}
              </p>
            </div>

            {selectedTarget ? (
              <div className="flex flex-col gap-2 lg:items-end">
                    <Badge
                      variant={REVIEW_STATUS_META[selectedTarget.virtualPr.status].badgeVariant}
                      className={REVIEW_STATUS_META[selectedTarget.virtualPr.status].badgeClassName}
                    >
                      {REVIEW_STATUS_META[selectedTarget.virtualPr.status].label}
                    </Badge>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => void loadSelectedDiff(selectedTarget.virtualPr.id)}
                  disabled={diffLoadingId === selectedTarget.virtualPr.id}
                >
                  {diffLoadingId === selectedTarget.virtualPr.id ? (
                    <Loader2 className="size-3.5 animate-spin" />
                  ) : (
                    <ChevronsUpDown className="size-3.5" />
                  )}
                  Refresh diff
                </Button>
              </div>
            ) : null}
          </div>

          {selectedTarget ? (
            <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-muted-foreground">
              <span>
                Repo <span className="font-medium text-foreground">{selectedTarget.task.repo ?? '-'}</span>
              </span>
              <span>
                Agent <span className="font-medium text-foreground">{selectedTarget.task.agentLabel}</span>
              </span>
              <span>
                Range{' '}
                <code className="rounded bg-muted px-1.5 py-0.5 text-[11px] text-foreground">
                  {shortCommit(selectedTarget.virtualPr.base_commit)}..{shortCommit(selectedTarget.virtualPr.head_commit)}
                </code>
              </span>
              <span>
                Files{' '}
                <span className="font-medium text-foreground">
                  {selectedTarget.virtualPr.changed_files.length}
                </span>
              </span>
              <span>
                Diff{' '}
                <span className="font-medium text-foreground">
                  +{selectedTarget.virtualPr.additions} / -{selectedTarget.virtualPr.deletions}
                </span>
              </span>
            </div>
          ) : null}

          {reviewTargets.length > 1 ? (
            <div className="mt-4 flex flex-wrap gap-2">
              {reviewTargets.map(target => {
                const isActive = target.virtualPr.id === selectedVirtualPrId;
                return (
                  <button
                    key={target.virtualPr.id}
                    type="button"
                    onClick={() => setSelectedVirtualPrId(target.virtualPr.id)}
                    className={cn(
                      'rounded-md border px-3 py-1.5 text-xs font-medium transition-colors',
                      isActive
                        ? 'border-primary bg-primary/10 text-primary'
                        : 'hover:bg-accent hover:text-accent-foreground',
                    )}
                  >
                    {target.workItem
                      ? `${target.workItem.order_index}. ${target.workItem.title}`
                      : 'Virtual PR'}
                  </button>
                );
              })}
            </div>
          ) : null}
        </div>

        <div className="border-b bg-muted/20 px-5 py-3">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-sm font-medium">{activeFile?.displayPath ?? 'Diff preview'}</p>
              <p className="mt-1 text-xs text-muted-foreground">
                {activeFile
                  ? `+${activeFile.additions} / -${activeFile.deletions}`
                  : 'Select a file to inspect the patch.'}
              </p>
            </div>
          </div>
        </div>

        <ScrollArea className="min-h-0 flex-1 bg-muted/10">
          {!selectedTarget ? (
            <div className="px-5 py-5 text-sm text-muted-foreground">
              Select a review target from the queue.
            </div>
          ) : diffLoadingId === selectedTarget.virtualPr.id && !parsedDiff.files.length ? (
            <div className="flex items-center gap-2 px-5 py-5 text-sm text-muted-foreground">
              <Loader2 className="size-4 animate-spin" />
              Loading diff...
            </div>
          ) : activeFile ? (
            <div className="p-5">
              <div className="overflow-hidden rounded-lg border bg-background">
                {activeFile.hunks.length > 0 ? (
                  activeFile.hunks.map(hunk => (
                    <div key={hunk.id} className="border-t first:border-t-0">
                      <div className="border-b bg-muted/50 px-4 py-2 font-mono text-xs text-muted-foreground">
                        {hunk.header}
                      </div>
                      <div className="font-mono text-xs leading-6">
                        {hunk.lines.map((line, index) => (
                          <div
                            key={`${hunk.id}-${index}`}
                            className={cn(
                              'grid grid-cols-[56px_56px_minmax(0,1fr)] border-b border-border/50 last:border-b-0',
                              fileChangeTone(line.kind),
                            )}
                          >
                            <div className="border-r px-2 py-0.5 text-right text-muted-foreground/80">
                              {lineNumberValue(line.oldLineNumber)}
                            </div>
                            <div className="border-r px-2 py-0.5 text-right text-muted-foreground/80">
                              {lineNumberValue(line.newLineNumber)}
                            </div>
                            <pre className="overflow-x-auto px-3 py-0.5 whitespace-pre">
                              {line.text || ' '}
                            </pre>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="px-4 py-4 text-sm text-muted-foreground">
                    No hunks were parsed for this file.
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="px-5 py-5 text-sm text-muted-foreground">
              No parsed file diff is available for the selected file.
            </div>
          )}
        </ScrollArea>

        <div className="border-t bg-background px-5 py-4">
          <div className="flex items-center gap-2 text-sm font-medium">
            <MessageSquare className="size-4" />
            Review summary
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            Add overall feedback before approving.
          </p>
          <Textarea
            rows={4}
            value={reviewComment}
            onChange={event => setReviewComment(event.target.value)}
            placeholder="Write a summary comment for this review."
            className="mt-3"
            disabled={!selectedTarget || activeReviewId === selectedTarget.virtualPr.id}
          />
          <div className="mt-4 flex flex-wrap items-center justify-end gap-2">
            <Button
              type="button"
              disabled={!canSubmitReview}
              onClick={() => void submitReview('approved')}
            >
              {activeReviewAction === 'approved' ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <CheckCircle2 className="size-4" />
              )}
              Approve
            </Button>
          </div>
          {reviewError ? <p className="mt-3 text-sm text-destructive">{reviewError}</p> : null}
        </div>
      </Card>
    </div>
  );
}
