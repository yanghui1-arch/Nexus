import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import type { ApiTaskStatus } from '@/api/types';
import type { WorkspaceTaskView } from '../utils';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardHeader,
} from '@/components/ui/card';
import {
  STATUS_META,
  TASK_BOARD_STATUS_ORDER,
  sortTasksForBoard,
  timeAgo,
} from '../utils';

type WorkspaceTaskBoardProps = {
  tasks: WorkspaceTaskView[];
  repoFilters: string[];
  repoFilter: string;
  isLoading: boolean;
  onRepoFilterChange: (repoId: string) => void;
};

export function WorkspaceTaskBoard({
  tasks,
  repoFilters,
  repoFilter,
  isLoading,
  onRepoFilterChange,
}: WorkspaceTaskBoardProps) {
  const filteredTasks = useMemo(() => {
    const byRepo =
      repoFilter === 'all'
        ? tasks
        : tasks.filter(task => task.repo === repoFilter);
    return sortTasksForBoard(byRepo).filter(task =>
      TASK_BOARD_STATUS_ORDER.includes(task.status),
    );
  }, [tasks, repoFilter]);

  const groupedTasks = useMemo(() => {
    const groups = TASK_BOARD_STATUS_ORDER.reduce(
      (acc, status) => {
        acc[status] = [];
        return acc;
      },
      {} as Partial<Record<ApiTaskStatus, WorkspaceTaskView[]>>,
    );

    filteredTasks.forEach(task => {
      groups[task.status]?.push(task);
    });

    return groups;
  }, [filteredTasks]);

  return (
    <Card>
      <CardHeader className="gap-4">
        <div className="flex flex-wrap gap-2 pt-2"><Button
            type="button"
            variant={repoFilter === 'all' ? 'default' : 'outline'}
            size="sm"
            onClick={() => onRepoFilterChange('all')}
          >
            All repos
          </Button>
          {repoFilters.map(repo => (
            <Button
              key={repo}
              type="button"
              variant={repoFilter === repo ? 'default' : 'outline'}
              size="sm"
              onClick={() => onRepoFilterChange(repo)}
            >
              {repo}
            </Button>
          ))}
        </div>
      </CardHeader>

      <CardContent className="overflow-x-auto">
        <div className="grid min-w-[720px] grid-cols-4 gap-4">
          {TASK_BOARD_STATUS_ORDER.map(status => {
            const statusMeta = STATUS_META[status];
            const StatusIcon = statusMeta.icon;
            const statusTasks = groupedTasks[status] ?? [];

            return (
              <Card key={status} className="min-w-0 gap-4 py-4">
                <CardHeader className="min-w-0 px-4">
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
                      {statusTasks.length}
                    </Badge>
                  </div>
                </CardHeader>

                <CardContent className="min-w-0 px-4">
                  {statusTasks.length === 0 ? (
                    <p className="rounded-md border bg-muted/30 px-3 py-4 text-sm text-muted-foreground">
                      {isLoading ? 'Loading tasks...' : 'No tasks in this column.'}
                    </p>
                  ) : (
                    <div className="flex flex-col gap-3">
                      {statusTasks.map(task => (
                        <article
                          key={task.id}
                          className="min-w-0 rounded-lg border bg-background p-3"
                        >
                          <p className="line-clamp-3 text-sm font-medium leading-snug">
                            {task.question}
                          </p>

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
                            <p className="mt-2 text-xs text-destructive line-clamp-2">{task.error}</p>
                          ) : null}

                          <div className="mt-2 flex flex-col gap-0.5 text-xs text-muted-foreground">
                            <span>{timeAgo(task.createdAt)}</span>
                            <span>Updated {timeAgo(task.updatedAt)}</span>
                          </div>

                          <div className="mt-2 flex justify-end">
                            <Button asChild size="sm" variant="ghost" className="h-7 px-2 text-xs">
                              <Link to={`/task/${task.id}`}>Details</Link>
                            </Button>
                          </div>
                        </article>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}
