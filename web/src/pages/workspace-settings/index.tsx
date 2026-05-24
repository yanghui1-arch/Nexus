import { Loader2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useAppLayout } from '@/components/layout/AppLayout';
import { WorkspaceSettingsDialog } from './components/WorkspaceSettingsDialog';
import { WorkspaceSettingsFilters } from './components/WorkspaceSettingsFilters';
import { WorkspaceSettingsTable } from './components/WorkspaceSettingsTable';
import { useWorkspaceSettings } from './hooks/useWorkspaceSettings';

export default function WorkspaceSettingsPage() {
  const { t } = useTranslation();
  const workspaceSettings = useWorkspaceSettings();

  useAppLayout({
    title: t('workspaceSettings.title'),
    mainClassName: 'pt-4 pb-6',
  });

  if (workspaceSettings.isLoading) {
    return (
      <section className="flex flex-1 items-center justify-center">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="size-4 animate-spin" />
          <span>{t('workspaceSettings.loading')}</span>
        </div>
      </section>
    );
  }

  if (!workspaceSettings.hasInstances) {
    return (
      <section className="px-1 py-10 text-center text-sm text-black/55">
        {t('workspaceSettings.emptyTitle')}
      </section>
    );
  }

  return (
    <>
      <section>
        <WorkspaceSettingsFilters
          searchQuery={workspaceSettings.searchQuery}
          agentFilter={workspaceSettings.agentFilter}
          statusFilter={workspaceSettings.statusFilter}
          onSearchQueryChange={workspaceSettings.updateSearchQuery}
          onAgentFilterChange={workspaceSettings.updateAgentFilter}
          onStatusFilterChange={workspaceSettings.updateStatusFilter}
        />
        <WorkspaceSettingsTable
          instances={workspaceSettings.filteredInstances}
          drafts={workspaceSettings.drafts}
          onSelect={workspaceSettings.openInstance}
        />
      </section>

      <WorkspaceSettingsDialog
        instance={workspaceSettings.selectedInstance}
        draft={workspaceSettings.selectedDraft}
        isDirty={workspaceSettings.isSelectedDirty}
        isSaving={workspaceSettings.isSelectedSaving}
        onClose={workspaceSettings.closeDialog}
        onDraftChange={workspaceSettings.updateSelectedDraftField}
        onSave={() => void workspaceSettings.saveSelectedInstance()}
      />
    </>
  );
}
