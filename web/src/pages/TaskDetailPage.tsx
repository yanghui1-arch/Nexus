import { startTransition, useEffect, useMemo, useState, type ReactNode } from 'react';
import { useParams } from 'react-router-dom';
import { AlertCircle, GitBranch } from 'lucide-react';
import { getErrorDetail, ApiError } from '@/api/client';
import { getTask, getTaskMessages } from '@/api/tasks';
import type { ApiTask, ApiTaskMessage } from '@/api/types';
import { DashboardShell } from '@/components/layout/DashboardShell';
import { STATUS_META } from '@/pages/workspace/utils';
import { Badge } from '@/components/ui/badge';
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
  const [useLegacyFallback, setUseLegacyFallback] = useState(
    Boolean(taskId && legacyTask && !isUuidLike(taskId)),
  );
  const [taskError, setTaskError] = useState<string | null>(null);
  const [messagesError, setMessagesError] = useState<string | null>(null);
  const [isLoadingTask, setIsLoadingTask] = useState(Boolean(taskId && isUuidLike(taskId)));
  const [isLoadingMessages, setIsLoadingMessages] = useState(false);

  useEffect(() => {
    startTransition(() => {
      setTask(null);
      setMessages([]);
      setMessagesError(null);
      setTaskError(null);
      setUseLegacyFallback(Boolean(taskId && legacyTask && !isUuidLike(taskId)));
      setIsLoadingTask(Boolean(taskId && isUuidLike(taskId)));
      setIsLoadingMessages(false);
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

  usePolling(refreshTask, 5_000, {
    enabled: Boolean(taskId && isUuidLike(taskId) && !useLegacyFallback),
  });

  usePolling(refreshMessages, 5_000, {
    enabled: Boolean(task),
    runImmediately: false,
  });

  useEffect(() => {
    if (!task) {
      startTransition(() => {
        setMessages([]);
        setMessagesError(null);
        setIsLoadingMessages(false);
      });
      return;
    }

    startTransition(() => {
      setMessages([]);
      setMessagesError(null);
      setIsLoadingMessages(true);
    });
    void refreshMessages();
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
    </DashboardShell>
  );
}

