import { useTranslation } from 'react-i18next';
import type { ApiAgentInstance } from '@/api/types';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { cn } from '@/lib/utils';
import type { DraftMap } from '../types';
import {
  formatExpiry,
  getAgentMeta,
  getInstanceLabel,
  getStatusMeta,
  getWorkspaceVisualStatus,
  toDraft,
} from '../utils';

type WorkspaceSettingsTableProps = {
  instances: ApiAgentInstance[];
  drafts: DraftMap;
  onSelect: (instanceId: string) => void;
};

export function WorkspaceSettingsTable({
  instances,
  drafts,
  onSelect,
}: WorkspaceSettingsTableProps) {
  const { t } = useTranslation();

  return (
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
        {instances.length === 0 ? (
          <TableRow className="hover:bg-transparent">
            <TableCell colSpan={6} className="px-5 py-12 text-center text-sm text-black/50">
              {t('workspaceSettings.noResultsTitle')}
            </TableCell>
          </TableRow>
        ) : null}

        {instances.map(instance => {
          const draft = drafts[instance.id] ?? toDraft(instance);
          const label = getInstanceLabel(instance, draft);
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
              onClick={() => onSelect(instance.id)}
              onKeyDown={event => {
                if (event.key === 'Enter' || event.key === ' ') {
                  event.preventDefault();
                  onSelect(instance.id);
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
  );
}
