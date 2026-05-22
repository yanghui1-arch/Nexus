import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import type { ApiProductProposal } from '@/api/types';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  PROPOSAL_STATUS_META,
  TABLE_BODY_CLASS,
  TABLE_CARD_CLASS,
  TABLE_HEAD_CLASS,
  TABLE_HEADER_ROW_CLASS,
  TABLE_ROW_CLASS,
} from '../constants';
import { formatRelativeTime, getProjectLabel } from '../utils';
import { TablePaginationFooter } from './TablePaginationFooter';

type ProposalTableProps = {
  page: number;
  pageCount: number;
  proposals: ApiProductProposal[];
  totalCount: number;
  onSelect: (proposalId: string) => void;
  onPageChange: (page: number) => void;
};

export function ProposalTable({ page, pageCount, proposals, totalCount, onSelect, onPageChange }: ProposalTableProps) {
  const { t } = useTranslation();
  return (
    <div className={TABLE_CARD_CLASS}>
      <Table className="table-fixed">
        <TableHeader>
          <TableRow className={TABLE_HEADER_ROW_CLASS}>
            <TableHead className={`w-[52%] ${TABLE_HEAD_CLASS}`}>{t('common.title')}</TableHead>
            <TableHead className={`w-[16%] ${TABLE_HEAD_CLASS}`}>{t('common.project')}</TableHead>
            <TableHead className={`w-[20%] ${TABLE_HEAD_CLASS}`}>{t('common.status')}</TableHead>
            <TableHead className={`w-[12%] text-right ${TABLE_HEAD_CLASS}`}>{t('productResearch.submitted')}</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody className={TABLE_BODY_CLASS}>
          {proposals.map(proposal => {
            const statusMeta = PROPOSAL_STATUS_META[proposal.status];
            return (
              <TableRow
                key={proposal.id}
                tabIndex={0}
                className={cn(
                  TABLE_ROW_CLASS,
                  proposal.status === 'proposed' &&
                    'bg-amber-50/70 hover:bg-amber-100/70 focus-visible:bg-amber-100/70',
                )}
                onClick={() => onSelect(proposal.id)}
                onKeyDown={event => {
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    onSelect(proposal.id);
                  }
                }}
              >
                <TableCell>
                  <div className="flex min-w-0 flex-col gap-1">
                    <Link to={`/product-research/proposals/${proposal.id}`} className="truncate font-medium text-black hover:underline" onClick={event => event.stopPropagation()}>{proposal.title}</Link>
                    <span className="text-xs text-black/45">{proposal.repo ?? t('common.noRepository')}</span>
                  </div>
                </TableCell>
                <TableCell className="truncate text-sm text-black/55">{getProjectLabel(proposal.project, t)}</TableCell>
                <TableCell><Badge variant={statusMeta.variant} className={statusMeta.className}>{t(`productResearch.proposalStatus.${proposal.status}`)}</Badge></TableCell>
                <TableCell className="text-right text-sm text-black/45">{formatRelativeTime(proposal.created_at)}</TableCell>
              </TableRow>
            );
          })}
        </TableBody>
        <TablePaginationFooter columnCount={4} page={page} pageCount={pageCount} total={totalCount} onPageChange={onPageChange} />
      </Table>
    </div>
  );
}
