import { useTranslation } from 'react-i18next';
import { Clock, Loader2, Users, AlertTriangle, CheckCircle2, type LucideIcon } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { TaskBoardStatus } from '../utils';
import type { WorkspaceTaskView } from '@/lib/workspace-task-view';
import { Sparkline } from './Sparkline';

type StatusCardData = {
  status: TaskBoardStatus;
  count: number;
  subtitlePrefix: string;
  subtitleKey: string;
  icon: LucideIcon;
  color: 'lime' | 'white' | 'orange' | 'red' | 'green';
  sparklineData: number[];
  sparklineColor: string;
};

type StatusCardsProps = {
  groupedTasks: Record<TaskBoardStatus, WorkspaceTaskView[]>;
  isLoading: boolean;
};

const STATUS_CONFIG: Omit<StatusCardData, 'count' | 'sparklineData'>[] = [
  {
    status: 'queued',
    subtitleKey: 'taskBoard.sinceYesterday',
    subtitlePrefix: '+3',
    icon: Clock,
    color: 'lime',
    sparklineColor: '#a3a3a3',
  },
  {
    status: 'running',
    subtitleKey: 'taskBoard.active',
    subtitlePrefix: '+4',
    icon: Loader2,
    color: 'white',
    sparklineColor: '#84cc16',
  },
  {
    status: 'waiting_for_review',
    subtitleKey: 'taskBoard.overdue',
    subtitlePrefix: '2',
    icon: Users,
    color: 'orange',
    sparklineColor: '#f97316',
  },
  {
    status: 'failed',
    subtitleKey: 'taskBoard.needAttention',
    subtitlePrefix: '2',
    icon: AlertTriangle,
    color: 'red',
    sparklineColor: '#ef4444',
  },
  {
    status: 'merged',
    subtitleKey: 'taskBoard.thisWeekCount',
    subtitlePrefix: '+18',
    icon: CheckCircle2,
    color: 'green',
    sparklineColor: '#84cc16',
  },
];

function generateSparklineData(count: number): number[] {
  const points: number[] = [];
  let value = 5 + Math.random() * 10;
  for (let i = 0; i < 12; i++) {
    value += (Math.random() - 0.45) * 4;
    value = Math.max(1, Math.min(20, value));
    points.push(value);
  }
  if (count > 0) {
    points[points.length - 1] = Math.max(points[points.length - 1], count * 0.5);
  }
  return points;
}

function getCardClasses(color: StatusCardData['color']): string {
  switch (color) {
    case 'lime':
      return 'bg-[hsl(80,85%,92%)] border-[hsl(80,60%,80%)]';
    case 'white':
      return 'bg-white border-gray-200/60';
    case 'orange':
      return 'bg-white border-gray-200/60';
    case 'red':
      return 'bg-white border-gray-200/60';
    case 'green':
      return 'bg-white border-gray-200/60';
  }
}

function getIconBgClasses(color: StatusCardData['color']): string {
  switch (color) {
    case 'lime':
      return 'bg-[hsl(80,85%,55%)] text-[hsl(0,0%,10%)]';
    case 'white':
      return 'bg-gray-100 text-gray-600';
    case 'orange':
      return 'bg-orange-100 text-orange-600';
    case 'red':
      return 'bg-red-100 text-red-600';
    case 'green':
      return 'bg-green-100 text-green-600';
  }
}

export function StatusCards({ groupedTasks, isLoading }: StatusCardsProps) {
  const { t } = useTranslation();

  const cards: StatusCardData[] = STATUS_CONFIG.map(config => ({
    ...config,
    count: groupedTasks[config.status]?.length ?? 0,
    sparklineData: generateSparklineData(groupedTasks[config.status]?.length ?? 0),
  }));

  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
      {cards.map(card => {
        const Icon = card.icon;
        return (
          <div
            key={card.status}
            className={cn(
              'min-w-0 rounded-2xl border p-5 transition-shadow hover:shadow-md',
              getCardClasses(card.color),
            )}
          >
            <div className="flex min-w-0 items-center gap-2 text-sm font-medium text-gray-600">
              <div className={cn('flex size-7 shrink-0 items-center justify-center rounded-lg', getIconBgClasses(card.color))}>
                <Icon className={cn('size-3.5', card.status === 'running' ? 'animate-spin' : '')} />
              </div>
              <span className="min-w-0 truncate">{t(`status.${card.status}` as never)}</span>
            </div>
            <div className="mt-3 flex items-end justify-between">
              <div className="min-w-0">
                <p className="text-3xl font-bold tracking-tight text-[hsl(0,0%,8%)]">
                  {isLoading ? '...' : card.count}
                </p>
                <p className="mt-1 truncate text-xs text-gray-500">
                  {card.subtitlePrefix} {t(card.subtitleKey as never)}
                </p>
              </div>
              <div className="shrink-0">
                <Sparkline data={card.sparklineData} color={card.sparklineColor} width={80} height={32} />
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
