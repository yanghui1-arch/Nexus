import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { classifyFailureReason } from '@/lib/failure-reason-classifier';
import { timeAgo, type WorkspaceTaskView } from '@/lib/workspace-task-view';

type TaskBoardTaskCardProps = {
  task: WorkspaceTaskView;
  onOpenReview: (taskId: string) => void;
};

export function TaskBoardTaskCard({
  task,
  onOpenReview,
}: TaskBoardTaskCardProps) {
  const { t } = useTranslation();
  const failureReason = task.error ? classifyFailureReason(task.error) : null;
  const canOpenReview =
    task.status === 'waiting_for_review' ||
    task.status === 'merged' ||
    task.status === 'closed' ||
    Boolean(task.externalPullRequestUrl);

  return (
    <article className="min-w-0 rounded-lg border bg-background p-3">
      <p className="line-clamp-3 text-sm font-medium leading-snug">{task.question}</p>

      <div className="mt-2 flex flex-col gap-0.5 text-xs text-muted-foreground">
        <span className="truncate" title={task.repo ?? '-'}>
          {task.repo ?? t('common.noRepository')}
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
        <div className="mt-2 flex flex-col gap-1 text-xs text-destructive">
          {failureReason ? <Badge variant="outline">{failureReason}</Badge> : null}
          <p className="line-clamp-2">{task.error}</p>
        </div>
      ) : null}

      <div className="mt-2 flex flex-col gap-0.5 text-xs text-muted-foreground">
        <span>{timeAgo(task.createdAt)}</span>
        <span>{t('common.updatedRelative', { time: timeAgo(task.updatedAt) })}</span>
      </div>

      <div className="mt-2 flex justify-end">
        <div className="flex items-center gap-1">
          {canOpenReview ? (
            <Button
              type="button"
              size="sm"
              variant="secondary"
              className="h-7 px-2 text-xs"
              onClick={() => onOpenReview(task.id)}
            >
              {t('taskBoard.openReview')}
            </Button>
          ) : null}
          <Button asChild size="sm" variant="ghost" className="h-7 px-2 text-xs">
            <Link to={`/task/${task.id}`}>{t('common.details')}</Link>
          </Button>
        </div>
      </div>
    </article>
  );
}
