import type { TFunction } from 'i18next';
import type { ApiAgentInstance } from '@/api/types';

export function getAgentLabel(agent: string, t: TFunction): string {
  switch (agent) {
    case 'sophie': return t('workspaceSettings.agentSophie');
    case 'tela': return t('workspaceSettings.agentTela');
    case 'jules': return t('workspaceSettings.agentJules');
    case 'marc': return t('workspaceSettings.agentMarc');
    case 'assistant': return t('workspaceSettings.agentAssistant');
    default: return agent;
  }
}

export function getStatusLabel(
  instance: ApiAgentInstance,
  t: TFunction,
): string {
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

export function isReady(instance: ApiAgentInstance): boolean {
  return (
    instance.is_active &&
    Boolean(instance.workspace?.github_repo && instance.workspace?.project)
  );
}

export function matchesSearch(
  instance: ApiAgentInstance,
  search: string,
): boolean {
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

export function matchesAgentFilter(
  instance: ApiAgentInstance,
  agent: string,
): boolean {
  if (!agent || agent === 'all') return true;
  return instance.agent === agent;
}

export function matchesStatusFilter(
  instance: ApiAgentInstance,
  status: string,
  t: TFunction,
): boolean {
  if (!status || status === 'all') return true;
  const label = getStatusLabel(instance, t);
  return label === status;
}
