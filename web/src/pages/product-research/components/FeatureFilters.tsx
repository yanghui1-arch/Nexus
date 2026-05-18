import { useTranslation } from 'react-i18next';
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
  const { t } = useTranslation();
  return (
    <div className="flex items-center gap-2 sm:justify-end">
      <span className="text-sm text-muted-foreground">{t('common.project')}</span>
      <Select
        aria-label={t('productResearch.filterFeaturesByProject')}
        className="max-w-[220px]"
        name="feature-project-filter"
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
  );
}
