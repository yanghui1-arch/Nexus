import { useTranslation } from 'react-i18next';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { Button } from '@/components/ui/button';

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
  const { t } = useTranslation();
  const start = (page - 1) * 10 + 1;
  const end = Math.min(page * 10, total);

  return (
    <>
      <tr>
        <td colSpan={columnCount} className="border-t border-gray-100 px-4 py-3">
          <div className="flex items-center justify-between">
            <p className="text-xs text-gray-400">
              {t('productResearch.showingEntries', { start, end, total })}
            </p>
            <div className="flex items-center gap-1">
              <Button
                variant="ghost"
                size="sm"
                className="h-7 w-7 p-0"
                disabled={page <= 1}
                onClick={() => onPageChange(page - 1)}
              >
                <ChevronLeft className="size-3.5" />
              </Button>
              <span className="px-2 text-xs text-gray-500">
                {page} / {pageCount}
              </span>
              <Button
                variant="ghost"
                size="sm"
                className="h-7 w-7 p-0"
                disabled={page >= pageCount}
                onClick={() => onPageChange(page + 1)}
              >
                <ChevronRight className="size-3.5" />
              </Button>
            </div>
          </div>
        </td>
      </tr>
    </>
  );
}
