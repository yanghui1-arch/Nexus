import { useTranslation } from 'react-i18next';
import { Code2, MoreHorizontal } from 'lucide-react';
import { cn } from '@/lib/utils';

type TopRepositoriesChartProps = {
  className?: string;
};

const REPOS = [
  { name: 'yanghui-arch/Nexus', value: 128, max: 128 },
  { name: 'Nexus/backend-service', value: 84, max: 128 },
  { name: 'Nexus/web-dashboard', value: 56, max: 128 },
  { name: 'Nexus/agent-runner', value: 32, max: 128 },
];

export function TopRepositoriesChart({ className }: TopRepositoriesChartProps) {
  const { t } = useTranslation();

  return (
    <div className={cn('rounded-2xl border border-gray-200/60 bg-white p-6', className)}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Code2 className="size-4 text-gray-400" />
          <div>
            <h3 className="text-sm font-bold text-[hsl(0,0%,8%)]">{t('taskBoard.topRepositories')}</h3>
            <p className="text-xs text-gray-400">{t('taskBoard.byActivity')}</p>
          </div>
        </div>
        <button className="text-gray-400 hover:text-gray-600">
          <MoreHorizontal className="size-4" />
        </button>
      </div>

      <div className="mt-5 space-y-3.5">
        {REPOS.map((repo, index) => (
          <div key={repo.name} className="flex items-center gap-3">
            <span className="w-40 truncate text-xs text-gray-600">{repo.name}</span>
            <div className="flex-1">
              <div className="h-2.5 overflow-hidden rounded-full bg-gray-100">
                <div
                  className={cn(
                    'h-full rounded-full transition-all',
                    index === 0 ? 'bg-[hsl(80,85%,55%)]' : 'bg-gray-300',
                  )}
                  style={{ width: `${(repo.value / repo.max) * 100}%` }}
                />
              </div>
            </div>
            <span className="w-8 text-right text-xs font-semibold text-gray-700">{repo.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
