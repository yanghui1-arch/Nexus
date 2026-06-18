import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { GitPullRequest, Loader2 } from 'lucide-react';
import { FaGithub } from 'react-icons/fa';
import { Link, Navigate, useParams } from 'react-router-dom';
import { useAppLayout } from '@/components/layout/AppLayout';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { getTaskEvents } from '@/api/tasks';
import type { ApiTaskExecutionEvent } from '@/api/types';
import { useWorkspaceRecords } from '@/lib/useWorkspaceRecords';
import {
  STATUS_META,
  timeAgo,
  type WorkspaceTaskView,
} from '@/lib/workspace-task-view';
import { cn } from '@/lib/utils';
import { TaskBoardRepoSelect } from '@/pages/task-board/components/TaskBoardRepoSelect';
import { ExecutionTimeline } from '@/pages/process-tracking/components/ExecutionTimeline';

const ALL_REPOSITORIES = 'All repositories';
const REVIEW_STATUSES = new Set<WorkspaceTaskView['status']>([
  'waiting_for_review',
  'merged',
  'closed',
]);

type QueueTab = {
  id: 'review' | 'merge' | 'close';
  labelKey: string;
  statuses: WorkspaceTaskView['status'][];
};

const QUEUE_TABS: QueueTab[] = [
  {
    id: 'review',
    labelKey: 'codeReview.review',
    statuses: ['waiting_for_review'],
  },
  {
    id: 'merge',
    labelKey: 'codeReview.merge',
    statuses: ['merged'],
  },
  {
    id: 'close',
    labelKey: 'codeReview.close',
    statuses: ['closed'],
  },
];

const CODE_REVIEW_BADGE_CLASS_NAMES: Partial<Record<WorkspaceTaskView['status'], string>> = {
  waiting_for_review: 'border-transparent bg-emerald-600 text-white hover:bg-emerald-600',
  merged: 'border-transparent bg-violet-100 text-violet-700 hover:bg-violet-100',
  closed: 'border-transparent bg-destructive text-destructive-foreground hover:bg-destructive',
};

function formatTimestamp(value: string | null): string {
  if (!value) {
    return '-';
  }

  const timestamp = Date.parse(value);
  if (Number.isNaN(timestamp)) {
    return '-';
  }

  return new Date(timestamp).toLocaleString();
}

function deriveRepoOptions(tasks: WorkspaceTaskView[]): string[] {
  const repos = Array.from(
    new Set(tasks.map(task => task.repo).filter((repo): repo is string => Boolean(repo))),
  ).sort((left, right) => left.localeCompare(right));

  return [ALL_REPOSITORIES, ...repos];
}

function isReviewTask(task: WorkspaceTaskView): boolean {
  return (
    task.category === 'coding' &&
    (REVIEW_STATUSES.has(task.status) || Boolean(task.externalPullRequestUrl))
  );
}

function sortNewestFirst(tasks: WorkspaceTaskView[]): WorkspaceTaskView[] {
  return [...tasks].sort(
    (left, right) =>
      Date.parse(right.updatedAt || right.createdAt) - Date.parse(left.updatedAt || left.createdAt),
  );
}

export function NexusReviewPage() {
  const { t } = useTranslation();

  useAppLayout({
    title: t('codeReview.title'),
    description: t('codeReview.description'),
  });

  const { taskId } = useParams<{ taskId?: string }>();
  const { taskViews, isLoading } = useWorkspaceRecords();
  const [repoFilter, setRepoFilter] = useState(ALL_REPOSITORIES);
  const [activeTab, setActiveTab] = useState<QueueTab['id']>('review');
  const [timelineEvents, setTimelineEvents] = useState<ApiTaskExecutionEvent[]>([]);
  const [isLoadingTimeline, setIsLoadingTimeline] = useState(false);

  const reviewTasks = useMemo(
    () => sortNewestFirst(taskViews.filter(isReviewTask)),
    [taskViews],
  );
  const repoOptions = useMemo(
    () => deriveRepoOptions(reviewTasks),
    [reviewTasks],
  );

  useEffect(() => {
    if (!repoOptions.includes(repoFilter)) {
      setRepoFilter(ALL_REPOSITORIES);
    }
  }, [repoFilter, repoOptions]);

  const repoVisibleTasks = useMemo(() => {
    if (repoFilter === ALL_REPOSITORIES) {
      return reviewTasks;
    }
    return reviewTasks.filter(task => task.repo === repoFilter);
  }, [repoFilter, reviewTasks]);

  const activeQueueTab = useMemo(
    () => QUEUE_TABS.find(tab => tab.id === activeTab) ?? QUEUE_TABS[0],
    [activeTab],
  );

  const visibleTasks = useMemo(
    () =>
      repoVisibleTasks.filter(task => activeQueueTab.statuses.includes(task.status)),
    [activeQueueTab.statuses, repoVisibleTasks],
  );

  const selectedTask = useMemo(
    () => reviewTasks.find(task => task.id === taskId) ?? null,
    [reviewTasks, taskId],
  );

  useEffect(() => {
    if (!selectedTask?.id) {
      setTimelineEvents([]);
      return;
    }

    let cancelled = false;
    setIsLoadingTimeline(true);
    getTaskEvents(selectedTask.id)
      .then(events => {
        if (!cancelled) setTimelineEvents(events);
      })
      .catch(() => {
        if (!cancelled) setTimelineEvents([]);
      })
      .finally(() => {
        if (!cancelled) setIsLoadingTimeline(false);
      });

    return () => {
      cancelled = true;
    };
  }, [selectedTask?.id, selectedTask?.updatedAt]);

  if (taskId && !isLoading && !selectedTask) {
    return <Navigate to="/code-review/nexus" replace />;
  }

  if (taskId && selectedTask) {
    const statusMeta = STATUS_META[selectedTask.status];
    const badgeClassName = CODE_REVIEW_BADGE_CLASS_NAMES[selectedTask.status];

    return (
      <div className="flex flex-col gap-4">
        <div className="flex items-center gap-2">
          <Button asChild variant="ghost" size="sm">
            <Link to="/code-review/nexus">{t('codeReview.backToQueue')}</Link>
          </Button>
        </div>

        <section className="space-y-6">
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <Badge
                variant={statusMeta.badgeVariant}
                className={badgeClassName}
              >
                {t(`status.${selectedTask.status}`)}
              </Badge>
              <span className="text-sm text-muted-foreground">
                {t('common.updatedRelative', { time: timeAgo(selectedTask.updatedAt) })}
              </span>
            </div>
            <h1 className="line-clamp-2 text-2xl font-normal tracking-tight">
              {selectedTask.question}
            </h1>
          </div>

          <div className="space-y-4">
            <div className="rounded-md border bg-background">
              <div className="border-b px-4 py-3 text-sm font-semibold">{t('common.details')}</div>
              <div className="grid gap-3 px-4 py-4 text-sm sm:grid-cols-2">
                <div className="flex items-center justify-between gap-3 sm:block">
                  <span className="text-muted-foreground">{t('common.repository')}</span>
                  <div className="font-mono text-xs sm:mt-1">{selectedTask.repo ?? '-'}</div>
                </div>
                <div className="flex items-center justify-between gap-3 sm:block">
                  <span className="text-muted-foreground">{t('common.project')}</span>
                  <div className="text-xs sm:mt-1">{selectedTask.project ?? '-'}</div>
                </div>
                <div className="flex items-center justify-between gap-3 sm:block">
                  <span className="text-muted-foreground">{t('common.agent')}</span>
                  <div className="text-xs sm:mt-1">{selectedTask.agentLabel}</div>
                </div>
                <div className="flex items-center justify-between gap-3 sm:block">
                  <span className="text-muted-foreground">{t('common.status')}</span>
                  <div className="text-xs sm:mt-1">{t(`status.${selectedTask.status}`)}</div>
                </div>
                <div className="flex items-center justify-between gap-3 sm:block">
                  <span className="text-muted-foreground">{t('taskDetail.created')}</span>
                  <div className="text-xs sm:mt-1">{formatTimestamp(selectedTask.createdAt)}</div>
                </div>
                <div className="flex items-center justify-between gap-3 sm:block">
                  <span className="text-muted-foreground">{t('common.updated')}</span>
                  <div className="text-xs sm:mt-1">{formatTimestamp(selectedTask.updatedAt)}</div>
                </div>
                <div className="flex items-center justify-between gap-3 sm:block">
                  <span className="text-muted-foreground">{t('taskDetail.started')}</span>
                  <div className="text-xs sm:mt-1">{formatTimestamp(selectedTask.startedAt)}</div>
                </div>
                <div className="flex items-center justify-between gap-3 sm:block">
                  <span className="text-muted-foreground">{t('taskDetail.finished')}</span>
                  <div className="text-xs sm:mt-1">{formatTimestamp(selectedTask.finishedAt)}</div>
                </div>
                <div className="flex items-center justify-between gap-3 sm:col-span-2 sm:block">
                  <span className="text-muted-foreground">{t('codeReview.prLink')}</span>
                  <div className="text-xs sm:mt-1">
                    {selectedTask.externalPullRequestUrl ? (
                      <a
                        href={selectedTask.externalPullRequestUrl}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-2 break-all text-foreground underline-offset-4 hover:underline"
                      >
                        <GitPullRequest className="size-3.5" />
                        {selectedTask.externalPullRequestUrl}
                      </a>
                    ) : (
                      <span className="text-muted-foreground">{t('codeReview.noPrLinked')}</span>
                    )}
                  </div>
                </div>
                {selectedTask.externalIssueUrl ? (
                  <div className="flex items-center justify-between gap-3 sm:col-span-2 sm:block">
                    <span className="text-muted-foreground">{t('codeReview.issueLink')}</span>
                    <div className="text-xs sm:mt-1">
                      <a
                        href={selectedTask.externalIssueUrl}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-2 break-all text-foreground underline-offset-4 hover:underline"
                      >
                        <FaGithub className="size-3.5" />
                        {selectedTask.externalIssueUrl}
                      </a>
                    </div>
                  </div>
                ) : null}
              </div>
            </div>
          </div>

          <div className="min-h-[420px]">
            <ExecutionTimeline events={timelineEvents} isLoading={isLoadingTimeline} />
          </div>
        </section>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="max-w-sm">
        <TaskBoardRepoSelect
          repoOptions={repoOptions}
          value={repoFilter}
          onChange={setRepoFilter}
        />
      </div>

      <div className="border-b">
        <div className="-mb-px flex flex-wrap items-center gap-5">
          {QUEUE_TABS.map(tab => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                'inline-flex items-center gap-2 border-b-2 px-0 pb-3 text-sm font-medium transition-colors',
                activeTab === tab.id
                  ? 'border-foreground font-semibold text-foreground'
                  : 'border-transparent text-muted-foreground hover:text-foreground',
              )}
            >
              <span>{t(tab.labelKey)}</span>
              <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                {repoVisibleTasks.filter(task => tab.statuses.includes(task.status)).length}
              </span>
            </button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="size-4 animate-spin" />
          {t('codeReview.loadingQueue')}
        </div>
      ) : visibleTasks.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          {t('codeReview.emptyQueue', { queue: t(activeQueueTab.labelKey) })}
        </p>
      ) : (
        <div className="grid gap-3">
          {visibleTasks.map(task => {
            const statusMeta = STATUS_META[task.status];
            const StatusIcon = statusMeta.icon;
            const badgeClassName = CODE_REVIEW_BADGE_CLASS_NAMES[task.status];

            return (
              <Link
                key={task.id}
                to={`/code-review/nexus/tasks/${task.id}`}
                className="rounded-xl border bg-card px-5 py-4 transition-colors hover:bg-accent/20"
              >
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge
                        variant={statusMeta.badgeVariant}
                        className={cn('gap-1', badgeClassName)}
                      >
                        <StatusIcon className="size-3" />
                        {t(`status.${task.status}`)}
                      </Badge>
                      {task.externalPullRequestUrl ? (
                        <Badge variant="outline" className="gap-1">
                          <GitPullRequest className="size-3" />
                          {t('codeReview.githubPr')}
                        </Badge>
                      ) : null}
                      {task.externalIssueUrl ? (
                        <Badge variant="outline" className="gap-1">
                          <FaGithub className="size-3" />
                          {t('codeReview.githubIssue')}
                        </Badge>
                      ) : null}
                    </div>
                    <h2 className="mt-3 line-clamp-2 text-base font-normal leading-snug">
                      {task.question}
                    </h2>
                    <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted-foreground">
                      <span>{task.repo ?? t('common.noRepository')}</span>
                      <span>{task.project ?? t('common.noProject')}</span>
                      <span>{task.agentLabel}</span>
                    </div>
                  </div>
                  <div className="shrink-0 text-sm text-muted-foreground">
                    {t('common.updatedRelative', { time: timeAgo(task.updatedAt) })}
                  </div>
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
