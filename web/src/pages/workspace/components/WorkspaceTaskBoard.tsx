import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import type { ApiTaskStatus } from '@/api/types';
import type { WorkspaceTaskView } from '../utils';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Select } from '@/components/ui/select';
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
  repoOptions: string[];
  repoFilter: string;
  isLoading: boolean;
  onRepoFilterChange: (repoId: string) => void;
};

export function WorkspaceTaskBoard({
  tasks,
  repoOptions,
  repoFilter,
  isLoading,
  onRepoFilterChange,
}: WorkspaceTaskBoardProps) {
  const filteredTasks = useMemo(() => {
    const byRepo = tasks.filter(task => task.repo === repoFilter);
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
    <section className="space-y-4">
      <div className="max-w-sm">
        <Select
          aria-label="Select repository"
          value={repoFilter}
          onChange={event => onRepoFilterChange(event.target.value)}
        >
          {repoOptions.map(repo => (
            <option key={repo} value={repo}>
              {repo}
            </option>
          ))}
        </Select>
      </div>

      <div className="overflow-x-auto">
        <div className="grid min-w-[720px] grid-cols-4 gap-4">
          {TASK_BOARD_STATUS_ORDER.map(status => {
            const statusMeta = STATUS_META[status];
            const StatusIcon = statusMeta.icon;
            const statusTasks = groupedTasks[status] ?? [];

            return (
              <Card
                key={status}
                className="h-[42rem] max-h-[70vh] min-w-0 gap-4 overflow-hidden py-4"
              >
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
                      {statusTasks.length}
                    </Badge>
                  </div>
                </CardHeader>

                <CardContent className="flex min-h-0 flex-1 pl-4 pr-1">
                  <ScrollArea className="h-full w-full">
                    {statusTasks.length === 0 ? (
                      <p className="mr-2 rounded-md border bg-muted/30 px-3 py-4 text-sm text-muted-foreground">
                        {isLoading ? 'Loading tasks...' : 'No tasks in this column.'}
                      </p>
                    ) : (
                      <div className="mr-2 flex flex-col gap-3">
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
                  </ScrollArea>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </div>
    </section>
  );
}
