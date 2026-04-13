import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import type {
  AgentProfile,
  RepoProfile,
  WorkspaceStatus,
  WorkspaceTask,
} from '@/data/workspaceMockData';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardHeader,
} from '@/components/ui/card';
import {
  STATUS_META,
  STATUS_ORDER,
  URGENCY_META,
  sortTasksForBoard,
  timeAgo,
} from './workspace-utils';

type WorkspaceTaskBoardProps = {
  tasks: WorkspaceTask[];
  repos: RepoProfile[];
  agents: AgentProfile[];
  repoFilter: string;
  onRepoFilterChange: (repoId: string) => void;
};

export function WorkspaceTaskBoard({
  tasks,
  repos,
  agents,
  repoFilter,
  onRepoFilterChange,
}: WorkspaceTaskBoardProps) {
  const filteredTasks = useMemo(() => {
    const byRepo =
      repoFilter === 'all'
        ? tasks
        : tasks.filter(task => task.repoId === repoFilter);
    return sortTasksForBoard(byRepo);
  }, [tasks, repoFilter]);

  const groupedTasks = useMemo(() => {
    const groups: Record<WorkspaceStatus, WorkspaceTask[]> = {
      queued: [],
      in_progress: [],
      blocked: [],
      done: [],
    };

    filteredTasks.forEach(task => {
      groups[task.status].push(task);
    });

    return groups;
  }, [filteredTasks]);

  const repoNameById = (repoId: string) => {
    return repos.find(repo => repo.id === repoId)?.name ?? repoId;
  };

  const agentNameById = (agentId: string) => {
    return agents.find(agent => agent.id === agentId)?.name ?? agentId;
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap gap-2 pt-2">
          <Button
            type="button"
            variant={repoFilter === 'all' ? 'default' : 'outline'}
            size="sm"
            onClick={() => onRepoFilterChange('all')}
          >
            All repos
          </Button>
          {repos.map(repo => (
            <Button
              key={repo.id}
              type="button"
              variant={repoFilter === repo.id ? 'default' : 'outline'}
              size="sm"
              onClick={() => onRepoFilterChange(repo.id)}
            >
              {repo.name}
            </Button>
          ))}
        </div>
      </CardHeader>

      <CardContent className="overflow-x-auto">
        <div className="grid gap-4 xl:grid-cols-4">
          {STATUS_ORDER.map(status => {
            const statusMeta = STATUS_META[status];
            const StatusIcon = statusMeta.icon;
            const statusTasks = groupedTasks[status];

            return (
              <Card key={status} className="min-w-0 gap-4 py-4">
                <CardHeader className="min-w-0 px-4">
                  <div className="flex min-w-0 items-center justify-between gap-2">
                    <div className="flex min-w-0 items-center gap-2 text-sm font-medium">
                      <StatusIcon
                        className={
                          status === 'in_progress'
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
                      No tasks in this column.
                    </p>
                  ) : (
                    <div className="flex flex-col gap-3">
                      {statusTasks.map(task => (
                        <article
                          key={task.id}
                          className="min-w-0 rounded-lg border bg-background p-3"
                        >
                          <div className="flex min-w-0 items-start justify-between gap-2">
                            <p className="min-w-0 flex-1 break-words text-sm font-medium leading-snug">
                              {task.title}
                            </p>
                            <Badge
                              className="shrink-0"
                              variant={URGENCY_META[task.urgency].badgeVariant}
                            >
                              {URGENCY_META[task.urgency].label}
                            </Badge>
                          </div>

                          <div className="mt-2 flex min-w-0 flex-col gap-1 text-xs text-muted-foreground">
                            <span className="truncate" title={repoNameById(task.repoId)}>
                              {repoNameById(task.repoId)}
                            </span>
                            <span className="truncate" title={agentNameById(task.agentId)}>
                              {agentNameById(task.agentId)}
                            </span>
                          </div>

                          <div className="mt-3 flex flex-col gap-1.5">
                            <div className="h-1.5 w-full rounded-full bg-muted">
                              <div
                                className="h-full rounded-full bg-primary"
                                style={{
                                  width: `${Math.max(0, Math.min(100, task.progress))}%`,
                                }}
                              />
                            </div>
                            <div className="flex items-center justify-between text-xs text-muted-foreground">
                              <span>{timeAgo(task.createdAt)}</span>
                              <span>{task.progress}%</span>
                            </div>
                          </div>

                          <div className="mt-3 flex items-center justify-between gap-2">
                            <Badge className="shrink-0" variant={statusMeta.badgeVariant}>
                              {statusMeta.label}
                            </Badge>
                            <Button asChild size="sm" variant="ghost">
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
