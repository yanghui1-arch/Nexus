import { useParams } from 'react-router-dom';
import { AlertCircle, GitBranch } from 'lucide-react';
import { DashboardShell } from '@/components/layout/DashboardShell';
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
import { getTaskById } from '@/data/mockWorkflows';

const LEVEL_STYLES: Record<string, string> = {
  info: 'text-muted-foreground',
  success: 'text-emerald-600',
  warning: 'text-amber-600',
  error: 'text-destructive',
};

export default function TaskDetailPage() {
  const { taskId } = useParams<{ taskId: string }>();
  const task = taskId ? getTaskById(taskId) : undefined;

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
              The requested task ID does not exist: {taskId}
            </CardDescription>
          </CardHeader>
        </Card>
      </DashboardShell>
    );
  }

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
            <div className="flex items-center justify-between gap-3 rounded-md border px-3 py-2">
              <span className="text-muted-foreground">Agent</span>
              <span>{task.agentName}</span>
            </div>
            <div className="flex items-center justify-between gap-3 rounded-md border px-3 py-2">
              <span className="text-muted-foreground">Type</span>
              <span>{task.agentType}</span>
            </div>
            <div className="flex items-center justify-between gap-3 rounded-md border px-3 py-2">
              <span className="text-muted-foreground">Status</span>
              <Badge variant="secondary">{task.status}</Badge>
            </div>
            {task.metadata?.repository ? (
              <div className="flex items-center justify-between gap-3 rounded-md border px-3 py-2">
                <span className="text-muted-foreground">Repository</span>
                <span className="truncate text-right">{task.metadata.repository}</span>
              </div>
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
                    <div key={`${entry.timestamp}-${index}`} className="grid grid-cols-[96px_minmax(0,1fr)] items-start gap-3 rounded-md border bg-card px-3 py-2">
                      <span className="text-xs text-muted-foreground">
                        {new Date(entry.timestamp).toLocaleTimeString()}
                      </span>
                      <span className={cn('text-xs leading-relaxed', LEVEL_STYLES[entry.level] ?? 'text-muted-foreground')}>
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
