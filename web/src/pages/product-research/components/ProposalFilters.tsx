import { useTranslation } from 'react-i18next';
import { Select } from '@/components/ui/select';
import { ALL_PROJECTS, PROPOSAL_FILTER_OPTIONS } from '../constants';
import type { ProjectOption, ProposalFilter } from '../types';
import type { ProposalReviewCounts } from '../view-model/proposalReviewCounts';

type ProposalFiltersProps = {
  proposalCounts: ProposalReviewCounts;
  proposalFilter: ProposalFilter;
  projectFilter: string;
  projectOptions: ProjectOption[];
  onProposalFilterChange: (filter: ProposalFilter) => void;
  onProjectFilterChange: (project: string) => void;
};

export function ProposalFilters({
  proposalCounts,
  proposalFilter,
  projectFilter,
  projectOptions,
  onProposalFilterChange,
  onProjectFilterChange,
}: ProposalFiltersProps) {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between">
      <div className="flex items-center gap-2 sm:min-w-[220px]">
        <span className="text-sm text-muted-foreground">{t('common.status')}</span>
        <Select
          aria-label={t('productResearch.filterRequirementsByStatus')}
          className="sm:max-w-[200px]"
          name="proposal-status-filter"
          value={proposalFilter}
          onChange={event => onProposalFilterChange(event.target.value as ProposalFilter)}
        >
          {PROPOSAL_FILTER_OPTIONS.map(option => (
            <option key={option.value} value={option.value}>
              {t(`productResearch.proposalFilter.${option.value}`, {
                count: proposalCounts[option.value],
              })}
            </option>
          ))}
        </Select>
      </div>

      <div className="flex items-center gap-2 sm:min-w-[240px]">
        <span className="text-sm text-muted-foreground">{t('common.project')}</span>
        <Select
          aria-label={t('productResearch.filterRequirementsByProject')}
          className="sm:max-w-[220px]"
          name="proposal-project-filter"
          value={projectFilter}
          onChange={event => onProjectFilterChange(event.target.value)}
        >
          <option value={ALL_PROJECTS}>{t('productResearch.allProjects')}</option>
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
