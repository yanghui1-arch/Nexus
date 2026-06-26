import { useTranslation } from 'react-i18next';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
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
  const { t } = useTranslation();
  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-center gap-2">
        <span className="text-sm font-medium text-gray-500">{t('common.status')}</span>
        <Select value={proposalFilter} onValueChange={v => onProposalFilterChange(v as ProposalFilter)}>
          <SelectTrigger className="h-9 w-[160px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {PROPOSAL_FILTER_OPTIONS.map(option => (
              <SelectItem key={option.value} value={option.value}>
                {t(`productResearch.proposalFilter.${option.value}` as never)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="flex items-center gap-2">
        <span className="text-sm font-medium text-gray-500">{t('common.project')}</span>
        <Select value={projectFilter} onValueChange={onProjectFilterChange}>
          <SelectTrigger className="h-9 w-[200px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL_PROJECTS}>{t('productResearch.allProjects')}</SelectItem>
            {projectOptions.map(option => (
              <SelectItem key={option.value} value={option.value}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
    </div>
  );
}
