import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  AlertCircle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  CircleDot,
  Clock3,
  GitPullRequestArrow,
  KanbanSquare,
  ListTodo,
} from 'lucide-react';
import { getErrorDetail } from '@/api/client';
import { getTask } from '@/api/tasks';
import type { ApiFeature, ApiFeatureItemStatus, ApiTask } from '@/api/types';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  FEATURE_ITEM_STATUS_META,
  FEATURE_STATUS_META,
  TABLE_BODY_CLASS,
  TABLE_CARD_CLASS,
  TABLE_HEAD_CLASS,
  TABLE_HEADER_ROW_CLASS,
  TABLE_ROW_CLASS,
} from '../constants';
import {
  calculateFeatureCompletion,
  formatDateTime,
  formatRelativeTime,
  getProjectLabel,
  getTaskPullRequestUrl,
  shortId,
} from '../utils';

type ProposalPlanListProps = {
  features: ApiFeature[];
  onRetryFeatureItem: (featureItemId: string) => Promise<void>;
  retryingFeatureItemId: string | null;
};

function getWorkItemDisplayStatus(itemStatus: ApiFeatureItemStatus, task: ApiTask | null | undefined): ApiFeatureItemStatus {
  return itemStatus === 'failed' || task?.status === 'failed' ? 'failed' : itemStatus;
}

export function ProposalPlanList({ features, onRetryFeatureItem, retryingFeatureItemId }: ProposalPlanListProps) {
  const { t } = useTranslation();
  const [selectedFeatureId, setSelectedFeatureId] = useState<string | null>(null);
  const [expandedItemIds, setExpandedItemIds] = useState<string[]>([]);
  const [tasksById, setTasksById] = useState<Record<string, ApiTask | null>>({});
  const [taskLoadErrorsById, setTaskLoadErrorsById] = useState<Record<string, string>>({});
  const selectedFeature =
    features.find(feature => feature.id === selectedFeatureId) ?? null;
  const selectedFeatureTaskIds = useMemo(
    () =>
      Array.from(
        new Set(
          (selectedFeature?.items ?? [])
            .map(item => item.task_id)
            .filter((taskId): taskId is string => Boolean(taskId)),
        ),
      ),
    [selectedFeature],
  );

  useEffect(() => {
    if (!selectedFeature) {
      return;
    }

    const missingTaskIds = selectedFeatureTaskIds.filter(
      taskId => !(taskId in tasksById),
    );
    if (missingTaskIds.length === 0) {
      return;
    }

    let isCancelled = false;

    void Promise.all(
      missingTaskIds.map(async taskId => {
        try {
          return { taskId, task: await getTask(taskId), loadError: null };
        } catch (error) {
          return {
            taskId,
            task: null,
            loadError: getErrorDetail(error, t('productResearch.workItemTaskLoadFailedDescription')),
          };
        }
      }),
    ).then(entries => {
      if (isCancelled) {
        return;
      }

      setTasksById(current => {
        const next = { ...current };

        for (const entry of entries) {
          next[entry.taskId] = entry.task;
        }

        return next;
      });

      setTaskLoadErrorsById(current => {
        const next = { ...current };

        for (const entry of entries) {
          if (entry.task) {
            delete next[entry.taskId];
          } else if (entry.loadError) {
            next[entry.taskId] = entry.loadError;
          }
        }

        return next;
      });
    });

    return () => {
      isCancelled = true;
    };
  }, [selectedFeature, selectedFeatureTaskIds, tasksById, t]);

  function openFeatureDetail(feature: ApiFeature) {
    setSelectedFeatureId(feature.id);
    setExpandedItemIds((feature.items ?? []).map(item => item.id));
  }

  function closeFeatureDetail() {
    setSelectedFeatureId(null);
    setExpandedItemIds([]);
  }

  function toggleFeatureItem(itemId: string) {
    setExpandedItemIds(current =>
      current.includes(itemId)
        ? current.filter(currentId => currentId !== itemId)
        : [...current, itemId],
    );
  }

  if (features.length === 0) {
    return (
      <div className="rounded-xl border bg-background/70 px-5 py-8 text-sm text-muted-foreground">
        {t('productResearch.planListEmpty')}
      </div>
    );
  }

  return (
    <>
      <div className={TABLE_CARD_CLASS}>
        <Table className="table-fixed">
          <TableHeader>
            <TableRow className={TABLE_HEADER_ROW_CLASS}>
              <TableHead className={`w-[40%] px-5 ${TABLE_HEAD_CLASS}`}>{t('productResearch.feature')}</TableHead>
              <TableHead className={`w-[18%] px-5 ${TABLE_HEAD_CLASS}`}>{t('common.updated')}</TableHead>
              <TableHead className={`w-[22%] px-5 ${TABLE_HEAD_CLASS}`}>{t('productResearch.progress')}</TableHead>
              <TableHead className={`w-[20%] px-5 ${TABLE_HEAD_CLASS}`}>
                {t('productResearch.statistics')}
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody className={TABLE_BODY_CLASS}>
            {features.map(feature => {
              const featureMeta = FEATURE_STATUS_META[feature.status];
              const items = feature.items ?? [];
              const completion = calculateFeatureCompletion(items);
              const completedItems = items.filter(
                item => item.status === 'completed' || item.status === 'closed',
              ).length;
              const activeItems = items.filter(
                item => item.status === 'in_progress',
              ).length;
              const failedItems = items.filter(item => {
                const task = item.task_id ? tasksById[item.task_id] : null;
                return getWorkItemDisplayStatus(item.status, task) === 'failed';
              }).length;

              return (
                <TableRow
                  key={feature.id}
                  tabIndex={0}
                  className={TABLE_ROW_CLASS}
                  onClick={() => openFeatureDetail(feature)}
                  onKeyDown={event => {
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault();
                      openFeatureDetail(feature);
                    }
                  }}
                >
                  <TableCell className="px-5 py-5">
                    <div className="flex items-center gap-4">
                      <div className="flex size-11 items-center justify-center rounded-2xl border border-black/10 bg-black/[0.035]">
                        <KanbanSquare className="size-5 text-black/65" />
                      </div>
                      <div className="flex min-w-0 flex-col gap-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="truncate font-medium text-black">
                            {feature.title}
                          </span>
                          <Badge
                            variant={featureMeta.variant}
                            className={featureMeta.className}
                          >
                            {t(`productResearch.featureStatus.${feature.status}`)}
                          </Badge>
                        </div>
                        <span className="truncate text-sm text-black/55">
                          {getProjectLabel(feature.project, t)}
                        </span>
                      </div>
                    </div>
                  </TableCell>
                  <TableCell className="px-5 py-5">
                    <div className="flex flex-col gap-1 text-sm">
                      <div className="flex items-center gap-2 text-black">
                        <Clock3 className="size-4 text-black/45" />
                        <span>{formatRelativeTime(feature.updated_at)}</span>
                      </div>
                      <span className="text-xs text-black/45">
                        {formatDateTime(feature.updated_at)}
                      </span>
                    </div>
                  </TableCell>
                  <TableCell className="px-5 py-5">
                    <div className="flex flex-col gap-2">
                      <div className="flex items-center justify-between gap-3 text-sm">
                        <span className="font-medium text-black">{completion}%</span>
                        <span className="text-black/45">
                          {completedItems}/{items.length || 0}
                        </span>
                      </div>
                      <div className="h-2 rounded-full bg-black/[0.08]">
                        <div
                          className="h-2 rounded-full bg-foreground transition-[width]"
                          style={{ width: `${completion}%` }}
                        />
                      </div>
                    </div>
                  </TableCell>
                  <TableCell className="px-5 py-5">
                    <div className="flex items-center gap-5 text-sm text-black">
                      <div className="flex items-center gap-2">
                        <ListTodo className="size-4 text-black/45" />
                        <span>{items.length}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <CircleDot className="size-4 text-black/45" />
                        <span>{activeItems}</span>
                      </div>
                      {failedItems > 0 ? (
                        <div className="flex items-center gap-2 text-red-700">
                          <AlertCircle className="size-4" />
                          <span>{failedItems}</span>
                        </div>
                      ) : null}
                      <div className="flex items-center gap-2">
                        <CheckCircle2 className="size-4 text-black/45" />
                        <span>{completedItems}</span>
                      </div>
                    </div>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>

      <Dialog open={selectedFeature !== null} onOpenChange={open => !open && closeFeatureDetail()}>
        <DialogContent className="max-h-[85vh] gap-0 overflow-hidden p-0 sm:max-w-4xl">
          {selectedFeature ? (
            <div className="flex max-h-[85vh] flex-col">
              <DialogHeader className="border-b px-6 py-5">
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                  <div className="flex min-w-0 flex-col gap-2">
                    <DialogTitle className="text-xl">{selectedFeature.title}</DialogTitle>
                    <DialogDescription className="text-sm leading-6">
                      {selectedFeature.description}
                    </DialogDescription>
                  </div>

                  <div className="flex items-center gap-2">
                    <Badge
                      variant={FEATURE_STATUS_META[selectedFeature.status].variant}
                      className={FEATURE_STATUS_META[selectedFeature.status].className}
                    >
                      {t(`productResearch.featureStatus.${selectedFeature.status}`)}
                    </Badge>
                  </div>
                </div>

                <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm text-muted-foreground">
                  <span>{getProjectLabel(selectedFeature.project, t)}</span>
                  <span>{t('productResearch.featureItemsCount', { count: (selectedFeature.items ?? []).length })}</span>
                  <span>{t('common.updatedAt', { time: formatDateTime(selectedFeature.updated_at) })}</span>
                </div>
              </DialogHeader>

              <div className="overflow-y-auto px-6 py-5">
                <div className="flex flex-col gap-5">
                  {(selectedFeature.items ?? []).length === 0 ? (
                    <p className="text-sm text-muted-foreground">
                      {t('productResearch.noFeatureItems')}
                    </p>
                  ) : (
                    (selectedFeature.items ?? []).map(item => {
                      const isExpanded = expandedItemIds.includes(item.id);
                      const task = item.task_id ? tasksById[item.task_id] : null;
                      const pullRequestUrl = getTaskPullRequestUrl(task);
                      const taskLoadError = item.task_id ? taskLoadErrorsById[item.task_id] : null;
                      const displayStatus = getWorkItemDisplayStatus(item.status, task);
                      const itemMeta = FEATURE_ITEM_STATUS_META[displayStatus];
                      const taskError = displayStatus === 'failed'
                        ? task?.error ?? taskLoadError ?? t('productResearch.workItemFailedFallback')
                        : null;
                      const isRetrying = retryingFeatureItemId === item.id;
                      const errorId = `feature-item-${item.id}-error`;

                      return (
                        <div
                          key={item.id}
                          className="border-b pb-4 last:border-b-0 last:pb-0"
                        >
                          <button
                            type="button"
                            className="flex w-full items-start gap-3 text-left"
                            onClick={() => toggleFeatureItem(item.id)}
                          >
                            {isExpanded ? (
                              <ChevronDown className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
                            ) : (
                              <ChevronRight className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
                            )}

                            <div className="flex min-w-0 flex-1 flex-col gap-2">
                              <div className="flex flex-wrap items-center justify-between gap-3">
                                <div className="flex min-w-0 flex-col gap-1">
                                  <span className="text-sm font-medium">
                                    {item.order_index}. {item.title}
                                  </span>
                                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
                                    {item.task_id ? (
                                      <span>{t('productResearch.taskShort', { id: shortId(item.task_id) })}</span>
                                    ) : null}
                                    <span>{t('common.updatedAt', { time: formatDateTime(item.updated_at) })}</span>
                                  </div>
                                </div>

                                <div className="flex items-center gap-2">
                                  {pullRequestUrl ? (
                                    <a
                                      href={pullRequestUrl}
                                      target="_blank"
                                      rel="noreferrer"
                                      className="inline-flex items-center gap-1 text-xs font-medium text-muted-foreground transition-colors hover:text-foreground"
                                      onClick={event => event.stopPropagation()}
                                    >
                                      <GitPullRequestArrow className="size-3.5" />
                                      <span>PR</span>
                                    </a>
                                  ) : null}
                                  <Badge
                                    variant={itemMeta.variant}
                                    className={itemMeta.className}
                                  >
                                    {t(`productResearch.featureItemStatus.${displayStatus}`)}
                                  </Badge>
                                  {displayStatus === 'failed' ? (
                                    <Button
                                      type="button"
                                      size="sm"
                                      variant="outline"
                                      className="h-7 border-red-200 px-2.5 text-xs text-red-700 hover:bg-red-50 hover:text-red-800"
                                      disabled={isRetrying}
                                      aria-describedby={taskError ? errorId : undefined}
                                      onClick={event => {
                                        event.stopPropagation();
                                        void onRetryFeatureItem(item.id);
                                      }}
                                    >
                                      {isRetrying
                                        ? t('productResearch.workItemRetrying')
                                        : t('productResearch.workItemRetry')}
                                    </Button>
                                  ) : null}
                                </div>
                              </div>

                              {taskError ? (
                                <div
                                  id={errorId}
                                  role="alert"
                                  className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm leading-6 text-red-800"
                                >
                                  <span className="font-medium">{t('productResearch.workItemFailed')}</span>
                                  <span className="ml-1">{taskError}</span>
                                </div>
                              ) : null}

                              {isExpanded ? (
                                <p className="text-sm leading-6 text-muted-foreground">
                                  {item.description}
                                </p>
                              ) : null}
                            </div>
                          </button>
                        </div>
                      );
                    })
                  )}
                </div>
              </div>
            </div>
          ) : null}
        </DialogContent>
      </Dialog>
    </>
  );
}
