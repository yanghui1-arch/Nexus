import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { useAppLayout } from '@/components/layout/AppLayout';
import { timeAgo } from '@/lib/workspace-task-view';
import { useWorkspaceRecords } from '@/lib/useWorkspaceRecords';
import {
  ALL_FAILED_TASK_AGENTS,
  ALL_FAILED_TASK_REPOS,
  DEFAULT_FAILED_TASK_FILTERS,
  deriveFailedTaskAgentOptions,
  deriveFailedTaskRepoOptions,
  getVisibleFailedTasks,
  type FailedTaskSortOrder,
} from '@/pages/task-board/failedTaskQueue';

export default function FailedTaskQueuePage() {
  const { t } = useTranslation();
  const { taskViews, isLoading } = useWorkspaceRecords();
  const [repo, setRepo] = useState(DEFAULT_FAILED_TASK_FILTERS.repo);
  const [agent, setAgent] = useState(DEFAULT_FAILED_TASK_FILTERS.agent);
  const [errorKeyword, setErrorKeyword] = useState(DEFAULT_FAILED_TASK_FILTERS.errorKeyword);
  const [sortOrder, setSortOrder] = useState<FailedTaskSortOrder>(DEFAULT_FAILED_TASK_FILTERS.sortOrder);

  useAppLayout({ title: t('failedTaskQueue.title'), description: t('failedTaskQueue.description') });

  const repoOptions = useMemo(() => deriveFailedTaskRepoOptions(taskViews), [taskViews]);
  const agentOptions = useMemo(() => deriveFailedTaskAgentOptions(taskViews), [taskViews]);
  const visibleTasks = useMemo(
    () => getVisibleFailedTasks(taskViews, { repo, agent, errorKeyword, sortOrder }),
    [agent, errorKeyword, repo, sortOrder, taskViews],
  );

  return (
    <section className="space-y-4">
      <Card>
        <CardContent className="grid gap-3 md:grid-cols-4">
          <Select aria-label={t('failedTaskQueue.repoFilter')} value={repo} onChange={event => setRepo(event.target.value)}>
            <option value={ALL_FAILED_TASK_REPOS}>{t('failedTaskQueue.allRepos')}</option>
            {repoOptions.map(option => <option key={option} value={option}>{option}</option>)}
          </Select>
          <Select aria-label={t('failedTaskQueue.agentFilter')} value={agent} onChange={event => setAgent(event.target.value)}>
            <option value={ALL_FAILED_TASK_AGENTS}>{t('failedTaskQueue.allAgents')}</option>
            {agentOptions.map(option => <option key={option} value={option}>{option}</option>)}
          </Select>
          <Select aria-label={t('failedTaskQueue.sortOrder')} value={sortOrder} onChange={event => setSortOrder(event.target.value as FailedTaskSortOrder)}>
            <option value="newest">{t('failedTaskQueue.newestFirst')}</option>
            <option value="oldest">{t('failedTaskQueue.oldestFirst')}</option>
          </Select>
          <Input
            aria-label={t('failedTaskQueue.errorKeyword')}
            value={errorKeyword}
            onChange={event => setErrorKeyword(event.target.value)}
            placeholder={t('failedTaskQueue.errorKeywordPlaceholder')}
          />
        </CardContent>
      </Card>

      {isLoading ? <p className="text-sm text-muted-foreground">{t('failedTaskQueue.loading')}</p> : null}
      {!isLoading && visibleTasks.length === 0 ? <p className="text-sm text-muted-foreground">{t('failedTaskQueue.empty')}</p> : null}

      <div className="space-y-3">
        {visibleTasks.map(task => (
          <Card key={task.id}>
            <CardContent className="space-y-3">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="font-medium">{task.question}</p>
                  <p className="text-xs text-muted-foreground">{task.repo ?? t('common.noRepository')} · {task.agentLabel}</p>
                </div>
                <Badge variant="destructive">{t('status.failed')}</Badge>
              </div>
              {task.error ? <p className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">{task.error}</p> : null}
              <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
                <span>{t('failedTaskQueue.failedRelative', { time: timeAgo(task.finishedAt ?? task.updatedAt) })}</span>
                <Button asChild size="sm" variant="secondary" className="h-7 px-2 text-xs">
                  <Link to={`/task/${task.id}`}>{t('common.details')}</Link>
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </section>
  );
}
