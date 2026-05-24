import { Search } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import type { AgentFilterValue, StatusFilterValue } from '../types';

type WorkspaceSettingsFiltersProps = {
  searchQuery: string;
  agentFilter: AgentFilterValue;
  statusFilter: StatusFilterValue;
  onSearchQueryChange: (value: string) => void;
  onAgentFilterChange: (value: AgentFilterValue) => void;
  onStatusFilterChange: (value: StatusFilterValue) => void;
};

export function WorkspaceSettingsFilters({
  searchQuery,
  agentFilter,
  statusFilter,
  onSearchQueryChange,
  onAgentFilterChange,
  onStatusFilterChange,
}: WorkspaceSettingsFiltersProps) {
  const { t } = useTranslation();

  return (
    <div className="flex flex-col gap-3 border-b border-black/8 px-1 py-4 md:flex-row">
      <div className="relative min-w-0 flex-1">
        <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-black/35" />
        <Input
          aria-label={t('workspaceSettings.searchLabel')}
          value={searchQuery}
          onChange={event => onSearchQueryChange(event.target.value)}
          placeholder={t('workspaceSettings.searchPlaceholder')}
          className="h-10 rounded-xl border-black/10 bg-white pl-10 shadow-none"
        />
      </div>

      <Select
        aria-label={t('workspaceSettings.agentFilterLabel')}
        value={agentFilter}
        onChange={event => onAgentFilterChange(event.target.value as AgentFilterValue)}
        className="h-10 min-w-[150px] rounded-xl border-black/10 bg-white shadow-none"
      >
        <option value="all">{t('workspaceSettings.filterAllAgents')}</option>
        <option value="sophie">{t('workspaceSettings.agentSophie')}</option>
        <option value="tela">{t('workspaceSettings.agentTela')}</option>
        <option value="marc">{t('workspaceSettings.agentMarc')}</option>
      </Select>

      <Select
        aria-label={t('workspaceSettings.statusFilterLabel')}
        value={statusFilter}
        onChange={event => onStatusFilterChange(event.target.value as StatusFilterValue)}
        className="h-10 min-w-[150px] rounded-xl border-black/10 bg-white shadow-none"
      >
        <option value="all">{t('workspaceSettings.filterAllStatuses')}</option>
        <option value="ready">{t('workspaceSettings.statusReady')}</option>
        <option value="running">{t('workspaceSettings.statusRunning')}</option>
        <option value="unconfigured">{t('workspaceSettings.statusUnconfigured')}</option>
        <option value="inactive">{t('workspaceSettings.statusInactive')}</option>
      </Select>
    </div>
  );
}
