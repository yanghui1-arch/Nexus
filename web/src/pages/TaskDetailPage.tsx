import { startTransition, useEffect, useMemo, useState, type ReactNode } from 'react';
import { useParams } from 'react-router-dom';
import { AlertCircle, GitBranch } from 'lucide-react';
import { ApiError, getErrorDetail } from '@/api/client';
import { getTask } from '@/api/tasks';
import type { ApiTask } from '@/api/types';
import { DashboardShell } from '@/components/layout/DashboardShell';
import { Badge } from '@/components/ui/badge';
import { STATUS_META } from '@/lib/workspace-task-view';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { getTaskById } from '@/data/mockWorkflows';
import { usePolling } from '@/lib/usePolling';

type LegacyTask = NonNullable<ReturnType<typeof getTaskById>>;

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
    <DashboardShell title={task.title} description="Task status and metadata.">
      <Card className="h-fit max-w-3xl">
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
    </DashboardShell>
  );
}

export default function TaskDetailPage() {
  const { taskId } = useParams<{ taskId: string }>();
  const legacyTask = useMemo(() => (taskId ? getTaskById(taskId) : undefined), [taskId]);

  const [task, setTask] = useState<ApiTask | null>(null);
  const [useLegacyFallback, setUseLegacyFallback] = useState(
    Boolean(taskId && legacyTask && !isUuidLike(taskId)),
  );
  const [taskError, setTaskError] = useState<string | null>(null);
  const [isLoadingTask, setIsLoadingTask] = useState(Boolean(taskId && isUuidLike(taskId)));

  useEffect(() => {
    startTransition(() => {
      setTask(null);
      setTaskError(null);
      setUseLegacyFallback(Boolean(taskId && legacyTask && !isUuidLike(taskId)));
      setIsLoadingTask(Boolean(taskId && isUuidLike(taskId)));
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

  usePolling(refreshTask, 5_000, {
    enabled: Boolean(taskId && isUuidLike(taskId) && !useLegacyFallback),
  });

  if (useLegacyFallback && legacyTask) {
    return <LegacyTaskDetail task={legacyTask} />;
  }

  if (isLoadingTask && !task) {
    return (
      <DashboardShell title="Task Detail" description="Task status and metadata.">
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
      <DashboardShell title="Task Detail" description="Task status and metadata.">
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
    <DashboardShell title={task.question} description="Task status and metadata.">
      <Card className="h-fit max-w-3xl">
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
          <MetadataRow
            label="Started"
            value={detailValue(task.started_at ? new Date(task.started_at).toLocaleString() : null)}
          />
          <MetadataRow
            label="Finished"
            value={detailValue(task.finished_at ? new Date(task.finished_at).toLocaleString() : null)}
          />
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
    </DashboardShell>
  );
}
