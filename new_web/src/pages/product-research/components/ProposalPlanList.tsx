import { useTranslation } from 'react-i18next';
import type { ApiFeature } from '@/api/types';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { FEATURE_ITEM_STATUS_META, FEATURE_STATUS_META } from '../constants';
import { calculateFeatureCompletion, formatRelativeTime } from '../utils';

type ProposalPlanListProps = {
  features: ApiFeature[];
  retryingFeatureItemId: string | null;
  onRetryFeatureItem: (featureItemId: string) => Promise<void>;
};

export function ProposalPlanList({
  features,
  retryingFeatureItemId,
  onRetryFeatureItem,
}: ProposalPlanListProps) {
  const { t } = useTranslation();

  if (features.length === 0) {
    return (
      <div className="rounded-xl border border-gray-200/60 bg-gray-50 p-8 text-center">
        <p className="text-sm text-gray-400">{t('productResearch.planListEmpty')}</p>
      </div>
    );
  }

  return (
    <div className="mt-4 space-y-4">
      {features.map(feature => {
        const completion = calculateFeatureCompletion(feature.items);
        return (
          <div key={feature.id} className="rounded-xl border border-gray-200/60 bg-white p-5">
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0 flex-1">
                <h4 className="text-sm font-semibold text-[hsl(0,0%,8%)]">{feature.title}</h4>
                <p className="mt-1 text-xs text-gray-500 line-clamp-2">{feature.description}</p>
              </div>
              <Badge variant="outline" className={FEATURE_STATUS_META[feature.status]?.className ?? ''}>
                {t(`productResearch.featureStatus.${feature.status}` as never)}
              </Badge>
            </div>

            {feature.items && feature.items.length > 0 ? (
              <div className="mt-4 space-y-2">
                <div className="flex items-center justify-between text-xs text-gray-400">
                  <span>{t('productResearch.featureItemsCount', { count: feature.items.length })}</span>
                  <span>{completion}% complete</span>
                </div>
                <div className="h-1.5 overflow-hidden rounded-full bg-gray-100">
                  <div
                    className="h-full rounded-full bg-[hsl(80,85%,55%)] transition-all"
                    style={{ width: `${completion}%` }}
                  />
                </div>
                <div className="mt-2 space-y-1.5">
                  {feature.items.map(item => {
                    const itemStatusMeta = FEATURE_ITEM_STATUS_META[item.status];
                    const isRetrying = retryingFeatureItemId === item.id;
                    return (
                      <div key={item.id} className="flex items-center justify-between rounded-lg bg-gray-50 px-3 py-2">
                        <div className="flex items-center gap-2 min-w-0 flex-1">
                          <Badge variant="outline" className={itemStatusMeta?.className ?? ''}>
                            {t(`productResearch.featureItemStatus.${item.status}` as never)}
                          </Badge>
                          <span className="truncate text-xs font-medium text-[hsl(0,0%,8%)]">{item.title}</span>
                        </div>
                        <div className="flex items-center gap-2 ml-2">
                          <span className="text-[10px] text-gray-400">{formatRelativeTime(item.updated_at)}</span>
                          {item.status === 'failed' ? (
                            <Button
                              type="button"
                              size="sm"
                              variant="outline"
                              disabled={isRetrying}
                              onClick={() => void onRetryFeatureItem(item.id)}
                              className="h-6 px-2 text-[10px] rounded-md"
                            >
                              {isRetrying ? t('productResearch.workItemRetrying') : t('productResearch.workItemRetry')}
                            </Button>
                          ) : null}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            ) : (
              <p className="mt-3 text-xs text-gray-400">{t('productResearch.noFeatureItems')}</p>
            )}
          </div>
        );
      })}
    </div>
  );
}
