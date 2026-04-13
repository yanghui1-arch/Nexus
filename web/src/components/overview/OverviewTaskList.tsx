import { ExternalLink, GitBranch } from 'lucide-react';
import { Link } from 'react-router-dom';
import type { AgentTask } from '@/types/agent';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { STATUS_META, formatDuration, timeAgo } from './overview-utils';

type OverviewTaskListProps = {
  tasks: AgentTask[];
};

export function OverviewTaskList({ tasks }: OverviewTaskListProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Task Feed</CardTitle>
        <CardDescription>
          Live and historical tasks from selected project scope.
        </CardDescription>
      </CardHeader>

      <CardContent>
        {tasks.length === 0 ? (
          <p className="rounded-md border bg-muted/30 px-3 py-6 text-center text-sm text-muted-foreground">
            No tasks for the current filter.
          </p>
        ) : (
          <div className="flex flex-col">
            {tasks.map(task => {
              const statusMeta = STATUS_META[task.status];
              const StatusIcon = statusMeta.icon;
              const timeRef =
                task.status === 'running' || task.status === 'waiting'
                  ? task.startTime
                  : task.endTime;

              return (
                <article
                  key={task.id}
                  className="flex flex-col gap-3 border-b py-4 last:border-b-0"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex min-w-0 flex-col gap-2">
                      <div className="flex items-center gap-2">
                        <StatusIcon
                          className={
                            task.status === 'running'
                              ? 'size-4 animate-spin'
                              : 'size-4'
                          }
                        />
                        <Link
                          to={`/task/${task.id}`}
                          className="truncate text-sm font-medium hover:underline"
                        >
                          {task.title}
                        </Link>
                      </div>

                      <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
                        <span>{task.agentName}</span>
                        {task.metadata?.branch ? (
                          <span className="inline-flex items-center gap-1">
                            <GitBranch className="size-3" />
                            <span className="font-mono">{task.metadata.branch}</span>
                          </span>
                        ) : null}
                        {task.metadata?.commit ? (
                          <code>{task.metadata.commit.slice(0, 7)}</code>
                        ) : null}
                        <span>{formatDuration(task.duration)}</span>
                        <span>{timeAgo(timeRef)}</span>
                      </div>

                      {task.error ? (
                        <p className="text-xs text-destructive">{task.error}</p>
                      ) : null}
                    </div>

                    <div className="flex items-center gap-2">
                      <Badge variant={statusMeta.badgeVariant}>{statusMeta.label}</Badge>
                      {task.prUrl ? (
                        <Button asChild size="sm" variant="outline">
                          <a href={task.prUrl} target="_blank" rel="noreferrer">
                            <ExternalLink data-icon="inline-start" />
                            PR
                          </a>
                        </Button>
                      ) : null}
                    </div>
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
