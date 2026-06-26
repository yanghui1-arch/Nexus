import { useTranslation } from 'react-i18next';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import type { WorkspaceSettingsFilter } from '../types';

type WorkspaceSettingsFiltersProps = {
  filter: WorkspaceSettingsFilter;
  onFilterChange: (filter: WorkspaceSettingsFilter) => void;
  agentOptions: string[];
  statusOptions: string[];
};

export function WorkspaceSettingsFilters({
  filter,
  onFilterChange,
  agentOptions,
  statusOptions,
}: WorkspaceSettingsFiltersProps) {
  const { t } = useTranslation();

  const update = <K extends keyof WorkspaceSettingsFilter>(key: K, value: WorkspaceSettingsFilter[K]) => {
    onFilterChange({ ...filter, [key]: value });
  };

  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
      <div className="flex-1 sm:max-w-xs">
        <Input
          placeholder={t('workspaceSettings.searchPlaceholder')}
          value={filter.search}
          onChange={e => update('search', e.target.value)}
          className="h-9"
        />
      </div>
      <div className="flex items-center gap-2">
        <span className="text-sm text-gray-500">{t('workspaceSettings.agentFilterLabel')}</span>
        <Select value={filter.agent} onValueChange={v => update('agent', v)}>
          <SelectTrigger className="h-9 w-[140px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{t('workspaceSettings.filterAllAgents')}</SelectItem>
            {agentOptions.map(a => (
              <SelectItem key={a} value={a}>{a}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <div className="flex items-center gap-2">
        <span className="text-sm text-gray-500">{t('workspaceSettings.statusFilterLabel')}</span>
        <Select value={filter.status} onValueChange={v => update('status', v)}>
          <SelectTrigger className="h-9 w-[140px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{t('workspaceSettings.filterAllStatuses')}</SelectItem>
            {statusOptions.map(s => (
              <SelectItem key={s} value={s}>{s}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
    </div>
  );
}
