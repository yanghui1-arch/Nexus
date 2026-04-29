import { startTransition, useEffect, useMemo, useState, type ReactNode } from 'react';
import { useParams } from 'react-router-dom';
import { AlertCircle, CheckCircle2, FileText, GitBranch, XCircle } from 'lucide-react';
import { getErrorDetail, ApiError } from '@/api/client';
import {
  getTask,
  getTaskMessages,
  getTaskVirtualPullRequestDiff,
  getTaskVirtualPullRequests,
  getTaskWorkItems,
  reviewTaskVirtualPullRequest,
} from '@/api/tasks';
import type {
  ApiTask,
  ApiTaskMessage,
  ApiTaskWorkItem,
  ApiVirtualPullRequest,
} from '@/api/types';
import { DashboardShell } from '@/components/layout/DashboardShell';
import { STATUS_META } from '@/pages/workspace/utils';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area';
import { cn } from '@/lib/utils';
import { usePolling } from '@/lib/usePolling';
import { getTaskById } from '@/data/mockWorkflows';

type LegacyTask = NonNullable<ReturnType<typeof getTaskById>>;

const LEGACY_LEVEL_STYLES: Record<string, string> = {
  info: 'text-muted-foreground',
  success: 'text-emerald-600',
  warning: 'text-amber-600',
  error: 'text-destructive',
};

function isUuidLike(value: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(
    value,
  );
}

function detailValue(value: string | null | undefined): string {
  if (!value) {
    return '-';
  }
  return value;
}

function messageTone(status: string): string {
  const normalized = status.toLowerCase();
  if (normalized.includes('fail') || normalized.includes('error')) {
    return 'text-destructive';
  }
  if (
    normalized.includes('merge') ||
    normalized.includes('complete') ||
    normalized.includes('closed')
  ) {
    return 'text-emerald-600';
  }
  return 'text-muted-foreground';
}

function renderPayload(
  label: string,
  payload: Record<string, unknown> | null,
): ReactNode {
  if (!payload || Object.keys(payload).length === 0) {
    return null;
  }

  return (
    <div className="mt-2 rounded-md border bg-muted/40 p-2">
      <p className="text-[11px] font-medium uppercase tracking-[0.16em] text-muted-foreground">
        {label}
      </p>
      <pre className="mt-2 overflow-x-auto text-[11px] leading-relaxed text-muted-foreground">
        {JSON.stringify(payload, null, 2)}
      </pre>
    </div>
  );
}

function MetadataRow({
  label,
  value,
}: {
  label: string;
  value: ReactNode;
}) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-md border px-3 py-2">
      <span className="text-muted-foreground">{label}</span>
      <span className="min-w-0 truncate text-right">{value}</span>
    </div>
  );
}

const WORK_ITEM_STATUS_LABEL: Record<ApiTaskWorkItem['status'], string> = {
  pending: 'Pending',
  running: 'Running',
  ready_for_review: 'Ready for Review',
  approved: 'Approved',
  changes_requested: 'Changes Requested',
};

const VIRTUAL_PR_STATUS_LABEL: Record<ApiVirtualPullRequest['status'], string> = {
  ready_for_review: 'Ready for Review',
  approved: 'Approved',
  changes_requested: 'Changes Requested',
};

function shortCommit(value: string | null | undefined): string {
  if (!value) {
    return '-';
  }
  return value.slice(0, 8);
}

function ReviewPanel({
  workItems,
  virtualPrs,
  isLoading,
  error,
  diffByVirtualPrId,
  activeActionId,
  onLoadDiff,
  onReview,
}: {
  workItems: ApiTaskWorkItem[];
  virtualPrs: ApiVirtualPullRequest[];
  isLoading: boolean;
  error: string | null;
  diffByVirtualPrId: Record<string, string>;
  activeActionId: string | null;
  onLoadDiff: (virtualPrId: string) => void;
  onReview: (virtualPrId: string, decision: 'approved' | 'changes_requested') => void;
}) {
  const workItemById = new Map(workItems.map((item) => [item.id, item]));

  return (
    <Card>
      <CardHeader>
        <CardTitle>Nexus Review</CardTitle>
        <CardDescription>Internal work items and virtual PR review state.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {error ? <p className="text-sm text-destructive">{error}</p> : null}
        {isLoading && workItems.length === 0 && virtualPrs.length === 0 ? (
          <p className="text-sm text-muted-foreground">Loading review data...</p>
        ) : workItems.length === 0 ? (
          <p className="text-sm text-muted-foreground">No Nexus work items yet.</p>
        ) : (
          <div className="space-y-3">
            {workItems.map((item) => (
              <div key={item.id} className="rounded-md border px-3 py-3">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-sm font-medium">
                      {item.order_index}. {item.title}
                    </p>
                    <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                      {item.description}
                    </p>
                  </div>
                  <Badge variant={item.status === 'changes_requested' ? 'destructive' : 'secondary'}>
                    {WORK_ITEM_STATUS_LABEL[item.status]}
                  </Badge>
                </div>
                {item.summary ? (
                  <p className="mt-3 whitespace-pre-wrap text-xs leading-relaxed">{item.summary}</p>
                ) : null}
              </div>
            ))}
          </div>
        )}

        {virtualPrs.length > 0 ? (
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-sm font-medium">
              <FileText className="size-4" />
              Virtual PRs
            </div>
            {virtualPrs.map((virtualPr) => {
              const workItem = workItemById.get(virtualPr.work_item_id);
              const canReview = virtualPr.status === 'ready_for_review';
              return (
                <div key={virtualPr.id} className="rounded-md border px-3 py-3">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-sm font-medium">
                        {workItem ? `${workItem.order_index}. ${workItem.title}` : 'Virtual PR'}
                      </p>
                      <p className="mt-1 whitespace-pre-wrap text-xs leading-relaxed text-muted-foreground">
                        {virtualPr.summary}
                      </p>
                    </div>
                    <Badge variant={virtualPr.status === 'changes_requested' ? 'destructive' : 'outline'}>
                      {VIRTUAL_PR_STATUS_LABEL[virtualPr.status]}
                    </Badge>
                  </div>
                  <div className="mt-3 grid gap-2 text-xs text-muted-foreground sm:grid-cols-3">
                    <span>{virtualPr.changed_files.length} files</span>
                    <span>+{virtualPr.additions} / -{virtualPr.deletions}</span>
                    <span>
                      {shortCommit(virtualPr.base_commit)}..{shortCommit(virtualPr.head_commit)}
                    </span>
                  </div>
                  {virtualPr.changed_files.length > 0 ? (
                    <p className="mt-2 truncate text-xs text-muted-foreground">
                      {virtualPr.changed_files.join(', ')}
                    </p>
                  ) : null}
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => onLoadDiff(virtualPr.id)}
                    >
                      <FileText className="size-3.5" />
                      {diffByVirtualPrId[virtualPr.id] ? 'Refresh diff' : 'View diff'}
                    </Button>
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      disabled={!canReview || activeActionId === virtualPr.id}
                      onClick={() => onReview(virtualPr.id, 'approved')}
                    >
                      <CheckCircle2 className="size-3.5" />
                      Approve
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      disabled={!canReview || activeActionId === virtualPr.id}
                      onClick={() => onReview(virtualPr.id, 'changes_requested')}
                    >
                      <XCircle className="size-3.5" />
                      Request changes
                    </Button>
                  </div>
                  {diffByVirtualPrId[virtualPr.id] ? (
                    <pre className="mt-3 max-h-72 overflow-auto rounded-md border bg-muted/40 p-3 text-[11px] leading-relaxed">
                      {diffByVirtualPrId[virtualPr.id]}
                    </pre>
                  ) : null}
                </div>
              );
            })}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

function LegacyTaskDetail({ task }: { task: LegacyTask }) {
  return (
    <DashboardShell
      title={task.title}
      description="Detailed execution timeline and logs."
    >
      <div className="grid gap-6 xl:grid-cols-[340px_minmax(0,1fr)]">
        <Card className="h-fit">
          <CardHeader>
            <CardTitle>Metadata</CardTitle>
            <CardDescription>Task routing and execution context.</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-3 text-sm">
            <MetadataRow label="Agent" value={task.agentName} />
            <MetadataRow label="Type" value={task.agentType} />
            <div className="flex items-center justify-between gap-3 rounded-md border px-3 py-2">
              <span className="text-muted-foreground">Status</span>
              <Badge variant="secondary">{task.status}</Badge>
            </div>
            {task.metadata?.repository ? (
              <MetadataRow label="Repository" value={task.metadata.repository} />
            ) : null}
            {task.metadata?.branch ? (
              <div className="flex items-center justify-between gap-3 rounded-md border px-3 py-2">
                <span className="inline-flex items-center gap-1 text-muted-foreground">
                  <GitBranch className="size-3.5" />
                  Branch
                </span>
                <code>{task.metadata.branch}</code>
              </div>
            ) : null}
            {task.error ? (
              <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                {task.error}
              </div>
            ) : null}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Execution Logs</CardTitle>
            <CardDescription>
              Timestamped events for this task execution.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ScrollArea className="h-[540px] rounded-md border bg-background p-3">
              {task.logs.length === 0 ? (
                <p className="text-sm text-muted-foreground">No logs available.</p>
              ) : (
                <div className="flex flex-col gap-2 pr-2">
                  {task.logs.map((entry, index) => (
                    <div
                      key={`${entry.timestamp}-${index}`}
                      className="grid grid-cols-[96px_minmax(0,1fr)] items-start gap-3 rounded-md border bg-card px-3 py-2"
                    >
                      <span className="text-xs text-muted-foreground">
                        {new Date(entry.timestamp).toLocaleTimeString()}
                      </span>
                      <span
                        className={cn(
                          'text-xs leading-relaxed',
                          LEGACY_LEVEL_STYLES[entry.level] ?? 'text-muted-foreground',
                        )}
                      >
                        {entry.message}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </ScrollArea>
          </CardContent>
        </Card>
      </div>
    </DashboardShell>
  );
}

export default function TaskDetailPage() {
  const { taskId } = useParams<{ taskId: string }>();
  const legacyTask = useMemo(() => (taskId ? getTaskById(taskId) : undefined), [taskId]);

  const [task, setTask] = useState<ApiTask | null>(null);
  const [messages, setMessages] = useState<ApiTaskMessage[]>([]);
  const [workItems, setWorkItems] = useState<ApiTaskWorkItem[]>([]);
  const [virtualPrs, setVirtualPrs] = useState<ApiVirtualPullRequest[]>([]);
  const [diffByVirtualPrId, setDiffByVirtualPrId] = useState<Record<string, string>>({});
  const [useLegacyFallback, setUseLegacyFallback] = useState(
    Boolean(taskId && legacyTask && !isUuidLike(taskId)),
  );
  const [taskError, setTaskError] = useState<string | null>(null);
  const [messagesError, setMessagesError] = useState<string | null>(null);
  const [reviewError, setReviewError] = useState<string | null>(null);
  const [isLoadingTask, setIsLoadingTask] = useState(Boolean(taskId && isUuidLike(taskId)));
  const [isLoadingMessages, setIsLoadingMessages] = useState(false);
  const [isLoadingReview, setIsLoadingReview] = useState(false);
  const [activeReviewActionId, setActiveReviewActionId] = useState<string | null>(null);

  useEffect(() => {
    startTransition(() => {
      setTask(null);
      setMessages([]);
      setWorkItems([]);
      setVirtualPrs([]);
      setDiffByVirtualPrId({});
      setMessagesError(null);
      setReviewError(null);
      setTaskError(null);
      setUseLegacyFallback(Boolean(taskId && legacyTask && !isUuidLike(taskId)));
      setIsLoadingTask(Boolean(taskId && isUuidLike(taskId)));
      setIsLoadingMessages(false);
      setIsLoadingReview(false);
      setActiveReviewActionId(null);
    });
  }, [legacyTask, taskId]);

  const refreshTask = async () => {
    if (!taskId || !isUuidLike(taskId)) {
      return;
    }

    try {
      const nextTask = await getTask(taskId);
      startTransition(() => {
        setTask(nextTask);
        setTaskError(null);
        setUseLegacyFallback(false);
        setIsLoadingTask(false);
      });
    } catch (error) {
      if (error instanceof ApiError && error.status === 404 && legacyTask) {
        startTransition(() => {
          setTask(null);
          setTaskError(null);
          setUseLegacyFallback(true);
          setIsLoadingTask(false);
        });
        return;
      }

      startTransition(() => {
        setTask(null);
        setTaskError(getErrorDetail(error, 'Failed to load task.'));
        setIsLoadingTask(false);
      });
    }
  };

  const refreshMessages = async () => {
    if (!task) {
      return;
    }

    try {
      const nextMessages = await getTaskMessages(task.id);
      startTransition(() => {
        setMessages(nextMessages);
        setMessagesError(null);
        setIsLoadingMessages(false);
      });
    } catch (error) {
      startTransition(() => {
        setMessagesError(getErrorDetail(error, 'Failed to load task events.'));
        setIsLoadingMessages(false);
      });
    }
  };

  const refreshReviewData = async () => {
    if (!task) {
      return;
    }

    try {
      const [nextWorkItems, nextVirtualPrs] = await Promise.all([
        getTaskWorkItems(task.id),
        getTaskVirtualPullRequests(task.id),
      ]);
      startTransition(() => {
        setWorkItems(nextWorkItems);
        setVirtualPrs(nextVirtualPrs);
        setReviewError(null);
        setIsLoadingReview(false);
      });
    } catch (error) {
      startTransition(() => {
        setReviewError(getErrorDetail(error, 'Failed to load Nexus review data.'));
        setIsLoadingReview(false);
      });
    }
  };

  const loadVirtualPrDiff = async (virtualPrId: string) => {
    if (!task) {
      return;
    }

    try {
      const payload = await getTaskVirtualPullRequestDiff(task.id, virtualPrId);
      startTransition(() => {
        setDiffByVirtualPrId((current) => ({
          ...current,
          [virtualPrId]: payload.diff || 'No diff recorded.',
        }));
        setReviewError(null);
      });
    } catch (error) {
      startTransition(() => {
        setReviewError(getErrorDetail(error, 'Failed to load virtual PR diff.'));
      });
    }
  };

  const submitVirtualPrReview = async (
    virtualPrId: string,
    decision: 'approved' | 'changes_requested',
  ) => {
    if (!task) {
      return;
    }

    setActiveReviewActionId(virtualPrId);
    try {
      await reviewTaskVirtualPullRequest(task.id, virtualPrId, { decision });
      await Promise.all([refreshTask(), refreshReviewData()]);
      startTransition(() => {
        setReviewError(null);
        setActiveReviewActionId(null);
      });
    } catch (error) {
      startTransition(() => {
        setReviewError(getErrorDetail(error, 'Failed to submit Nexus review.'));
        setActiveReviewActionId(null);
      });
    }
  };

  usePolling(refreshTask, 5_000, {
    enabled: Boolean(taskId && isUuidLike(taskId) && !useLegacyFallback),
  });

  usePolling(refreshMessages, 5_000, {
    enabled: Boolean(task),
    runImmediately: false,
  });

  usePolling(refreshReviewData, 5_000, {
    enabled: Boolean(task),
    runImmediately: false,
  });

  useEffect(() => {
    if (!task) {
      startTransition(() => {
        setMessages([]);
        setWorkItems([]);
        setVirtualPrs([]);
        setDiffByVirtualPrId({});
        setMessagesError(null);
        setReviewError(null);
        setIsLoadingMessages(false);
        setIsLoadingReview(false);
      });
      return;
    }

    startTransition(() => {
      setMessages([]);
      setWorkItems([]);
      setVirtualPrs([]);
      setDiffByVirtualPrId({});
      setMessagesError(null);
      setReviewError(null);
      setIsLoadingMessages(true);
      setIsLoadingReview(true);
    });
    void refreshMessages();
    void refreshReviewData();
  }, [task?.id]);

  if (useLegacyFallback && legacyTask) {
    return <LegacyTaskDetail task={legacyTask} />;
  }

  if (isLoadingTask && !task) {
    return (
      <DashboardShell
        title="Task Detail"
        description="Task record and execution log stream."
      >
        <Card>
          <CardHeader>
            <CardTitle>Loading task</CardTitle>
            <CardDescription>Fetching the latest task details.</CardDescription>
          </CardHeader>
        </Card>
      </DashboardShell>
    );
  }

  if (!task) {
    return (
      <DashboardShell
        title="Task Detail"
        description="Task record and execution log stream."
      >
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <AlertCircle className="size-4 text-destructive" />
              Task not found
            </CardTitle>
            <CardDescription>
              {taskError ?? `The requested task ID does not exist: ${taskId}`}
            </CardDescription>
          </CardHeader>
        </Card>
      </DashboardShell>
    );
  }

  return (
    <DashboardShell
      title={task.question}
      description="Detailed execution timeline and task status."
    >
      <div className="grid gap-6 xl:grid-cols-[340px_minmax(0,1fr)]">
        <Card className="h-fit">
          <CardHeader>
            <CardTitle>Metadata</CardTitle>
            <CardDescription>Real task record returned by the backend.</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-3 text-sm">
            <MetadataRow label="Agent" value={task.agent} />
            <MetadataRow label="Agent instance" value={task.agent_instance_id} />
            <div className="flex items-center justify-between gap-3 rounded-md border px-3 py-2">
              <span className="text-muted-foreground">Status</span>
              <Badge variant={STATUS_META[task.status].badgeVariant}>
                {STATUS_META[task.status].label}
              </Badge>
            </div>
            <MetadataRow label="Repository" value={detailValue(task.repo)} />
            <MetadataRow label="Project" value={detailValue(task.project)} />
            <MetadataRow label="Created" value={new Date(task.created_at).toLocaleString()} />
            <MetadataRow label="Updated" value={new Date(task.updated_at).toLocaleString()} />
            <MetadataRow label="Started" value={detailValue(task.started_at ? new Date(task.started_at).toLocaleString() : null)} />
            <MetadataRow label="Finished" value={detailValue(task.finished_at ? new Date(task.finished_at).toLocaleString() : null)} />
            {task.result ? (
              <div className="rounded-md border bg-muted/30 px-3 py-2 text-sm">
                <p className="text-xs font-medium uppercase tracking-[0.16em] text-muted-foreground">
                  Result
                </p>
                <p className="mt-2 whitespace-pre-wrap break-words">{task.result}</p>
              </div>
            ) : null}
            {task.error ? (
              <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                {task.error}
              </div>
            ) : null}
          </CardContent>
        </Card>

        <div className="space-y-6">
          <ReviewPanel
            workItems={workItems}
            virtualPrs={virtualPrs}
            isLoading={isLoadingReview}
            error={reviewError}
            diffByVirtualPrId={diffByVirtualPrId}
            activeActionId={activeReviewActionId}
            onLoadDiff={(virtualPrId) => void loadVirtualPrDiff(virtualPrId)}
            onReview={(virtualPrId, decision) => void submitVirtualPrReview(virtualPrId, decision)}
          />

          <Card>
            <CardHeader>
              <CardTitle>Execution Logs</CardTitle>
              <CardDescription>
                Timestamped task events from the backend message stream.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {messagesError ? (
                <p className="mb-3 text-sm text-destructive">{messagesError}</p>
              ) : null}
              <ScrollArea className="h-[540px] rounded-md border bg-background p-3">
                {isLoadingMessages && messages.length === 0 ? (
                  <p className="text-sm text-muted-foreground">Loading task events...</p>
                ) : messages.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No logs available.</p>
                ) : (
                  <div className="flex flex-col gap-2 pr-2">
                    {messages.map((entry, index) => (
                      <div
                        key={`${entry.timestamp}-${index}`}
                        className="rounded-md border bg-card px-3 py-3"
                      >
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <span className="text-xs text-muted-foreground">
                            {new Date(entry.timestamp).toLocaleTimeString()}
                          </span>
                          <Badge variant="outline">{entry.status}</Badge>
                        </div>
                        <p
                          className={cn(
                            'mt-2 text-xs leading-relaxed',
                            messageTone(entry.status),
                          )}
                        >
                          {entry.description ?? 'No description provided.'}
                        </p>
                        {renderPayload('Data', entry.data)}
                        {renderPayload('Meta', entry.meta)}
                      </div>
                    ))}
                  </div>
                )}
              </ScrollArea>
            </CardContent>
          </Card>
        </div>
      </div>
    </DashboardShell>
  );
}
