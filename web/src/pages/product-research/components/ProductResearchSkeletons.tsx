import { Skeleton } from '@/components/ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  TABLE_BODY_CLASS,
  TABLE_CARD_CLASS,
  TABLE_HEAD_CLASS,
  TABLE_HEADER_ROW_CLASS,
} from '../constants';

const SKELETON_ROW_COUNT = 6;

function TextSkeletonGroup() {
  return (
    <div className="flex min-w-0 flex-col gap-2">
      <Skeleton className="h-4 w-3/4" />
      <Skeleton className="h-3 w-1/2" />
    </div>
  );
}

function ProductResearchTableSkeleton({
  columns,
  label,
}: {
  columns: Array<{ className: string; label: string }>;
  label: string;
}) {
  return (
    <div className={TABLE_CARD_CLASS} aria-busy="true" aria-label={label}>
      <Table className="table-fixed">
        <TableHeader>
          <TableRow className={TABLE_HEADER_ROW_CLASS}>
            {columns.map(column => (
              <TableHead key={column.label} className={`${column.className} ${TABLE_HEAD_CLASS}`}>
                {column.label}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody className={TABLE_BODY_CLASS}>
          {Array.from({ length: SKELETON_ROW_COUNT }).map((_, rowIndex) => (
            <TableRow key={rowIndex} className="border-black/10">
              {columns.map((column, columnIndex) => (
                <TableCell key={column.label} className={column.className.includes('text-right') ? 'text-right' : undefined}>
                  {columnIndex === 0 ? (
                    <TextSkeletonGroup />
                  ) : column.className.includes('text-right') ? (
                    <Skeleton className="ml-auto h-4 w-16" />
                  ) : columnIndex === 2 ? (
                    <div className="flex flex-col gap-2">
                      <Skeleton className="h-6 w-24 rounded-full" />
                      {columns.length === 4 ? <Skeleton className="h-6 w-28 rounded-full" /> : null}
                    </div>
                  ) : columnIndex === 3 && columns.length === 5 ? (
                    <div className="flex items-center gap-3">
                      <Skeleton className="h-2 flex-1 rounded-full" />
                      <Skeleton className="h-3 w-8" />
                    </div>
                  ) : (
                    <Skeleton className="h-4 w-24" />
                  )}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

export function ProposalTableSkeleton({ label }: { label: string }) {
  return (
    <ProductResearchTableSkeleton
      label={label}
      columns={[
        { label: 'Title', className: 'w-[52%]' },
        { label: 'Project', className: 'w-[16%]' },
        { label: 'Status', className: 'w-[20%]' },
        { label: 'Submitted', className: 'w-[12%] text-right' },
      ]}
    />
  );
}

export function FeatureTableSkeleton({ label }: { label: string }) {
  return (
    <ProductResearchTableSkeleton
      label={label}
      columns={[
        { label: 'Title', className: 'w-[38%]' },
        { label: 'Project', className: 'w-[18%]' },
        { label: 'Status', className: 'w-[18%]' },
        { label: 'Progress', className: 'w-[18%]' },
        { label: 'Updated', className: 'w-[8%] text-right' },
      ]}
    />
  );
}

export function ProposalDetailSkeleton({ label }: { label: string }) {
  return (
    <article className="flex flex-col gap-5" aria-busy="true" aria-label={label}>
      <header className="flex flex-col gap-3 border-b pb-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div className="flex min-w-0 flex-1 flex-col gap-3">
            <Skeleton className="h-8 w-2/3 max-w-xl" />
            <div className="flex flex-wrap gap-3">
              <Skeleton className="h-4 w-28" />
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-4 w-36" />
            </div>
          </div>
          <div className="flex flex-wrap gap-2 lg:justify-end">
            <Skeleton className="h-6 w-24 rounded-full" />
            <Skeleton className="h-6 w-28 rounded-full" />
          </div>
        </div>
      </header>

      <div className="flex gap-2">
        <Skeleton className="h-9 w-28" />
        <Skeleton className="h-9 w-24" />
      </div>

      <section className="flex flex-col gap-8">
        <div className="flex flex-col gap-3">
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-11/12" />
          <Skeleton className="h-4 w-4/5" />
        </div>
        <div className="flex flex-col gap-3">
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-10/12" />
          <Skeleton className="h-4 w-3/4" />
        </div>
      </section>
    </article>
  );
}

export function FeatureDetailSkeleton({ label }: { label: string }) {
  return (
    <div className="rounded-xl border bg-card py-6 shadow-sm" aria-busy="true" aria-label={label}>
      <div className="grid gap-3 border-b px-6 pb-6 lg:grid-cols-[1fr_auto]">
        <div className="flex flex-col gap-2">
          <Skeleton className="h-6 w-2/3 max-w-lg" />
          <div className="flex flex-wrap gap-3">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-4 w-36" />
          </div>
        </div>
        <div className="flex gap-2">
          <Skeleton className="h-6 w-24 rounded-full" />
          <Skeleton className="h-6 w-20 rounded-full" />
        </div>
      </div>
      <div className="flex flex-col gap-6 px-6 pt-6">
        <div className="flex flex-col gap-3">
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-5/6" />
        </div>
        <div className="flex flex-col gap-3">
          <Skeleton className="h-4 w-28" />
          {Array.from({ length: 3 }).map((_, index) => (
            <div key={index} className="rounded-lg border bg-background/70 p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="flex flex-1 flex-col gap-2">
                  <Skeleton className="h-4 w-1/2" />
                  <Skeleton className="h-4 w-4/5" />
                </div>
                <Skeleton className="h-6 w-24 rounded-full" />
              </div>
              <Skeleton className="mt-3 h-3 w-40" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
