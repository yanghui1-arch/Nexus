import type { ApiAgentInstance } from '@/api/types';

export type WorkspaceSettingsInstance = ApiAgentInstance;

export type WorkspaceSettingsFilter = {
  search: string;
  agent: string;
  status: string;
};
