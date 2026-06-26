import { useTranslation } from 'react-i18next';
import { Loader2 } from 'lucide-react';
import type { ApiAgentInstance } from '@/api/types';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { useState } from 'react';
import { getAgentLabel, getStatusLabel } from '../utils';

type WorkspaceSettingsTableProps = {
  instances: ApiAgentInstance[];
  isLoading: boolean;
  isSaving: boolean;
  onSave: (instanceId: string, displayName: string | null, githubRepo: string | null, project: string | null) => Promise<void>;
};

export function WorkspaceSettingsTable({
  instances,
  isLoading,
  isSaving,
  onSave,
}: WorkspaceSettingsTableProps) {
  const { t } = useTranslation();
  const [editingInstance, setEditingInstance] = useState<ApiAgentInstance | null>(null);
  const [editDisplayName, setEditDisplayName] = useState('');
  const [editRepo, setEditRepo] = useState('');
  const [editProject, setEditProject] = useState('');

  const handleEdit = (instance: ApiAgentInstance) => {
    setEditingInstance(instance);
    setEditDisplayName(instance.display_name ?? '');
    setEditRepo(instance.workspace?.github_repo ?? '');
    setEditProject(instance.workspace?.project ?? '');
  };

  const handleSave = async () => {
    if (!editingInstance) return;
    await onSave(
      editingInstance.id,
      editDisplayName || null,
      editRepo || null,
      editProject || null,
    );
    setEditingInstance(null);
  };

  if (isLoading) {
    return (
      <div className="rounded-2xl border border-gray-200/60 bg-white p-8">
        <div className="flex items-center gap-2 text-sm text-gray-400">
          <Loader2 className="size-4 animate-spin" />
          {t('workspaceSettings.loading')}
        </div>
      </div>
    );
  }

  if (instances.length === 0) {
    return (
      <div className="rounded-2xl border border-gray-200/60 bg-white p-12 text-center">
        <p className="text-sm font-medium text-[hsl(0,0%,8%)]">{t('workspaceSettings.emptyTitle')}</p>
        <p className="mt-1 text-sm text-gray-400">{t('workspaceSettings.emptyDescription')}</p>
      </div>
    );
  }

  return (
    <>
      <div className="rounded-2xl border border-gray-200/60 bg-white overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="bg-gray-50/80 border-gray-100">
              <TableHead className="h-11 text-[11px] font-semibold uppercase tracking-wider text-gray-400">{t('workspaceSettings.tableInstance')}</TableHead>
              <TableHead className="h-11 text-[11px] font-semibold uppercase tracking-wider text-gray-400">{t('workspaceSettings.tableAgent')}</TableHead>
              <TableHead className="h-11 text-[11px] font-semibold uppercase tracking-wider text-gray-400">{t('workspaceSettings.tableWorkspace')}</TableHead>
              <TableHead className="h-11 text-[11px] font-semibold uppercase tracking-wider text-gray-400">{t('workspaceSettings.tableStatus')}</TableHead>
              <TableHead className="h-11 text-[11px] font-semibold uppercase tracking-wider text-gray-400 text-right">{t('workspaceSettings.tableActions')}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {instances.map((instance, idx) => {
              const statusLabel = getStatusLabel(instance, t);
              return (
                <TableRow key={instance.id} className={idx % 2 === 1 ? 'bg-gray-50/30' : ''}>
                  <TableCell>
                    <div className="flex min-w-0 flex-col gap-0.5">
                      <span className="text-sm font-semibold text-[hsl(0,0%,8%)]">
                        {instance.display_name ?? instance.client_id}
                      </span>
                      <span className="text-xs text-gray-400">{instance.client_id}</span>
                    </div>
                  </TableCell>
                  <TableCell>
                    <Badge variant="secondary" className="bg-gray-100 text-gray-600">
                      {getAgentLabel(instance.agent, t)}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <div className="flex min-w-0 flex-col gap-0.5">
                      <span className="truncate text-sm text-gray-600">
                        {instance.workspace?.github_repo ?? t('workspaceSettings.unconfigured')}
                      </span>
                      <span className="truncate text-xs text-gray-400">
                        {instance.workspace?.project ?? '-'}
                      </span>
                    </div>
                  </TableCell>
                  <TableCell>
                    <span className={`inline-flex items-center gap-1.5 text-xs font-medium ${
                      statusLabel === t('workspaceSettings.statusReady') || statusLabel === t('workspaceSettings.statusIdle')
                        ? 'text-green-600'
                        : statusLabel === t('workspaceSettings.statusRunning')
                          ? 'text-blue-600'
                          : statusLabel === t('workspaceSettings.statusInactive')
                            ? 'text-gray-400'
                            : 'text-orange-600'
                    }`}>
                      <span className={`size-1.5 rounded-full ${
                        statusLabel === t('workspaceSettings.statusReady') || statusLabel === t('workspaceSettings.statusIdle')
                          ? 'bg-green-500'
                          : statusLabel === t('workspaceSettings.statusRunning')
                            ? 'bg-blue-500'
                            : statusLabel === t('workspaceSettings.statusInactive')
                              ? 'bg-gray-300'
                              : 'bg-orange-500'
                      }`} />
                      {statusLabel}
                    </span>
                  </TableCell>
                  <TableCell className="text-right">
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 text-xs"
                      onClick={() => handleEdit(instance)}
                    >
                      {t('workspaceSettings.edit')}
                    </Button>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>

      <Dialog open={editingInstance !== null} onOpenChange={open => { if (!open) setEditingInstance(null); }}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>{t('workspaceSettings.editorTitle')}</DialogTitle>
            <DialogDescription>{t('workspaceSettings.editorDescription')}</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-2">
            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium text-[hsl(0,0%,8%)]">{t('workspaceSettings.nickname')}</label>
              <Input
                value={editDisplayName}
                onChange={e => setEditDisplayName(e.target.value)}
                placeholder={t('workspaceSettings.nicknamePlaceholder')}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium text-[hsl(0,0%,8%)]">{t('workspaceSettings.repository')}</label>
              <Input
                value={editRepo}
                onChange={e => setEditRepo(e.target.value)}
                placeholder="owner/repo"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium text-[hsl(0,0%,8%)]">{t('workspaceSettings.project')}</label>
              <Input
                value={editProject}
                onChange={e => setEditProject(e.target.value)}
                placeholder={t('workspaceSettings.projectPlaceholder')}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditingInstance(null)}>
              Cancel
            </Button>
            <Button
              onClick={handleSave}
              disabled={isSaving}
              className="bg-[hsl(0,0%,8%)] text-white hover:bg-[hsl(0,0%,20%)]"
            >
              {isSaving ? t('workspaceSettings.saving') : t('workspaceSettings.save')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
