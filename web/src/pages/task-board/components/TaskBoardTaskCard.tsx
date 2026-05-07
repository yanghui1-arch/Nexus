import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { timeAgo, type WorkspaceTaskView } from '@/lib/workspace-task-view';

type TaskBoardTaskCardProps = {
  task: WorkspaceTaskView;
  isOpeningReview: boolean;
  onOpenReview: (taskId: string) => void;
};

export function TaskBoardTaskCard({
  task,
  isOpeningReview,
  onOpenReview,
}: TaskBoardTaskCardProps) {
  return (
    <article className="min-w-0 rounded-lg border bg-background p-3">
      <p className="line-clamp-3 text-sm font-medium leading-snug">{task.question}</p>

      <div className="mt-2 flex flex-col gap-0.5 text-xs text-muted-foreground">
        <span className="truncate" title={task.repo ?? '-'}>
          {task.repo ?? 'No repo'}
        </span>
        <span className="truncate" title={task.agentLabel}>
          {task.agentLabel}
        </span>
        {task.project ? (
          <span className="truncate" title={task.project}>
            {task.project}
          </span>
        ) : null}
      </div>

      {task.error ? (
        <p className="mt-2 line-clamp-2 text-xs text-destructive">{task.error}</p>
      ) : null}

      <div className="mt-2 flex flex-col gap-0.5 text-xs text-muted-foreground">
        <span>{timeAgo(task.createdAt)}</span>
        <span>Updated {timeAgo(task.updatedAt)}</span>
      </div>

      <div className="mt-2 flex justify-end">
        <div className="flex items-center gap-1">
          {task.status === 'waiting_for_review' ? (
            <Button
              type="button"
              size="sm"
              variant="secondary"
              className="h-7 px-2 text-xs"
              disabled={isOpeningReview}
              onClick={() => onOpenReview(task.id)}
            >
              {isOpeningReview ? 'Opening...' : 'To Review'}
            </Button>
          ) : null}
          <Button asChild size="sm" variant="ghost" className="h-7 px-2 text-xs">
            <Link to={`/task/${task.id}`}>Details</Link>
          </Button>
        </div>
      </div>
    </article>
  );
}
