import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import {
  listAgentInstances,
  updateAgentInstance,
  updateAgentWorkspace,
} from '@/api/agentInstances';
import { getErrorDetail } from '@/api/client';
import type { ApiAgentInstance } from '@/api/types';
import type {
  AgentFilterValue,
  DraftMap,
  InstanceDraft,
  StatusFilterValue,
} from '../types';
import {
  getInstanceLabel,
  getWorkspaceVisualStatus,
  normalizeText,
  sortInstances,
  toDraft,
} from '../utils';

export function useWorkspaceSettings() {
  const { t } = useTranslation();
  const [instances, setInstances] = useState<ApiAgentInstance[]>([]);
  const [drafts, setDrafts] = useState<DraftMap>({});
  const [isLoading, setIsLoading] = useState(true);
  const [savingId, setSavingId] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [agentFilter, setAgentFilter] = useState<AgentFilterValue>('all');
  const [statusFilter, setStatusFilter] = useState<StatusFilterValue>('all');

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

  const selectedDraft = useMemo(() => {
    if (!selectedInstance) {
      return null;
    }
    return drafts[selectedInstance.id] ?? toDraft(selectedInstance);
  }, [drafts, selectedInstance]);

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

  const updateSelectedDraftField = (key: keyof InstanceDraft, value: string) => {
    if (!selectedInstance) {
      return;
    }
    updateDraft(selectedInstance.id, key, value);
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

  const saveSelectedInstance = async () => {
    if (!selectedInstance) {
      return;
    }
    await saveInstance(selectedInstance);
  };

  const filteredInstances = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();

    return orderedInstances.filter(instance => {
      const draft = drafts[instance.id] ?? toDraft(instance);
      const label = getInstanceLabel(instance, draft);
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

  const isSelectedDirty = useMemo(() => {
    if (!selectedInstance || !selectedDraft) {
      return false;
    }

    const normalizedDisplayName = normalizeText(selectedDraft.displayName);
    const normalizedGithubRepo = normalizeText(selectedDraft.githubRepo);
    const normalizedProject = normalizeText(selectedDraft.project);

    return (
      normalizedDisplayName !== selectedInstance.display_name ||
      normalizedGithubRepo !== (selectedInstance.workspace?.github_repo ?? null) ||
      normalizedProject !== (selectedInstance.workspace?.project ?? null)
    );
  }, [selectedDraft, selectedInstance]);

  return {
    drafts,
    filteredInstances,
    isLoading,
    hasInstances: orderedInstances.length > 0,
    selectedInstance,
    selectedDraft,
    isSelectedDirty,
    isSelectedSaving: selectedInstance ? savingId === selectedInstance.id : false,
    searchQuery,
    agentFilter,
    statusFilter,
    openInstance: (instanceId: string) => setSelectedId(instanceId),
    closeDialog: () => setSelectedId(null),
    updateSearchQuery: (value: string) => setSearchQuery(value),
    updateAgentFilter: (value: AgentFilterValue) => setAgentFilter(value),
    updateStatusFilter: (value: StatusFilterValue) => setStatusFilter(value),
    updateSelectedDraftField,
    saveSelectedInstance,
  };
}
