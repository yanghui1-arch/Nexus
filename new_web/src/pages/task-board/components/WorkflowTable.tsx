import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import {
  Clock,
  Loader2,
  Users,
  AlertTriangle,
  CheckCircle2,
  ArrowRight,
  Funnel,
  X,
  type LucideIcon,
} from 'lucide-react';
import type { ApiAgentKind } from '@/api/types';
import { cn } from '@/lib/utils';
import {
  TASK_BOARD_STATUS_ORDER,
  TASK_BOARD_TABS,
  type TaskBoardAgentFilter,
  type TaskBoardStatus,
  type TaskBoardStatusFilter,
  type TaskBoardTab,
} from '../utils';
import type { WorkspaceTaskView } from '@/lib/workspace-task-view';

type WorkflowTableProps = {
  groupedTasks: Record<TaskBoardStatus, WorkspaceTaskView[]>;
  activeTab: TaskBoardTab;
  onTabChange: (tab: TaskBoardTab) => void;
  isFilterOpen: boolean;
  onFilterOpenChange: (open: boolean) => void;
  statusFilter: TaskBoardStatusFilter;
  onStatusFilterChange: (status: TaskBoardStatusFilter) => void;
  agentFilter: TaskBoardAgentFilter;
  onAgentFilterChange: (agent: TaskBoardAgentFilter) => void;
  agentOptions: ApiAgentKind[];
  onClearFilters: () => void;
};

const WORKFLOW_ROWS: {
  status: TaskBoardStatus;
  icon: LucideIcon;
  descriptionKey: string;
  color: string;
  iconBg: string;
}[] = [
  {
    status: 'queued',
    icon: Clock,
    descriptionKey: 'taskBoard.tasksWaiting',
    color: 'text-[hsl(80,85%,40%)]',
    iconBg: 'bg-[hsl(80,85%,90%)]',
  },
  {
    status: 'running',
    icon: Loader2,
    descriptionKey: 'taskBoard.activelyRunning',
    color: 'text-gray-600',
    iconBg: 'bg-gray-100',
  },
  {
    status: 'waiting_for_review',
    icon: Users,
    descriptionKey: 'taskBoard.pullRequestsReady',
    color: 'text-orange-600',
    iconBg: 'bg-orange-50',
  },
  {
    status: 'failed',
    icon: AlertTriangle,
    descriptionKey: 'taskBoard.tasksNeedAttention',
    color: 'text-red-600',
    iconBg: 'bg-red-50',
  },
  {
    status: 'merged',
    icon: CheckCircle2,
    descriptionKey: 'taskBoard.successfullyMerged',
    color: 'text-green-600',
    iconBg: 'bg-green-50',
  },
];

function getAgentLabelKey(agent: ApiAgentKind): string {
  switch (agent) {
    case 'tela':
      return 'workspaceSettings.agentTela';
    case 'sophie':
      return 'workspaceSettings.agentSophie';
    case 'jules':
      return 'workspaceSettings.agentJules';
    case 'marc':
      return 'workspaceSettings.agentMarc';
    case 'assistant':
      return 'workspaceSettings.agentAssistant';
  }
}

function AvatarStack({ count }: { count: number }) {
  const displayCount = Math.min(count, 4);
  const extra = count - displayCount;
  const colors = ['bg-gray-300', 'bg-gray-400', 'bg-gray-500', 'bg-gray-600'];

  return (
    <div className="flex -space-x-2">
      {Array.from({ length: displayCount }).map((_, i) => (
        <div
          key={i}
          className={cn('size-6 rounded-full border-2 border-white', colors[i % colors.length])}
        />
      ))}
      {extra > 0 ? (
        <div className="flex size-6 items-center justify-center rounded-full border-2 border-white bg-gray-200 text-[10px] font-medium text-gray-600">
          +{extra}
        </div>
      ) : null}
    </div>
  );
}

export function WorkflowTable({
  groupedTasks,
  activeTab,
  onTabChange,
  isFilterOpen,
  onFilterOpenChange,
  statusFilter,
  onStatusFilterChange,
  agentFilter,
  onAgentFilterChange,
  agentOptions,
  onClearFilters,
}: WorkflowTableProps) {
  const { t } = useTranslation();
  const hasActiveFilters =
    activeTab !== 'allTasks' || statusFilter !== 'all' || agentFilter !== 'all';
  const rows = WORKFLOW_ROWS.filter(row => {
    if (statusFilter !== 'all') {
      return row.status === statusFilter;
    }
    if (hasActiveFilters) {
      return (groupedTasks[row.status]?.length ?? 0) > 0;
    }
    return true;
  });

  return (
    <div className="rounded-2xl border border-gray-200/60 bg-white">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-gray-100 px-6 py-4">
        <div className="flex items-center gap-3">
          <h2 className="text-base font-bold text-[hsl(0,0%,8%)]">{t('taskBoard.workflows')}</h2>
          <span className="flex items-center gap-1.5 text-xs text-gray-400">
            <span className="size-1.5 rounded-full bg-green-400 animate-pulse" />
            {t('taskBoard.live')}
          </span>
        </div>
        <div className="min-w-0 flex-1 overflow-x-auto sm:flex-none">
          <div className="flex w-max items-center gap-1 rounded-lg bg-gray-100 p-0.5">
          {TASK_BOARD_TABS.map(tab => (
            <button
              key={tab}
              type="button"
              onClick={() => onTabChange(tab)}
              className={cn(
                'rounded-md px-3.5 py-1.5 text-xs font-medium transition-all',
                activeTab === tab
                  ? 'bg-[hsl(0,0%,8%)] text-white shadow-sm'
                  : 'text-gray-500 hover:text-gray-700',
              )}
            >
              {t(`common.${tab}`)}
            </button>
          ))}
          </div>
        </div>
        <div className="relative">
          <button
            type="button"
            onClick={() => onFilterOpenChange(!isFilterOpen)}
            className={cn(
              'inline-flex items-center gap-1.5 rounded-lg border bg-white px-3 py-1.5 text-xs font-medium transition-colors hover:bg-gray-50',
              hasActiveFilters
                ? 'border-[hsl(80,60%,65%)] text-[hsl(80,85%,35%)]'
                : 'border-gray-200 text-gray-600',
            )}
          >
            <Funnel className="size-3.5" />
            {t('common.filters')}
          </button>

          {isFilterOpen ? (
            <div className="absolute right-0 top-full z-20 mt-2 w-72 rounded-xl border border-gray-200 bg-white p-4 shadow-lg">
              <div className="flex items-center justify-between">
                <p className="text-sm font-semibold text-[hsl(0,0%,8%)]">
                  {t('taskBoard.filterTitle')}
                </p>
                <button
                  type="button"
                  onClick={() => onFilterOpenChange(false)}
                  className="flex size-7 items-center justify-center rounded-lg text-gray-400 hover:bg-gray-100 hover:text-gray-600"
                >
                  <X className="size-3.5" />
                </button>
              </div>

              <div className="mt-4 space-y-4">
                <div>
                  <p className="mb-2 text-xs font-medium text-gray-500">
                    {t('taskBoard.filterStatus')}
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {(['all', ...TASK_BOARD_STATUS_ORDER] as TaskBoardStatusFilter[]).map(status => (
                      <button
                        key={status}
                        type="button"
                        onClick={() => onStatusFilterChange(status)}
                        className={cn(
                          'rounded-lg px-2.5 py-1.5 text-xs font-medium transition-colors',
                          statusFilter === status
                            ? 'bg-[hsl(0,0%,8%)] text-white'
                            : 'bg-gray-100 text-gray-500 hover:bg-gray-200 hover:text-gray-700',
                        )}
                      >
                        {status === 'all'
                          ? t('taskBoard.filterAllStatuses')
                          : t(`status.${status}` as never)}
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <p className="mb-2 text-xs font-medium text-gray-500">
                    {t('taskBoard.filterAgent')}
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {(['all', ...agentOptions] as TaskBoardAgentFilter[]).map(agent => (
                      <button
                        key={agent}
                        type="button"
                        onClick={() => onAgentFilterChange(agent)}
                        className={cn(
                          'rounded-lg px-2.5 py-1.5 text-xs font-medium transition-colors',
                          agentFilter === agent
                            ? 'bg-[hsl(0,0%,8%)] text-white'
                            : 'bg-gray-100 text-gray-500 hover:bg-gray-200 hover:text-gray-700',
                        )}
                      >
                        {agent === 'all'
                          ? t('taskBoard.filterAllAgents')
                          : t(getAgentLabelKey(agent) as never)}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              <button
                type="button"
                onClick={onClearFilters}
                className="mt-4 w-full rounded-lg border border-gray-200 px-3 py-2 text-xs font-medium text-gray-600 transition-colors hover:bg-gray-50"
              >
                {t('taskBoard.clearFilters')}
              </button>
            </div>
          ) : null}
        </div>
      </div>

      <div className="divide-y divide-gray-100">
        {rows.length === 0 ? (
          <div className="px-6 py-10 text-center">
            <p className="text-sm font-medium text-[hsl(0,0%,8%)]">
              {t('taskBoard.noWorkflowRows')}
            </p>
          </div>
        ) : null}

        {rows.map(row => {
          const Icon = row.icon;
          const tasks = groupedTasks[row.status] ?? [];
          const count = tasks.length;
          const targetTask = tasks[0];
          return (
            <div
              key={row.status}
              className="flex min-w-0 items-center gap-4 px-6 py-3.5 transition-colors hover:bg-gray-50/50"
            >
              <div className={cn('flex size-8 shrink-0 items-center justify-center rounded-full', row.iconBg)}>
                <Icon className={cn('size-4', row.status === 'running' ? 'animate-spin' : '', row.color)} />
              </div>
              <span className="w-36 shrink-0 truncate text-sm font-medium text-[hsl(0,0%,8%)]">
                {t(`status.${row.status}` as never)}
              </span>
              <span className="w-8 shrink-0 text-center text-sm font-bold text-[hsl(0,0%,8%)]">
                {count}
              </span>
              <span className="min-w-0 flex-1 truncate text-sm text-gray-500">
                {t(row.descriptionKey as never)}
              </span>
              <div className="shrink-0">
                <AvatarStack count={Math.min(count, 7)} />
              </div>
              {targetTask ? (
                <Link
                  to={`/task/${targetTask.id}`}
                  className="ml-auto flex size-8 shrink-0 items-center justify-center rounded-full border border-gray-200 text-gray-400 transition-colors hover:border-gray-300 hover:text-gray-600"
                  aria-label={t('common.details')}
                >
                  <ArrowRight className="size-3.5" />
                </Link>
              ) : (
                <button
                  type="button"
                  disabled
                  className="ml-auto flex size-8 shrink-0 items-center justify-center rounded-full border border-gray-200 text-gray-300"
                >
                  <ArrowRight className="size-3.5" />
                </button>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
