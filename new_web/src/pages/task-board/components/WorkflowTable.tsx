import { useTranslation } from 'react-i18next';
import { Clock, Loader2, Users, AlertTriangle, CheckCircle2, ArrowRight, type LucideIcon } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { TaskBoardStatus } from '../utils';
import type { WorkspaceTaskView } from '@/lib/workspace-task-view';

type WorkflowTableProps = {
  groupedTasks: Record<TaskBoardStatus, WorkspaceTaskView[]>;
  activeTab: string;
  onTabChange: (tab: string) => void;
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

const TABS = ['allTasks', 'myTasks', 'backend', 'frontend', 'devops'] as const;

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

export function WorkflowTable({ groupedTasks, activeTab, onTabChange }: WorkflowTableProps) {
  const { t } = useTranslation();

  return (
    <div className="rounded-2xl border border-gray-200/60 bg-white">
      <div className="flex items-center justify-between border-b border-gray-100 px-6 py-4">
        <div className="flex items-center gap-3">
          <h2 className="text-base font-bold text-[hsl(0,0%,8%)]">{t('taskBoard.workflows')}</h2>
          <span className="flex items-center gap-1.5 text-xs text-gray-400">
            <span className="size-1.5 rounded-full bg-green-400 animate-pulse" />
            {t('taskBoard.live')}
          </span>
        </div>
        <div className="flex items-center gap-1 rounded-lg bg-gray-100 p-0.5">
          {TABS.map(tab => (
            <button
              key={tab}
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
        <button className="inline-flex items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-xs font-medium text-gray-600 transition-colors hover:bg-gray-50">
          <svg className="size-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3" />
          </svg>
          {t('common.filters')}
        </button>
      </div>

      <div className="divide-y divide-gray-100">
        {WORKFLOW_ROWS.map(row => {
          const Icon = row.icon;
          const count = groupedTasks[row.status]?.length ?? 0;
          return (
            <div
              key={row.status}
              className="flex items-center gap-4 px-6 py-3.5 transition-colors hover:bg-gray-50/50"
            >
              <div className={cn('flex size-8 items-center justify-center rounded-full', row.iconBg)}>
                <Icon className={cn('size-4', row.status === 'running' ? 'animate-spin' : '', row.color)} />
              </div>
              <span className="w-36 text-sm font-medium text-[hsl(0,0%,8%)]">
                {t(`taskBoard.${row.status}` as never)}
              </span>
              <span className="w-8 text-center text-sm font-bold text-[hsl(0,0%,8%)]">
                {count}
              </span>
              <span className="flex-1 text-sm text-gray-500">
                {t(row.descriptionKey as never)}
              </span>
              <AvatarStack count={Math.min(count, 7)} />
              <button className="ml-auto flex size-8 items-center justify-center rounded-full border border-gray-200 text-gray-400 transition-colors hover:border-gray-300 hover:text-gray-600">
                <ArrowRight className="size-3.5" />
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
