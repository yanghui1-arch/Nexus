import { Button } from '@/components/ui/button';
import { FILTERS, type FilterTab } from './overview-utils';

type TaskCounts = {
  running: number;
  waiting_for_review: number;
  merged: number;
  closed: number;
  fail: number;
};

type OverviewTaskFiltersProps = {
  filter: FilterTab;
  counts: TaskCounts;
  total: number;
  onChange: (nextFilter: FilterTab) => void;
};

function filterCount(filter: FilterTab, counts: TaskCounts, total: number): number {
  if (filter === 'all') return total;
  if (filter === 'fail') return counts.fail;
  return counts[filter];
}

export function OverviewTaskFilters({
  filter,
  counts,
  total,
  onChange,
}: OverviewTaskFiltersProps) {
  return (
    <div className="flex flex-wrap gap-2">
      {FILTERS.map(item => {
        const count = filterCount(item.key, counts, total);

        return (
          <Button
            key={item.key}
            type="button"
            size="sm"
            variant={filter === item.key ? 'default' : 'outline'}
            onClick={() => onChange(item.key)}
          >
            {item.label} ({count})
          </Button>
        );
      })}
    </div>
  );
}
