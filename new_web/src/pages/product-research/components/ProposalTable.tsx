import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import type { ApiProductProposal } from '@/api/types';
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
  PROPOSAL_PLANNING_STATUS_META,
  PROPOSAL_STATUS_META,
} from '../constants';
import {
  formatRelativeTime,
  getProjectLabel,
  getProposalPlanningDisplayStatus,
} from '../utils';
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
    <div className="rounded-2xl border border-gray-200/60 bg-white overflow-hidden">
      <Table>
        <TableHeader>
          <TableRow className="bg-gray-50/80 border-gray-100">
            <TableHead className="h-11 text-[11px] font-semibold uppercase tracking-wider text-gray-400 w-[50%]">{t('common.title')}</TableHead>
            <TableHead className="h-11 text-[11px] font-semibold uppercase tracking-wider text-gray-400 w-[18%]">{t('common.project')}</TableHead>
            <TableHead className="h-11 text-[11px] font-semibold uppercase tracking-wider text-gray-400 w-[20%]">{t('common.status')}</TableHead>
            <TableHead className="h-11 text-[11px] font-semibold uppercase tracking-wider text-gray-400 text-right w-[12%]">{t('productResearch.submitted')}</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {proposals.map((proposal, idx) => {
            const statusMeta = PROPOSAL_STATUS_META[proposal.status];
            const planningStatus =
              proposal.status === 'approved'
                ? getProposalPlanningDisplayStatus(proposal)
                : null;
            return (
              <TableRow
                key={proposal.id}
                tabIndex={0}
                className={`cursor-pointer hover:bg-gray-50/50 ${idx % 2 === 1 ? 'bg-gray-50/30' : ''}`}
                onClick={() => onSelect(proposal.id)}
                onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onSelect(proposal.id); } }}
              >
                <TableCell>
                  <div className="flex min-w-0 flex-col gap-0.5">
                    <Link to={`/product-research/proposals/${proposal.id}`} className="truncate text-sm font-semibold text-[hsl(0,0%,8%)] hover:underline" onClick={event => event.stopPropagation()}>
                      {proposal.title}
                    </Link>
                    <span className="text-xs text-gray-400">{proposal.repo ?? t('common.noRepository')}</span>
                  </div>
                </TableCell>
                <TableCell className="truncate text-sm text-gray-500">{getProjectLabel(proposal.project, t)}</TableCell>
                <TableCell>
                  <div className="flex flex-col items-start gap-1.5">
                    <Badge variant="outline" className={statusMeta.className}>
                      {t(`productResearch.proposalStatus.${proposal.status}` as never)}
                    </Badge>
                    {planningStatus ? (
                      <Badge
                        variant="outline"
                        className={PROPOSAL_PLANNING_STATUS_META[planningStatus].className}
                      >
                        {t(`productResearch.planningRunStatus.${planningStatus}` as never)}
                      </Badge>
                    ) : null}
                  </div>
                </TableCell>
                <TableCell className="text-right text-sm text-gray-400">{formatRelativeTime(proposal.created_at)}</TableCell>
              </TableRow>
            );
          })}
          <TablePaginationFooter columnCount={4} page={page} pageCount={pageCount} total={totalCount} onPageChange={onPageChange} />
        </TableBody>
      </Table>
    </div>
  );
}
