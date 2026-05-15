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
import {
  FEATURE_STATUS_META,
  TABLE_BODY_CLASS,
  TABLE_CARD_CLASS,
  TABLE_HEAD_CLASS,
  TABLE_HEADER_ROW_CLASS,
  TABLE_ROW_CLASS,
} from '../constants';
import {
  calculateFeatureCompletion,
  formatRelativeTime,
  getProjectLabel,
} from '../utils';
import { TablePaginationFooter } from './TablePaginationFooter';

type FeatureTableProps = {
  features: ApiFeature[];
  page: number;
  pageCount: number;
  totalCount: number;
  onSelect: (featureId: string) => void;
  onPageChange: (page: number) => void;
};

export function FeatureTable({
  features,
  page,
  pageCount,
  totalCount,
  onSelect,
  onPageChange,
}: FeatureTableProps) {
  return (
    <div className={TABLE_CARD_CLASS}>
      <Table className="table-fixed">
        <TableHeader>
          <TableRow className={TABLE_HEADER_ROW_CLASS}>
            <TableHead className={`w-[38%] ${TABLE_HEAD_CLASS}`}>Title</TableHead>
            <TableHead className={`w-[18%] ${TABLE_HEAD_CLASS}`}>Project</TableHead>
            <TableHead className={`w-[18%] ${TABLE_HEAD_CLASS}`}>Status</TableHead>
            <TableHead className={`w-[18%] ${TABLE_HEAD_CLASS}`}>Progress</TableHead>
            <TableHead className={`w-[8%] text-right ${TABLE_HEAD_CLASS}`}>
              Updated
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody className={TABLE_BODY_CLASS}>
          {features.map(feature => {
            const featureMeta = FEATURE_STATUS_META[feature.status];
            const completion = calculateFeatureCompletion(feature.items);
            const itemCount = feature.items?.length ?? 0;

            return (
              <TableRow
                key={feature.id}
                tabIndex={0}
                className={TABLE_ROW_CLASS}
                onClick={() => onSelect(feature.id)}
                onKeyDown={event => {
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    onSelect(feature.id);
                  }
                }}
              >
                <TableCell>
                  <div className="flex min-w-0 flex-col gap-1">
                    <Link
                      to={`/product-research/features/${feature.id}`}
                      className="truncate font-medium text-black hover:underline"
                      onClick={event => event.stopPropagation()}
                    >
                      {feature.title}
                    </Link>
                    <span className="text-xs text-black/45">
                      {itemCount} feature items
                    </span>
                  </div>
                </TableCell>
                <TableCell className="truncate text-sm text-black/55">
                  {getProjectLabel(feature.project)}
                </TableCell>
                <TableCell>
                  <Badge variant={featureMeta.variant} className={featureMeta.className}>
                    {featureMeta.label}
                  </Badge>
                </TableCell>
                <TableCell>
                  <div className="flex items-center gap-3">
                    <div className="h-2 flex-1 rounded-full bg-black/[0.08]">
                      <div
                        className="h-2 rounded-full bg-black transition-[width]"
                        style={{ width: `${completion}%` }}
                      />
                    </div>
                    <span className="w-11 text-right text-xs text-black/45">
                      {completion}%
                    </span>
                  </div>
                </TableCell>
                <TableCell className="text-right text-sm text-black/45">
                  {formatRelativeTime(feature.updated_at)}
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
        <TablePaginationFooter
          columnCount={5}
          page={page}
          pageCount={pageCount}
          total={totalCount}
          onPageChange={onPageChange}
        />
      </Table>
    </div>
  );
}
