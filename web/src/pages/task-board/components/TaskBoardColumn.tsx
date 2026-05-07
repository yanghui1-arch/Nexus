import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area';
import { STATUS_META, type WorkspaceTaskView } from '@/lib/workspace-task-view';
import type { TaskBoardStatus } from '../utils';
import { TaskBoardTaskCard } from './TaskBoardTaskCard';

type TaskBoardColumnProps = {
  status: TaskBoardStatus;
  tasks: WorkspaceTaskView[];
  isLoading: boolean;
  activeReviewTaskId: string | null;
  onOpenReview: (taskId: string) => void;
};

export function TaskBoardColumn({
  status,
  tasks,
  isLoading,
  activeReviewTaskId,
  onOpenReview,
}: TaskBoardColumnProps) {
  const statusMeta = STATUS_META[status];
  const StatusIcon = statusMeta.icon;

  return (
    <Card className="h-[42rem] max-h-[70vh] min-w-0 gap-4 overflow-hidden py-4">
      <CardHeader className="min-w-0 shrink-0 px-4">
        <div className="flex min-w-0 items-center justify-between gap-2">
          <div className="flex min-w-0 items-center gap-2 text-sm font-medium">
            <StatusIcon
              className={
                status === 'running'
                  ? 'size-4 shrink-0 animate-spin'
                  : 'size-4 shrink-0'
              }
            />
            <span className="truncate">{statusMeta.label}</span>
          </div>
          <Badge variant="secondary" className="shrink-0">
            {tasks.length}
          </Badge>
        </div>
      </CardHeader>

      <CardContent className="flex min-h-0 flex-1 pl-4 pr-1">
        <ScrollArea className="h-full w-full">
          {tasks.length === 0 ? (
            <p className="mr-2 rounded-md border bg-muted/30 px-3 py-4 text-sm text-muted-foreground">
              {isLoading ? 'Loading tasks...' : 'No tasks in this column.'}
            </p>
          ) : (
            <div className="mr-2 flex flex-col gap-3">
              {tasks.map(task => (
                <TaskBoardTaskCard
                  key={task.id}
                  task={task}
                  isOpeningReview={activeReviewTaskId === task.id}
                  onOpenReview={onOpenReview}
                />
              ))}
            </div>
          )}
        </ScrollArea>
      </CardContent>
    </Card>
  );
}
