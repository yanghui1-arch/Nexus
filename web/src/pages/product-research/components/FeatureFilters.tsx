import { Select } from '@/components/ui/select';
import { ALL_PROJECTS } from '../constants';
import type { ProjectOption } from '../types';

type FeatureFiltersProps = {
  projectFilter: string;
  projectOptions: ProjectOption[];
  onProjectFilterChange: (project: string) => void;
};

export function FeatureFilters({
  projectFilter,
  projectOptions,
  onProjectFilterChange,
}: FeatureFiltersProps) {
  return (
    <div className="flex items-center gap-2 sm:justify-end">
      <span className="text-sm text-muted-foreground">Project</span>
      <Select
        aria-label="Filter features by project"
        className="max-w-[220px]"
        name="feature-project-filter"
        value={projectFilter}
        onChange={event => onProjectFilterChange(event.target.value)}
      >
        <option value={ALL_PROJECTS}>All projects</option>
        {projectOptions.map(option => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </Select>
    </div>
  );
}
