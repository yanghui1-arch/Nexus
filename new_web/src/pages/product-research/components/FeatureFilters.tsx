import { useTranslation } from 'react-i18next';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
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
  );
}
