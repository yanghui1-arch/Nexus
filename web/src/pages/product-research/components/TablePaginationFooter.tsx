import { Button } from '@/components/ui/button';
import { TableCell, TableFooter, TableRow } from '@/components/ui/table';
import { PAGE_SIZE } from '../constants';

type TablePaginationFooterProps = {
  columnCount: number;
  page: number;
  pageCount: number;
  total: number;
  onPageChange: (page: number) => void;
};

export function TablePaginationFooter({
  columnCount,
  page,
  pageCount,
  total,
  onPageChange,
}: TablePaginationFooterProps) {
  const start = total === 0 ? 0 : (page - 1) * PAGE_SIZE + 1;
  const end = Math.min(page * PAGE_SIZE, total);

  return (
    <TableFooter>
      <TableRow className="border-black/10 bg-black/[0.02] hover:bg-black/[0.02]">
        <TableCell colSpan={columnCount} className="p-0">
          <div className="flex flex-col gap-3 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm text-black/55">
              Showing {start} to {end} of {total} entries
            </p>
            <div className="flex items-center gap-2 self-end sm:self-auto">
              <Button
                type="button"
                size="sm"
                variant="ghost"
                className="text-black/65 hover:bg-black/[0.05] hover:text-black"
                disabled={page <= 1}
                onClick={() => onPageChange(page - 1)}
              >
                Previous
              </Button>
              <div className="flex items-center gap-1">
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  className="border-black/10 bg-white text-black"
                  disabled
                >
                  {page}
                </Button>
                <span className="px-1 text-sm text-black/55">/ {pageCount}</span>
              </div>
              <Button
                type="button"
                size="sm"
                variant="ghost"
                className="text-black/65 hover:bg-black/[0.05] hover:text-black"
                disabled={page >= pageCount}
                onClick={() => onPageChange(page + 1)}
              >
                Next
              </Button>
            </div>
          </div>
        </TableCell>
      </TableRow>
    </TableFooter>
  );
}
