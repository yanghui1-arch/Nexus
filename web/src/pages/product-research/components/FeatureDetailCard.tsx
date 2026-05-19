import { useTranslation } from 'react-i18next';
import type { ApiFeature } from '@/api/types';
import { Badge } from '@/components/ui/badge';
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { FEATURE_ITEM_STATUS_META, FEATURE_STATUS_META } from '../constants';
import { formatDateTime, shortId } from '../utils';

type FeatureDetailCardProps = {
  feature: ApiFeature;
};

export function FeatureDetailCard({ feature }: FeatureDetailCardProps) {
  const { t } = useTranslation();
  const featureMeta = FEATURE_STATUS_META[feature.status];
  const items = feature.items ?? [];

  return (
    <Card className="gap-0">
      <CardHeader className="border-b">
        <CardTitle>{feature.title}</CardTitle>
        <CardDescription className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <span>{feature.project ?? t('common.noProject')}</span>
          <span>{t('common.updatedAt', { time: formatDateTime(feature.updated_at) })}</span>
        </CardDescription>
        <CardAction className="flex items-center gap-2">
          <Badge variant={featureMeta.variant} className={featureMeta.className}>
            {t(`productResearch.featureStatus.${feature.status}`)}
          </Badge>
          {feature.proposal_id ? (
            <Badge variant="outline">{t('productResearch.proposalShort', { id: shortId(feature.proposal_id) })}</Badge>
          ) : null}
        </CardAction>
      </CardHeader>

      <CardContent className="flex flex-col gap-6 pt-6">
        <div className="flex flex-col gap-2">
          <p className="text-sm font-medium">{t('common.description')}</p>
          <p className="whitespace-pre-wrap text-sm leading-6 text-muted-foreground">
            {feature.description}
          </p>
        </div>

        <div className="flex flex-col gap-3">
          <p className="text-sm font-medium">{t('productResearch.featureItems')}</p>
          {items.length === 0 ? (
            <p className="text-sm text-muted-foreground">{t('productResearch.noFeatureItems')}</p>
          ) : (
            items.map(item => {
              const itemMeta = FEATURE_ITEM_STATUS_META[item.status];

              return (
                <div key={item.id} className="flex flex-col gap-2 rounded-lg border bg-background/70 p-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="flex min-w-0 flex-col gap-1">
                      <p className="text-sm font-medium">{item.order_index}. {item.title}</p>
                      <p className="text-sm leading-6 text-muted-foreground">{item.description}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge variant={itemMeta.variant} className={itemMeta.className}>
                        {t(`productResearch.featureItemStatus.${item.status}`)}
                      </Badge>
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
                    {item.task_id ? <span>{t('productResearch.taskShort', { id: shortId(item.task_id) })}</span> : null}
                    <span>{t('common.updatedAt', { time: formatDateTime(item.updated_at) })}</span>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </CardContent>
    </Card>
  );
}
