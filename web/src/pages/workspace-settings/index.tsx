import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  AlertCircle,
  CheckCircle2,
  Hammer,
  Lightbulb,
  Loader2,
  PenTool,
  Save,
  Search,
  Settings2,
  type LucideIcon,
} from 'lucide-react';
import { toast } from 'sonner';
import {
  listAgentInstances,
  updateAgentInstance,
  updateAgentWorkspace,
} from '@/api/agentInstances';
import { getErrorDetail } from '@/api/client';
import type { ApiAgentInstance, ApiAgentKind } from '@/api/types';
import { useAppLayout } from '@/components/layout/AppLayout';
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
import { Select } from '@/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { cn } from '@/lib/utils';
import { formatAgentLabel } from '@/lib/workspace-task-view';

type InstanceDraft = {
  displayName: string;
  githubRepo: string;
  project: string;
};

type WorkspaceVisualStatus = 'ready' | 'running' | 'inactive' | 'unconfigured';
type AgentFilterValue = 'all' | ApiAgentKind;
type StatusFilterValue = 'all' | WorkspaceVisualStatus;

type StatusMeta = {
  icon: LucideIcon;
  label: string;
  className: string;
  iconClassName: string;
};

type AgentMeta = {
  label: string;
  icon: LucideIcon;
  chipClassName: string;
  iconClassName: string;
};

function normalizeText(value: string): string | null {
  const nextValue = value.trim();
  return nextValue.length > 0 ? nextValue : null;
}

function toDraft(instance: ApiAgentInstance): InstanceDraft {
  return {
    displayName: instance.display_name ?? '',
    githubRepo: instance.workspace?.github_repo ?? '',
    project: instance.workspace?.project ?? '',
  };
}

function sortInstances(instances: ApiAgentInstance[]): ApiAgentInstance[] {
  return [...instances].sort((left, right) => {
    return new Date(right.updated_at).getTime() - new Date(left.updated_at).getTime();
  });
}

function getWorkspaceVisualStatus(instance: ApiAgentInstance): WorkspaceVisualStatus {
  const hasWorkspaceContext = Boolean(
    instance.workspace?.github_repo && instance.workspace?.project,
  );

  if (instance.workspace?.status === 'running') {
    return 'running';
  }
  if (hasWorkspaceContext) {
    return 'ready';
  }
  if (instance.workspace?.status === 'inactive' || !instance.is_active) {
    return 'inactive';
  }
  return 'unconfigured';
}

function getAgentMeta(t: (key: string) => string, agent: ApiAgentKind): AgentMeta {
  switch (agent) {
    case 'sophie':
      return {
        label: t('workspaceSettings.agentSophie'),
        icon: PenTool,
        chipClassName: 'border-violet-200 bg-violet-50 text-violet-700',
        iconClassName: 'text-violet-500',
      };
    case 'marc':
      return {
        label: t('workspaceSettings.agentMarc'),
        icon: Lightbulb,
        chipClassName: 'border-amber-200 bg-amber-50 text-amber-700',
        iconClassName: 'text-amber-500',
      };
    case 'tela':
    default:
      return {
        label: t('workspaceSettings.agentTela'),
        icon: Hammer,
        chipClassName: 'border-sky-200 bg-sky-50 text-sky-700',
        iconClassName: 'text-sky-500',
      };
  }
}

function getStatusMeta(
  t: (key: string) => string,
  status: WorkspaceVisualStatus,
): StatusMeta {
  switch (status) {
    case 'running':
      return {
        icon: Loader2,
        label: t('workspaceSettings.statusRunning'),
        className: 'border-sky-200 bg-sky-50 text-sky-700',
        iconClassName: 'text-sky-500',
      };
    case 'inactive':
      return {
        icon: AlertCircle,
        label: t('workspaceSettings.statusInactive'),
        className: 'border-rose-200 bg-rose-50 text-rose-700',
        iconClassName: 'text-rose-500',
      };
    case 'unconfigured':
      return {
        icon: Settings2,
        label: t('workspaceSettings.statusUnconfigured'),
        className: 'border-amber-200 bg-amber-50 text-amber-700',
        iconClassName: 'text-amber-500',
      };
    case 'ready':
    default:
      return {
        icon: CheckCircle2,
        label: t('workspaceSettings.statusReady'),
        className: 'border-emerald-200 bg-emerald-50 text-emerald-700',
        iconClassName: 'text-emerald-500',
      };
  }
}

function formatExpiry(value: string | null, locale?: string): string {
  if (!value) {
    return '-';
  }

  return new Intl.DateTimeFormat(locale, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  }).format(new Date(value));
}

export default function WorkspaceSettingsPage() {
  const { t } = useTranslation();
  const [instances, setInstances] = useState<ApiAgentInstance[]>([]);
  const [drafts, setDrafts] = useState<Record<string, InstanceDraft>>({});
  const [isLoading, setIsLoading] = useState(true);
  const [savingId, setSavingId] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [agentFilter, setAgentFilter] = useState<AgentFilterValue>('all');
  const [statusFilter, setStatusFilter] = useState<StatusFilterValue>('all');

  useAppLayout({
    title: t('workspaceSettings.title'),
    mainClassName: 'pt-4 pb-6',
  });

  const orderedInstances = useMemo(() => sortInstances(instances), [instances]);

  useEffect(() => {
    void (async () => {
      try {
        const nextInstances = await listAgentInstances();
        setInstances(nextInstances);
        setDrafts(
          Object.fromEntries(nextInstances.map(instance => [instance.id, toDraft(instance)])),
        );
      } catch (error) {
        toast.error(t('workspaceSettings.loadFailed'), {
          description: getErrorDetail(error),
        });
      } finally {
        setIsLoading(false);
      }
    })();
  }, [t]);

  const selectedInstance = useMemo(
    () => instances.find(instance => instance.id === selectedId) ?? null,
    [instances, selectedId],
  );

  const updateDraft = (instanceId: string, key: keyof InstanceDraft, value: string) => {
    setDrafts(current => ({
      ...current,
      [instanceId]: {
        ...(current[instanceId] ?? {
          displayName: '',
          githubRepo: '',
          project: '',
        }),
        [key]: value,
      },
    }));
  };

  const syncInstance = async (instanceId: string) => {
    try {
      const nextInstances = await listAgentInstances();
      const nextInstance = nextInstances.find(instance => instance.id === instanceId);
      if (!nextInstance) {
        return;
      }

      setInstances(current =>
        current.map(instance => (instance.id === instanceId ? nextInstance : instance)),
      );
      setDrafts(current => ({
        ...current,
        [instanceId]: toDraft(nextInstance),
      }));
    } catch {
      // Keep local edits when background resync fails after an error.
    }
  };

  const saveInstance = async (instance: ApiAgentInstance) => {
    const draft = drafts[instance.id] ?? toDraft(instance);
    const nextDisplayName = normalizeText(draft.displayName);
    const nextGithubRepo = normalizeText(draft.githubRepo);
    const nextProject = normalizeText(draft.project);

    const displayNameChanged = nextDisplayName !== instance.display_name;
    const workspaceChanged =
      nextGithubRepo !== (instance.workspace?.github_repo ?? null) ||
      nextProject !== (instance.workspace?.project ?? null);

    if (!displayNameChanged && !workspaceChanged) {
      setSelectedId(null);
      return;
    }

    setSavingId(instance.id);

    try {
      let nextInstance = instance;

      if (displayNameChanged) {
        nextInstance = await updateAgentInstance(instance.id, {
          display_name: nextDisplayName,
        });
      }

      if (workspaceChanged) {
        nextInstance = await updateAgentWorkspace(instance.id, {
          github_repo: nextGithubRepo,
          project: nextProject,
        });
      }

      setInstances(current =>
        current.map(item => (item.id === instance.id ? nextInstance : item)),
      );
      setDrafts(current => ({
        ...current,
        [instance.id]: toDraft(nextInstance),
      }));
      setSelectedId(null);
      toast.success(t('workspaceSettings.saved'));
    } catch (error) {
      toast.error(t('workspaceSettings.saveFailed'), {
        description: getErrorDetail(error),
      });
      await syncInstance(instance.id);
    } finally {
      setSavingId(null);
    }
  };

  const filteredInstances = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();

    return orderedInstances.filter(instance => {
      const draft = drafts[instance.id] ?? toDraft(instance);
      const label =
        normalizeText(draft.displayName) ?? formatAgentLabel(instance.agent, instance.id);
      const workspaceState = getWorkspaceVisualStatus(instance);
      const searchTarget = [
        label,
        draft.githubRepo,
        draft.project,
        instance.workspace?.github_repo ?? '',
        instance.workspace?.project ?? '',
        instance.agent,
      ]
        .join(' ')
        .toLowerCase();

      if (agentFilter !== 'all' && instance.agent !== agentFilter) {
        return false;
      }
      if (statusFilter !== 'all' && workspaceState !== statusFilter) {
        return false;
      }
      if (!query) {
        return true;
      }
      return searchTarget.includes(query);
    });
  }, [agentFilter, drafts, orderedInstances, searchQuery, statusFilter]);

  if (isLoading) {
    return (
      <section className="flex flex-1 items-center justify-center">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="size-4 animate-spin" />
          <span>{t('workspaceSettings.loading')}</span>
        </div>
      </section>
    );
  }

  if (orderedInstances.length === 0) {
    return (
      <section className="px-1 py-10 text-center text-sm text-black/55">
        {t('workspaceSettings.emptyTitle')}
      </section>
    );
  }

  return (
    <>
      <section>
        <div className="flex flex-col gap-3 border-b border-black/8 px-1 py-4 md:flex-row">
          <div className="relative min-w-0 flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-black/35" />
            <Input
              aria-label={t('workspaceSettings.searchLabel')}
              value={searchQuery}
              onChange={event => setSearchQuery(event.target.value)}
              placeholder={t('workspaceSettings.searchPlaceholder')}
              className="h-10 rounded-xl border-black/10 bg-white pl-10 shadow-none"
            />
          </div>

          <Select
            aria-label={t('workspaceSettings.agentFilterLabel')}
            value={agentFilter}
            onChange={event => setAgentFilter(event.target.value as AgentFilterValue)}
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
            onChange={event => setStatusFilter(event.target.value as StatusFilterValue)}
            className="h-10 min-w-[150px] rounded-xl border-black/10 bg-white shadow-none"
          >
            <option value="all">{t('workspaceSettings.filterAllStatuses')}</option>
            <option value="ready">{t('workspaceSettings.statusReady')}</option>
            <option value="running">{t('workspaceSettings.statusRunning')}</option>
            <option value="unconfigured">{t('workspaceSettings.statusUnconfigured')}</option>
            <option value="inactive">{t('workspaceSettings.statusInactive')}</option>
          </Select>
        </div>

        <Table className="min-w-[780px]">
          <TableHeader>
            <TableRow className="bg-black/[0.02] hover:bg-black/[0.02]">
              <TableHead className="h-12 px-5 text-xs font-semibold uppercase tracking-[0.12em] text-black/45">
                {t('workspaceSettings.tableInstance')}
              </TableHead>
              <TableHead className="h-12 text-xs font-semibold uppercase tracking-[0.12em] text-black/45">
                {t('workspaceSettings.tableAgent')}
              </TableHead>
              <TableHead className="h-12 text-xs font-semibold uppercase tracking-[0.12em] text-black/45">
                {t('common.repository')}
              </TableHead>
              <TableHead className="h-12 text-xs font-semibold uppercase tracking-[0.12em] text-black/45">
                {t('common.project')}
              </TableHead>
              <TableHead className="h-12 text-xs font-semibold uppercase tracking-[0.12em] text-black/45">
                {t('workspaceSettings.expiresAt')}
              </TableHead>
              <TableHead className="h-12 px-5 text-xs font-semibold uppercase tracking-[0.12em] text-black/45">
                {t('common.status')}
              </TableHead>
            </TableRow>
          </TableHeader>

          <TableBody>
            {filteredInstances.length === 0 ? (
              <TableRow className="hover:bg-transparent">
                <TableCell colSpan={6} className="px-5 py-12 text-center text-sm text-black/50">
                  {t('workspaceSettings.noResultsTitle')}
                </TableCell>
              </TableRow>
            ) : null}

            {filteredInstances.map(instance => {
              const draft = drafts[instance.id] ?? toDraft(instance);
              const label =
                normalizeText(draft.displayName) ??
                formatAgentLabel(instance.agent, instance.id);
              const agentMeta = getAgentMeta(t, instance.agent);
              const status = getWorkspaceVisualStatus(instance);
              const statusMeta = getStatusMeta(t, status);
              const AgentIcon = agentMeta.icon;
              const StatusIcon = statusMeta.icon;

              return (
                <TableRow
                  key={instance.id}
                  tabIndex={0}
                  className="cursor-pointer border-black/8 hover:bg-[#fafaf8] focus-visible:bg-[#fafaf8] focus-visible:outline-none"
                  onClick={() => setSelectedId(instance.id)}
                  onKeyDown={event => {
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault();
                      setSelectedId(instance.id);
                    }
                  }}
                >
                  <TableCell className="px-5 py-4">
                    <div className="min-w-0">
                      <div className="truncate text-sm font-semibold text-black/85">
                        {label}
                      </div>
                    </div>
                  </TableCell>

                  <TableCell className="py-4">
                    <div
                      className={cn(
                        'inline-flex items-center gap-2 rounded-full border px-3 py-1 text-sm font-medium',
                        agentMeta.chipClassName,
                      )}
                    >
                      <AgentIcon className={cn('size-4', agentMeta.iconClassName)} />
                      <span>{agentMeta.label}</span>
                    </div>
                  </TableCell>

                  <TableCell className="py-4 font-mono text-sm text-black/70">
                    {instance.workspace?.github_repo ?? t('workspaceSettings.unconfigured')}
                  </TableCell>

                  <TableCell className="py-4 text-sm text-black/70">
                    {instance.workspace?.project ?? t('workspaceSettings.unconfigured')}
                  </TableCell>

                  <TableCell className="py-4 text-sm text-black/70">
                    {formatExpiry(instance.expires_at)}
                  </TableCell>

                  <TableCell className="px-5 py-4">
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
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </section>

      <Dialog open={selectedInstance !== null} onOpenChange={open => !open && setSelectedId(null)}>
        {selectedInstance ? (
          <DialogContent className="gap-0 overflow-hidden border-black/10 p-0 sm:max-w-2xl">
            {(() => {
              const draft = drafts[selectedInstance.id] ?? toDraft(selectedInstance);
              const normalizedDisplayName = normalizeText(draft.displayName);
              const normalizedGithubRepo = normalizeText(draft.githubRepo);
              const normalizedProject = normalizeText(draft.project);
              const isDirty =
                normalizedDisplayName !== selectedInstance.display_name ||
                normalizedGithubRepo !== (selectedInstance.workspace?.github_repo ?? null) ||
                normalizedProject !== (selectedInstance.workspace?.project ?? null);
              const isSaving = savingId === selectedInstance.id;
              const agentMeta = getAgentMeta(t, selectedInstance.agent);
              const status = getWorkspaceVisualStatus(selectedInstance);
              const statusMeta = getStatusMeta(t, status);
              const AgentIcon = agentMeta.icon;
              const StatusIcon = statusMeta.icon;
              const label =
                normalizedDisplayName ??
                formatAgentLabel(selectedInstance.agent, selectedInstance.id);

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
                        htmlFor={`display-name-${selectedInstance.id}`}
                        className="text-sm font-medium text-black/80"
                      >
                        {t('workspaceSettings.nickname')}
                      </label>
                      <Input
                        id={`display-name-${selectedInstance.id}`}
                        value={draft.displayName}
                        onChange={event =>
                          updateDraft(selectedInstance.id, 'displayName', event.target.value)
                        }
                        placeholder={t('workspaceSettings.nicknamePlaceholder')}
                        className="h-11 rounded-xl border-black/10 shadow-none"
                      />
                    </div>

                    <div className="space-y-1.5">
                      <label
                        htmlFor={`github-repo-${selectedInstance.id}`}
                        className="text-sm font-medium text-black/80"
                      >
                        {t('workspaceSettings.repository')}
                      </label>
                      <Input
                        id={`github-repo-${selectedInstance.id}`}
                        value={draft.githubRepo}
                        onChange={event =>
                          updateDraft(selectedInstance.id, 'githubRepo', event.target.value)
                        }
                        placeholder="owner/repository"
                        className="h-11 rounded-xl border-black/10 shadow-none"
                      />
                    </div>

                    <div className="space-y-1.5">
                      <label
                        htmlFor={`project-${selectedInstance.id}`}
                        className="text-sm font-medium text-black/80"
                      >
                        {t('workspaceSettings.project')}
                      </label>
                      <Input
                        id={`project-${selectedInstance.id}`}
                        value={draft.project}
                        onChange={event =>
                          updateDraft(selectedInstance.id, 'project', event.target.value)
                        }
                        placeholder={t('workspaceSettings.projectPlaceholder')}
                        className="h-11 rounded-xl border-black/10 shadow-none"
                      />
                    </div>

                    <div className="space-y-1.5 sm:col-span-2">
                      <label className="text-sm font-medium text-black/80">
                        {t('workspaceSettings.expiresAt')}
                      </label>
                      <div className="h-11 rounded-xl border border-black/10 bg-black/[0.02] px-3 py-2 text-sm text-black/65">
                        {formatExpiry(selectedInstance.expires_at)}
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
                      disabled={savingId !== null || !isDirty}
                      className="rounded-xl bg-black text-white hover:bg-black/90"
                      onClick={() => void saveInstance(selectedInstance)}
                    >
                      {isSaving ? (
                        <>
                          <Loader2 className="size-4 animate-spin" />
                          {t('workspaceSettings.saving')}
                        </>
                      ) : (
                        <>
                          <Save className="size-4" />
                          {t('workspaceSettings.save')}
                        </>
                      )}
                    </Button>
                  </DialogFooter>
                </>
              );
            })()}
          </DialogContent>
        ) : null}
      </Dialog>
    </>
  );
}
