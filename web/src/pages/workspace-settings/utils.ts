import {
  AlertCircle,
  CheckCircle2,
  Coffee,
  Bot,
  Hammer,
  Lightbulb,
  Loader2,
  PenTool,
  Settings2,
  type LucideIcon,
} from 'lucide-react';
import type { ApiAgentInstance, ApiAgentKind } from '@/api/types';
import { formatAgentLabel } from '@/lib/workspace-task-view';
import type { InstanceDraft, WorkspaceVisualStatus } from './types';

type Translator = (key: string) => string;

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

export function normalizeText(value: string): string | null {
  const nextValue = value.trim();
  return nextValue.length > 0 ? nextValue : null;
}

export function toDraft(instance: ApiAgentInstance): InstanceDraft {
  return {
    displayName: instance.display_name ?? '',
    githubRepo: instance.workspace?.github_repo ?? '',
    project: instance.workspace?.project ?? '',
  };
}

export function sortInstances(instances: ApiAgentInstance[]): ApiAgentInstance[] {
  return [...instances].sort((left, right) => {
    return new Date(right.updated_at).getTime() - new Date(left.updated_at).getTime();
  });
}

export function getInstanceLabel(
  instance: ApiAgentInstance,
  draft: InstanceDraft = toDraft(instance),
): string {
  return normalizeText(draft.displayName) ?? formatAgentLabel(instance.agent, instance.id);
}

export function getWorkspaceVisualStatus(instance: ApiAgentInstance): WorkspaceVisualStatus {
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

export function getAgentMeta(t: Translator, agent: ApiAgentKind): AgentMeta {
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
    case 'jules':
      return {
        label: t('workspaceSettings.agentJules'),
        icon: Coffee,
        chipClassName: 'border-emerald-200 bg-emerald-50 text-emerald-700',
        iconClassName: 'text-emerald-500',
      };
    case 'assistant':
      return {
        label: t('workspaceSettings.agentAssistant'),
        icon: Bot,
        chipClassName: 'border-cyan-200 bg-cyan-50 text-cyan-700',
        iconClassName: 'text-cyan-500',
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

export function getStatusMeta(
  t: Translator,
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

export function formatExpiry(value: string | null, locale?: string): string {
  if (!value) {
    return '-';
  }

  return new Intl.DateTimeFormat(locale, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  }).format(new Date(value));
}
