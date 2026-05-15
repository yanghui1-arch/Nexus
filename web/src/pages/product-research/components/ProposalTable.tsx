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

export function ProposalTable({
  page,
  pageCount,
  proposals,
  totalCount,
  onSelect,
  onPageChange,
}: ProposalTableProps) {
  return (
    <div className={TABLE_CARD_CLASS}>
      <Table className="table-fixed">
        <TableHeader>
          <TableRow className={TABLE_HEADER_ROW_CLASS}>
            <TableHead className={`w-[52%] ${TABLE_HEAD_CLASS}`}>Title</TableHead>
            <TableHead className={`w-[16%] ${TABLE_HEAD_CLASS}`}>Project</TableHead>
            <TableHead className={`w-[20%] ${TABLE_HEAD_CLASS}`}>Status</TableHead>
            <TableHead className={`w-[12%] text-right ${TABLE_HEAD_CLASS}`}>
              Submitted
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody className={TABLE_BODY_CLASS}>
          {proposals.map(proposal => {
            const statusMeta = PROPOSAL_STATUS_META[proposal.status];

            return (
              <TableRow
                key={proposal.id}
                tabIndex={0}
                className={TABLE_ROW_CLASS}
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
                    <Link
                      to={`/product-research/proposals/${proposal.id}`}
                      className="truncate font-medium text-black hover:underline"
                      onClick={event => event.stopPropagation()}
                    >
                      {proposal.title}
                    </Link>
                    <span className="text-xs text-black/45">
                      {proposal.repo ?? 'No repository'}
                    </span>
                  </div>
                </TableCell>
                <TableCell className="truncate text-sm text-black/55">
                  {getProjectLabel(proposal.project)}
                </TableCell>
                <TableCell>
                  <Badge variant={statusMeta.variant} className={statusMeta.className}>
                    {statusMeta.label}
                  </Badge>
                </TableCell>
                <TableCell className="text-right text-sm text-black/45">
                  {formatRelativeTime(proposal.created_at)}
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
        <TablePaginationFooter
          columnCount={4}
          page={page}
          pageCount={pageCount}
          total={totalCount}
          onPageChange={onPageChange}
        />
      </Table>
    </div>
  );
}
