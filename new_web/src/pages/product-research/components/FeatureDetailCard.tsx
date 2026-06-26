import { useTranslation } from 'react-i18next';
import type { ApiFeature } from '@/api/types';
import { Badge } from '@/components/ui/badge';
import { FEATURE_STATUS_META, FEATURE_ITEM_STATUS_META } from '../constants';
import { calculateFeatureCompletion, formatRelativeTime, getProjectLabel } from '../utils';

type FeatureDetailCardProps = {
  feature: ApiFeature;
};

export function FeatureDetailCard({ feature }: FeatureDetailCardProps) {
  const { t } = useTranslation();
  const statusMeta = FEATURE_STATUS_META[feature.status];
  const completion = calculateFeatureCompletion(feature.items);

  return (
    <article className="rounded-2xl border border-gray-200/60 bg-white">
      <header className="border-b border-gray-100 p-6">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div className="flex min-w-0 flex-col gap-2">
            <h2 className="text-xl font-bold tracking-tight text-[hsl(0,0%,8%)]">{feature.title}</h2>
            <p className="text-sm text-gray-500">{feature.description}</p>
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-gray-500">
              <span>{getProjectLabel(feature.project, t)}</span>
              <span>{t('common.updatedRelative', { time: formatRelativeTime(feature.updated_at) })}</span>
            </div>
          </div>
          <Badge variant="outline" className={statusMeta.className}>
            {t(`productResearch.featureStatus.${feature.status}` as never)}
          </Badge>
        </div>
      </header>

      <div className="p-6">
        <div className="mb-6">
          <div className="flex items-center justify-between text-sm">
            <span className="font-medium text-[hsl(0,0%,8%)]">{t('productResearch.progress')}</span>
            <span className="font-semibold text-[hsl(0,0%,8%)]">{completion}%</span>
          </div>
          <div className="mt-2 h-2 overflow-hidden rounded-full bg-gray-100">
            <div
              className="h-full rounded-full bg-[hsl(80,85%,55%)] transition-all"
              style={{ width: `${completion}%` }}
            />
          </div>
        </div>

        {feature.items && feature.items.length > 0 ? (
          <div>
            <h3 className="text-sm font-semibold text-[hsl(0,0%,8%)] mb-3">
              {t('productResearch.featureItems')} ({feature.items.length})
            </h3>
            <div className="space-y-2">
              {feature.items.map((item, idx) => {
                const itemStatusMeta = FEATURE_ITEM_STATUS_META[item.status];
                return (
                  <div
                    key={item.id}
                    className={`flex items-center justify-between rounded-xl border border-gray-100 px-4 py-3 ${idx % 2 === 1 ? 'bg-gray-50/50' : ''}`}
                  >
                    <div className="flex items-center gap-3 min-w-0 flex-1">
                      <Badge variant="outline" className={itemStatusMeta?.className ?? ''}>
                        {t(`productResearch.featureItemStatus.${item.status}` as never)}
                      </Badge>
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-[hsl(0,0%,8%)]">{item.title}</p>
                        <p className="truncate text-xs text-gray-400">{item.description}</p>
                      </div>
                    </div>
                    <span className="ml-3 text-xs text-gray-400 shrink-0">{formatRelativeTime(item.updated_at)}</span>
                  </div>
                );
              })}
            </div>
          </div>
        ) : (
          <div className="rounded-xl border border-gray-200/60 bg-gray-50 p-8 text-center">
            <p className="text-sm text-gray-400">{t('productResearch.noFeatureItems')}</p>
          </div>
        )}
      </div>
    </article>
  );
}
