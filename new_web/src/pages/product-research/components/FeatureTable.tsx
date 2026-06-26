import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import type { ApiFeature } from '@/api/types';
import { Badge } from '@/components/ui/badge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { FEATURE_STATUS_META } from '../constants';
import { calculateFeatureCompletion, formatRelativeTime, getProjectLabel } from '../utils';
import { TablePaginationFooter } from './TablePaginationFooter';

type FeatureTableProps = {
  features: ApiFeature[];
  page: number;
  pageCount: number;
  totalCount: number;
  onSelect: (featureId: string) => void;
  onPageChange: (page: number) => void;
};

export function FeatureTable({ features, page, pageCount, totalCount, onSelect, onPageChange }: FeatureTableProps) {
  const { t } = useTranslation();
  return (
    <div className="rounded-2xl border border-gray-200/60 bg-white overflow-hidden">
      <Table>
        <TableHeader>
          <TableRow className="bg-gray-50/80 border-gray-100">
            <TableHead className="h-11 text-[11px] font-semibold uppercase tracking-wider text-gray-400 w-[40%]">{t('common.title')}</TableHead>
            <TableHead className="h-11 text-[11px] font-semibold uppercase tracking-wider text-gray-400 w-[15%]">{t('common.project')}</TableHead>
            <TableHead className="h-11 text-[11px] font-semibold uppercase tracking-wider text-gray-400 w-[15%]">{t('common.status')}</TableHead>
            <TableHead className="h-11 text-[11px] font-semibold uppercase tracking-wider text-gray-400 w-[18%]">{t('productResearch.progress')}</TableHead>
            <TableHead className="h-11 text-[11px] font-semibold uppercase tracking-wider text-gray-400 text-right w-[12%]">{t('common.updated')}</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {features.map((feature, idx) => {
            const statusMeta = FEATURE_STATUS_META[feature.status];
            const completion = calculateFeatureCompletion(feature.items);
            return (
              <TableRow
                key={feature.id}
                tabIndex={0}
                className={`cursor-pointer hover:bg-gray-50/50 ${idx % 2 === 1 ? 'bg-gray-50/30' : ''}`}
                onClick={() => onSelect(feature.id)}
                onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onSelect(feature.id); } }}
              >
                <TableCell>
                  <div className="flex min-w-0 flex-col gap-0.5">
                    <Link to={`/product-research/features/${feature.id}`} className="truncate text-sm font-semibold text-[hsl(0,0%,8%)] hover:underline" onClick={event => event.stopPropagation()}>
                      {feature.title}
                    </Link>
                    <span className="text-xs text-gray-400 line-clamp-1">{feature.description}</span>
                  </div>
                </TableCell>
                <TableCell className="truncate text-sm text-gray-500">{getProjectLabel(feature.project, t)}</TableCell>
                <TableCell>
                  <Badge variant="outline" className={statusMeta.className}>
                    {t(`productResearch.featureStatus.${feature.status}` as never)}
                  </Badge>
                </TableCell>
                <TableCell>
                  <div className="flex items-center gap-2">
                    <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-gray-100">
                      <div
                        className="h-full rounded-full bg-[hsl(80,85%,55%)] transition-all"
                        style={{ width: `${completion}%` }}
                      />
                    </div>
                    <span className="text-xs font-medium text-gray-500 w-8 text-right">{completion}%</span>
                  </div>
                </TableCell>
                <TableCell className="text-right text-sm text-gray-400">{formatRelativeTime(feature.updated_at)}</TableCell>
              </TableRow>
            );
          })}
          <TablePaginationFooter columnCount={5} page={page} pageCount={pageCount} total={totalCount} onPageChange={onPageChange} />
        </TableBody>
      </Table>
    </div>
  );
}
