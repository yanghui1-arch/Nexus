import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  Loader2,
} from 'lucide-react';
import type { WorkspaceTask } from '@/data/workspaceMockData';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';

type WorkspaceStatsCardsProps = {
  tasks: WorkspaceTask[];
};

export function WorkspaceStatsCards({ tasks }: WorkspaceStatsCardsProps) {
  const activeCount = tasks.filter(
    task => task.status === 'in_progress' || task.status === 'blocked',
  ).length;
  const blockedCount = tasks.filter(task => task.status === 'blocked').length;
  const doneCount = tasks.filter(task => task.status === 'done').length;
  const queuedCount = tasks.filter(task => task.status === 'queued').length;

  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <Card>
        <CardHeader>
          <CardDescription>Active Tasks</CardDescription>
          <CardTitle className="text-2xl">{activeCount}</CardTitle>
        </CardHeader>
        <CardContent className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="size-4 animate-spin" />
          Running or blocked now
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardDescription>Blocked</CardDescription>
          <CardTitle className="text-2xl">{blockedCount}</CardTitle>
        </CardHeader>
        <CardContent className="flex items-center gap-2 text-sm text-muted-foreground">
          <AlertTriangle className="size-4" />
          Need dependency or approval
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
          <CardTitle className="text-2xl">{doneCount}</CardTitle>
        </CardHeader>
        <CardContent className="flex items-center gap-2 text-sm text-muted-foreground">
          <CheckCircle2 className="size-4" />
          Finished and validated
        </CardContent>
      </Card>
    </div>
  );
}
