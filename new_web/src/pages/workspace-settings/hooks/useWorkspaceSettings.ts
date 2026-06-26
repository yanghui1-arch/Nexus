import { startTransition, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { getErrorDetail } from '@/api/client';
import {
  listAgentInstances,
  updateAgentInstance,
} from '@/api/agentInstances';
import type { ApiAgentInstance } from '@/api/types';
import type { WorkspaceSettingsFilter } from '../types';

const EMPTY_FILTER: WorkspaceSettingsFilter = {
  search: '',
  agent: 'all',
  status: 'all',
};

export type WorkspaceSettingsData = {
  instances: ApiAgentInstance[];
  filter: WorkspaceSettingsFilter;
  setFilter: (next: WorkspaceSettingsFilter) => void;
  filteredInstances: ApiAgentInstance[];
  isLoading: boolean;
  isSaving: boolean;
  saveInstance: (instanceId: string, displayName: string | null, githubRepo: string | null, project: string | null) => Promise<void>;
  reload: () => Promise<void>;
};

export function useWorkspaceSettings(): WorkspaceSettingsData {
  const { t } = useTranslation();
  const [instances, setInstances] = useState<ApiAgentInstance[]>([]);
  const [filter, setFilter] = useState<WorkspaceSettingsFilter>(EMPTY_FILTER);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);

  const reload = async () => {
    try {
      const next = await listAgentInstances({});
      startTransition(() => {
        setInstances(next);
        setIsLoading(false);
      });
    } catch (error) {
      toast.error(t('workspaceSettings.loadFailed'), {
        description: getErrorDetail(error),
      });
      startTransition(() => {
        setIsLoading(false);
      });
    }
  };

  useEffect(() => {
    void reload();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const filteredInstances = useMemo(() => {
    const tSimple = (key: string) => t(key as never) as string;
    return instances.filter(instance => {
      if (!matchesSearch(instance, filter.search)) return false;
      if (!matchesAgentFilter(instance, filter.agent)) return false;
      if (!matchesStatusFilter(instance, filter.status, tSimple)) return false;
      return true;
    });
  }, [instances, filter, t]);

  const saveInstance = async (
    instanceId: string,
    displayName: string | null,
    _githubRepo: string | null,
    _project: string | null,
  ) => {
    setIsSaving(true);
    try {
      await updateAgentInstance(instanceId, { display_name: displayName });
      await reload();
      toast.success(t('workspaceSettings.saved'));
    } catch (error) {
      toast.error(t('workspaceSettings.saveFailed'), {
        description: getErrorDetail(error),
      });
    } finally {
      setIsSaving(false);
    }
  };

  return {
    instances,
    filter,
    setFilter,
    filteredInstances,
    isLoading,
    isSaving,
    saveInstance,
    reload,
  };
}

function matchesSearch(instance: ApiAgentInstance, search: string): boolean {
  if (!search.trim()) return true;
  const q = search.toLowerCase();
  const displayName = instance.display_name?.toLowerCase() ?? '';
  const repo = instance.workspace?.github_repo?.toLowerCase() ?? '';
  const project = instance.workspace?.project?.toLowerCase() ?? '';
  const clientId = instance.client_id.toLowerCase();
  return (
    displayName.includes(q) ||
    repo.includes(q) ||
    project.includes(q) ||
    clientId.includes(q)
  );
}

function matchesAgentFilter(instance: ApiAgentInstance, agent: string): boolean {
  if (!agent || agent === 'all') return true;
  return instance.agent === agent;
}

function getStatusLabel(instance: ApiAgentInstance, t: (key: string) => string): string {
  if (!instance.is_active) {
    return t('workspaceSettings.statusInactive');
  }
  if (!instance.workspace?.github_repo || !instance.workspace?.project) {
    return t('workspaceSettings.statusUnconfigured');
  }
  const wsStatus = instance.workspace?.status;
  if (wsStatus === 'running') {
    return t('workspaceSettings.statusRunning');
  }
  return t('workspaceSettings.statusIdle');
}

function matchesStatusFilter(instance: ApiAgentInstance, status: string, t: (key: string) => string): boolean {
  if (!status || status === 'all') return true;
  const label = getStatusLabel(instance, t);
  return label === status;
}
