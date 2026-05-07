import {
  AlertCircle,
  CheckCircle2,
  Clock3,
  Loader2,
} from 'lucide-react';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import type { WorkspaceTaskView } from '@/lib/workspace-task-view';

type WorkspaceStatsCardsProps = {
  tasks: WorkspaceTaskView[];
};

export function WorkspaceStatsCards({ tasks }: WorkspaceStatsCardsProps) {
  const activeCount = tasks.filter(
    task =>
      task.status === 'running' ||
      task.status === 'waiting_for_review' ||
      task.status === 'waiting_for_merge',
  ).length;
  const queuedCount = tasks.filter(task => task.status === 'queued').length;
  const failedCount = tasks.filter(task => task.status === 'failed').length;
  const completedCount = tasks.filter(
    task => task.status === 'merged' || task.status === 'closed',
  ).length;

  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <Card>
        <CardHeader>
          <CardDescription>Active Tasks</CardDescription>
          <CardTitle className="text-2xl">{activeCount}</CardTitle>
        </CardHeader>
        <CardContent className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="size-4 animate-spin" />
          Running or awaiting review
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardDescription>Queued</CardDescription>
          <CardTitle className="text-2xl">{queuedCount}</CardTitle>
        </CardHeader>
        <CardContent className="flex items-center gap-2 text-sm text-muted-foreground">
          <Clock3 className="size-4" />
          Waiting to start
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardDescription>Completed</CardDescription>
          <CardTitle className="text-2xl">{completedCount}</CardTitle>
        </CardHeader>
        <CardContent className="flex items-center gap-2 text-sm text-muted-foreground">
          <CheckCircle2 className="size-4" />
          Merged or closed
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardDescription>Failed</CardDescription>
          <CardTitle className="text-2xl">{failedCount}</CardTitle>
        </CardHeader>
        <CardContent className="flex items-center gap-2 text-sm text-muted-foreground">
          <AlertCircle className="size-4" />
          Requires investigation
        </CardContent>
      </Card>
    </div>
  );
}
