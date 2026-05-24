import type { ApiAgentKind } from '@/api/types';

export type InstanceDraft = {
  displayName: string;
  githubRepo: string;
  project: string;
};

export type DraftMap = Record<string, InstanceDraft>;

export type WorkspaceVisualStatus = 'ready' | 'running' | 'inactive' | 'unconfigured';

export type AgentFilterValue = 'all' | ApiAgentKind;

export type StatusFilterValue = 'all' | WorkspaceVisualStatus;
