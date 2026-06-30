import { useTranslation } from 'react-i18next';
import { GitPullRequest, AlertTriangle, Cpu, type LucideIcon } from 'lucide-react';
import { cn } from '@/lib/utils';
import { timeAgo, type WorkspaceTaskView } from '@/lib/workspace-task-view';

type ActivityFeedProps = {
  tasks: WorkspaceTaskView[];
  className?: string;
  isLoading?: boolean;
};

type ActivityType = 'pr' | 'failed' | 'agent';

type ActivityItem = {
  id: string;
  type: ActivityType;
  title: string;
  description: string;
  statusKey: string;
  statusColor: string;
  dotColor: string;
  time: string | null;
  iconBg: string;
};

const ICON_MAP: Record<ActivityType, LucideIcon> = {
  pr: GitPullRequest,
  failed: AlertTriangle,
  agent: Cpu,
};

function prLabelFromUrl(url: string | null): string | null {
  if (!url) return null;
  const match = url.match(/\/pull\/(\d+)/);
  return match ? `PR #${match[1]}` : null;
}

export function ActivityFeed({ tasks, className, isLoading }: ActivityFeedProps) {
  const { t } = useTranslation();

  const activities: ActivityItem[] = tasks
    .map((task): ActivityItem | null => {
      const description = task.question;
      switch (task.status) {
        case 'merged':
          return {
            id: task.id,
            type: 'pr',
            title: prLabelFromUrl(task.externalPullRequestUrl) ?? t('taskBoard.pullRequest'),
            description: task.result || description,
            statusKey: 'status.merged',
            statusColor: 'text-green-600',
            dotColor: 'bg-green-500',
            time: task.finishedAt ?? task.updatedAt,
            iconBg: 'bg-purple-100 text-purple-600',
          };
        case 'waiting_for_review':
          return {
            id: task.id,
            type: 'pr',
            title: prLabelFromUrl(task.externalPullRequestUrl) ?? t('taskBoard.pullRequest'),
            description: task.result || description,
            statusKey: 'status.waiting_for_review',
            statusColor: 'text-orange-600',
            dotColor: 'bg-orange-500',
            time: task.updatedAt,
            iconBg: 'bg-purple-100 text-purple-600',
          };
        case 'failed':
          return {
            id: task.id,
            type: 'failed',
            title: t('taskBoard.taskFailed'),
            description: task.error || description,
            statusKey: 'status.failed',
            statusColor: 'text-red-600',
            dotColor: 'bg-red-500',
            time: task.finishedAt ?? task.updatedAt,
            iconBg: 'bg-red-100 text-red-600',
          };
        case 'running':
          return {
            id: task.id,
            type: 'agent',
            title: t('taskBoard.agentRunning'),
            description,
            statusKey: 'status.running',
            statusColor: 'text-purple-600',
            dotColor: 'bg-purple-500',
            time: task.startedAt ?? task.createdAt,
            iconBg: 'bg-green-100 text-green-600',
          };
        case 'queued':
          return {
            id: task.id,
            type: 'agent',
            title: t('taskBoard.taskQueued'),
            description,
            statusKey: 'status.queued',
            statusColor: 'text-gray-600',
            dotColor: 'bg-gray-400',
            time: task.createdAt,
            iconBg: 'bg-green-100 text-green-600',
          };
        default:
          return null;
      }
    })
    .filter((item): item is ActivityItem => item !== null)
    .sort((a, b) => {
      const at = a.time ? new Date(a.time).getTime() : 0;
      const bt = b.time ? new Date(b.time).getTime() : 0;
      return bt - at;
    })
    .slice(0, 20);

  return (
    <div className={cn('flex min-h-0 min-w-0 max-w-full flex-col overflow-hidden rounded-2xl border border-gray-200/60 bg-white', className)}>
      <div className="flex shrink-0 items-center justify-between border-b border-gray-100 px-5 py-4">
        <h3 className="text-sm font-bold text-[hsl(0,0%,8%)]">{t('taskBoard.activityFeed')}</h3>
        <button className="text-xs font-medium text-gray-400 hover:text-gray-600">
          {t('common.viewAll')}
        </button>
      </div>

      <div className="min-h-0 min-w-0 flex-1 divide-y divide-gray-50 overflow-y-auto overflow-x-hidden">
        {activities.length === 0 ? (
          <div className="px-5 py-10 text-center text-xs text-gray-400">
            {isLoading ? '...' : t('taskBoard.noActivity')}
          </div>
        ) : (
          activities.map(item => {
            const Icon = ICON_MAP[item.type];
            return (
              <div key={item.id} className="flex min-w-0 max-w-full gap-3 overflow-hidden px-5 py-3.5 transition-colors hover:bg-gray-50/50">
                <div className={cn('flex size-9 shrink-0 items-center justify-center rounded-full', item.iconBg)}>
                  <Icon className="size-4" />
                </div>
                <div className="w-0 min-w-0 flex-1 overflow-hidden">
                  <p className={cn('text-xs font-semibold', item.type === 'failed' ? 'text-red-600' : item.type === 'pr' ? 'text-purple-600' : 'text-[hsl(0,0%,8%)]')}>
                    {item.title}
                  </p>
                  <p className="mt-0.5 truncate text-xs text-gray-500">{item.description}</p>
                  <div className="mt-1 flex items-center gap-2 text-[10px]">
                    <span className={cn('flex items-center gap-1', item.statusColor)}>
                      <span className={cn('size-1.5 rounded-full', item.dotColor)} />
                      {t(item.statusKey as never)}
                    </span>
                    <span className="text-gray-400">{timeAgo(item.time)}</span>
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
