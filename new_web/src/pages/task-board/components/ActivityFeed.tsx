import { useTranslation } from 'react-i18next';
import { GitPullRequest, AlertTriangle, Rocket, Cpu } from 'lucide-react';
import { cn } from '@/lib/utils';

type ActivityFeedProps = {
  className?: string;
};

type ActivityItem = {
  id: string;
  type: 'pr' | 'failed' | 'deployment' | 'agent';
  title: string;
  description: string;
  status: string;
  statusColor: string;
  time: string;
  iconBg: string;
};

const ACTIVITIES: ActivityItem[] = [
  {
    id: '1',
    type: 'pr',
    title: 'PR #482',
    description: 'Add Recovery Assessment API endpoint and tests',
    status: 'Merged',
    statusColor: 'text-green-600',
    time: '2m ago',
    iconBg: 'bg-purple-100 text-purple-600',
  },
  {
    id: '2',
    type: 'failed',
    title: 'Task Failed',
    description: 'Retry from Checkpoint API integration tests',
    status: 'Failed',
    statusColor: 'text-red-600',
    time: '14m ago',
    iconBg: 'bg-red-100 text-red-600',
  },
  {
    id: '3',
    type: 'pr',
    title: 'PR #481',
    description: 'New Task API: create, list, cancel endpoints',
    status: 'Under review',
    statusColor: 'text-orange-600',
    time: '28m ago',
    iconBg: 'bg-purple-100 text-purple-600',
  },
  {
    id: '4',
    type: 'deployment',
    title: 'Deployment',
    description: 'v1.48.0 deployed to staging environment',
    status: 'Success',
    statusColor: 'text-green-600',
    time: '1h ago',
    iconBg: 'bg-blue-100 text-blue-600',
  },
  {
    id: '5',
    type: 'agent',
    title: 'Agent Scaled',
    description: 'Build agent pool scaled up (+3 machines)',
    status: 'Auto',
    statusColor: 'text-purple-600',
    time: '2h ago',
    iconBg: 'bg-green-100 text-green-600',
  },
];

const ICON_MAP = {
  pr: GitPullRequest,
  failed: AlertTriangle,
  deployment: Rocket,
  agent: Cpu,
};

export function ActivityFeed({ className }: ActivityFeedProps) {
  const { t } = useTranslation();

  return (
    <div className={cn('rounded-2xl border border-gray-200/60 bg-white', className)}>
      <div className="flex items-center justify-between border-b border-gray-100 px-5 py-4">
        <h3 className="text-sm font-bold text-[hsl(0,0%,8%)]">{t('taskBoard.activityFeed')}</h3>
        <button className="text-xs font-medium text-gray-400 hover:text-gray-600">
          {t('common.viewAll')}
        </button>
      </div>

      <div className="divide-y divide-gray-50">
        {ACTIVITIES.map(item => {
          const Icon = ICON_MAP[item.type];
          return (
            <div key={item.id} className="flex gap-3 px-5 py-3.5 transition-colors hover:bg-gray-50/50">
              <div className={cn('flex size-9 shrink-0 items-center justify-center rounded-full', item.iconBg)}>
                <Icon className="size-4" />
              </div>
              <div className="min-w-0 flex-1">
                <p className={cn('text-xs font-semibold', item.type === 'failed' ? 'text-red-600' : item.type === 'pr' ? 'text-purple-600' : 'text-[hsl(0,0%,8%)]')}>
                  {item.title}
                </p>
                <p className="mt-0.5 truncate text-xs text-gray-500">{item.description}</p>
                <div className="mt-1 flex items-center gap-2 text-[10px]">
                  <span className={cn('flex items-center gap-1', item.statusColor)}>
                    <span className={cn(
                      'size-1.5 rounded-full',
                      item.status === 'Merged' || item.status === 'Success' ? 'bg-green-500' :
                      item.status === 'Failed' ? 'bg-red-500' :
                      item.status === 'Under review' ? 'bg-orange-500' : 'bg-purple-500',
                    )} />
                    {item.status}
                  </span>
                  <span className="text-gray-400">{item.time}</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
