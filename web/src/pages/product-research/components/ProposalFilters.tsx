import { Select } from '@/components/ui/select';
import { ALL_PROJECTS, PROPOSAL_FILTER_OPTIONS } from '../constants';
import type { ProjectOption, ProposalFilter } from '../types';

type ProposalFiltersProps = {
  proposalFilter: ProposalFilter;
  projectFilter: string;
  projectOptions: ProjectOption[];
  onProposalFilterChange: (filter: ProposalFilter) => void;
  onProjectFilterChange: (project: string) => void;
};

export function ProposalFilters({
  proposalFilter,
  projectFilter,
  projectOptions,
  onProposalFilterChange,
  onProjectFilterChange,
}: ProposalFiltersProps) {
  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between">
      <div className="flex items-center gap-2 sm:min-w-[220px]">
        <span className="text-sm text-muted-foreground">Status</span>
        <Select
          aria-label="Filter requirements by status"
          className="sm:max-w-[200px]"
          name="proposal-status-filter"
          value={proposalFilter}
          onChange={event =>
            onProposalFilterChange(event.target.value as ProposalFilter)
          }
        >
          {PROPOSAL_FILTER_OPTIONS.map(option => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </Select>
      </div>

      <div className="flex items-center gap-2 sm:min-w-[240px]">
        <span className="text-sm text-muted-foreground">Project</span>
        <Select
          aria-label="Filter requirements by project"
          className="sm:max-w-[220px]"
          name="proposal-project-filter"
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
    </div>
  );
}
