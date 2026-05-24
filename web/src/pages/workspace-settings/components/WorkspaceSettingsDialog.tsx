import { useTranslation } from 'react-i18next';
import type { ApiAgentInstance } from '@/api/types';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';
import type { InstanceDraft } from '../types';
import {
  formatExpiry,
  getAgentMeta,
  getInstanceLabel,
  getStatusMeta,
  getWorkspaceVisualStatus,
} from '../utils';

type WorkspaceSettingsDialogProps = {
  instance: ApiAgentInstance | null;
  draft: InstanceDraft | null;
  isDirty: boolean;
  isSaving: boolean;
  onClose: () => void;
  onDraftChange: (key: keyof InstanceDraft, value: string) => void;
  onSave: () => void;
};

export function WorkspaceSettingsDialog({
  instance,
  draft,
  isDirty,
  isSaving,
  onClose,
  onDraftChange,
  onSave,
}: WorkspaceSettingsDialogProps) {
  const { t } = useTranslation();
  const isOpen = instance !== null && draft !== null;

  return (
    <Dialog open={isOpen} onOpenChange={open => !open && onClose()}>
      {isOpen && instance && draft ? (
        <DialogContent className="gap-0 overflow-hidden border-black/10 p-0 sm:max-w-2xl">
          {(() => {
            const agentMeta = getAgentMeta(t, instance.agent);
            const status = getWorkspaceVisualStatus(instance);
            const statusMeta = getStatusMeta(t, status);
            const AgentIcon = agentMeta.icon;
            const StatusIcon = statusMeta.icon;
            const label = getInstanceLabel(instance, draft);

            return (
              <>
                <div className="border-b border-black/8 px-6 py-5">
                  <DialogHeader className="gap-3">
                    <div className="min-w-0">
                      <DialogTitle className="truncate text-xl">{label}</DialogTitle>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <div
                        className={cn(
                          'inline-flex items-center gap-2 rounded-full border px-3 py-1 text-sm font-medium',
                          agentMeta.chipClassName,
                        )}
                      >
                        <AgentIcon className={cn('size-4', agentMeta.iconClassName)} />
                        <span>{agentMeta.label}</span>
                      </div>
                      <div
                        className={cn(
                          'inline-flex items-center gap-2 rounded-full border px-3 py-1 text-sm font-medium',
                          statusMeta.className,
                        )}
                      >
                        <StatusIcon
                          className={cn(
                            'size-4',
                            statusMeta.iconClassName,
                            status === 'running' ? 'animate-spin' : undefined,
                          )}
                        />
                        <span>{statusMeta.label}</span>
                      </div>
                    </div>
                  </DialogHeader>
                </div>

                <div className="grid gap-4 px-6 py-5 sm:grid-cols-2">
                  <div className="space-y-1.5 sm:col-span-2">
                    <label
                      htmlFor={`display-name-${instance.id}`}
                      className="text-sm font-medium text-black/80"
                    >
                      {t('workspaceSettings.nickname')}
                    </label>
                    <Input
                      id={`display-name-${instance.id}`}
                      value={draft.displayName}
                      onChange={event => onDraftChange('displayName', event.target.value)}
                      placeholder={t('workspaceSettings.nicknamePlaceholder')}
                      className="h-11 rounded-xl border-black/10 shadow-none"
                    />
                  </div>

                  <div className="space-y-1.5">
                    <label
                      htmlFor={`github-repo-${instance.id}`}
                      className="text-sm font-medium text-black/80"
                    >
                      {t('workspaceSettings.repository')}
                    </label>
                    <Input
                      id={`github-repo-${instance.id}`}
                      value={draft.githubRepo}
                      onChange={event => onDraftChange('githubRepo', event.target.value)}
                      placeholder="owner/repository"
                      className="h-11 rounded-xl border-black/10 shadow-none"
                    />
                  </div>

                  <div className="space-y-1.5">
                    <label
                      htmlFor={`project-${instance.id}`}
                      className="text-sm font-medium text-black/80"
                    >
                      {t('workspaceSettings.project')}
                    </label>
                    <Input
                      id={`project-${instance.id}`}
                      value={draft.project}
                      onChange={event => onDraftChange('project', event.target.value)}
                      placeholder={t('workspaceSettings.projectPlaceholder')}
                      className="h-11 rounded-xl border-black/10 shadow-none"
                    />
                  </div>

                  <div className="space-y-1.5 sm:col-span-2">
                    <label className="text-sm font-medium text-black/80">
                      {t('workspaceSettings.expiresAt')}
                    </label>
                    <div className="h-11 rounded-xl border border-black/10 bg-black/[0.02] px-3 py-2 text-sm text-black/65">
                      {formatExpiry(instance.expires_at)}
                    </div>
                  </div>
                </div>

                <DialogFooter className="border-t border-black/8 px-6 py-4">
                  <DialogClose asChild>
                    <Button type="button" variant="outline" className="rounded-xl border-black/10">
                      {t('codeReview.close')}
                    </Button>
                  </DialogClose>
                  <Button
                    type="button"
                    disabled={isSaving || !isDirty}
                    className="rounded-xl bg-black text-white hover:bg-black/90"
                    onClick={onSave}
                  >
                    {isSaving ? t('workspaceSettings.saving') : t('workspaceSettings.save')}
                  </Button>
                </DialogFooter>
              </>
            );
          })()}
        </DialogContent>
      ) : null}
    </Dialog>
  );
}
