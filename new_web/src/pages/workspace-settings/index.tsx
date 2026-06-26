import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { useAppLayout } from '@/components/layout/AppLayout';
import { WorkspaceSettingsFilters } from './components/WorkspaceSettingsFilters';
import { WorkspaceSettingsTable } from './components/WorkspaceSettingsTable';
import { useWorkspaceSettings } from './hooks/useWorkspaceSettings';

export default function WorkspaceSettingsPage() {
  const { t } = useTranslation();

  useAppLayout({
    title: t('workspaceSettings.title'),
    description: t('workspaceSettings.description'),
  });

  const {
    instances,
    filter,
    setFilter,
    filteredInstances,
    isLoading,
    isSaving,
    saveInstance,
  } = useWorkspaceSettings();

  const agentOptions = useMemo(() => {
    const agents = new Set(instances.map(i => i.agent));
    return [...agents];
  }, [instances]);

  const statusOptions = useMemo(() => [
    t('workspaceSettings.statusIdle'),
    t('workspaceSettings.statusRunning'),
    t('workspaceSettings.statusInactive'),
    t('workspaceSettings.statusUnconfigured'),
  ], [t]);

  return (
    <div className="flex flex-col gap-5">
      <WorkspaceSettingsFilters
        filter={filter}
        onFilterChange={setFilter}
        agentOptions={agentOptions}
        statusOptions={statusOptions}
      />

      <WorkspaceSettingsTable
        instances={filteredInstances}
        isLoading={isLoading}
        isSaving={isSaving}
        onSave={saveInstance}
      />

      <p className="text-xs text-gray-400">
        {t('workspaceSettings.showingCount', { shown: filteredInstances.length, total: instances.length })}
      </p>
    </div>
  );
}
