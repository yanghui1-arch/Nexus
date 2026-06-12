import { Activity, Bot, CircleDollarSign, TimerReset } from 'lucide-react';
import type { WorkspaceTaskView } from '@/lib/workspace-task-view';
import { timeAgo } from '@/lib/workspace-task-view';

function durationLabel(task?: WorkspaceTaskView): string {
  if (!task?.startedAt) return '-';
  const end = task.finishedAt ? new Date(task.finishedAt).getTime() : Date.now();
  const seconds = Math.max(1, Math.round((end - new Date(task.startedAt).getTime()) / 1000));
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
  return `${Math.round(seconds / 3600)}h`;
}

export function ProcessTrackingMetricsCards({ selectedTask }: { selectedTask?: WorkspaceTaskView }) {
  const cards = [
    { label: 'Status', value: selectedTask?.status ?? '-', helper: selectedTask ? timeAgo(selectedTask.updatedAt) : 'No task selected', Icon: Activity },
    { label: 'Model', value: selectedTask?.modelName ?? 'Model unknown', helper: selectedTask?.agentLabel ?? '-', Icon: Bot },
    { label: 'Tokens', value: selectedTask?.tokenCount == null ? 'Token unknown' : selectedTask.tokenCount.toLocaleString(), helper: 'Total usage', Icon: CircleDollarSign },
    { label: 'Duration', value: durationLabel(selectedTask), helper: selectedTask?.startedAt ? 'Since start' : 'Not started', Icon: TimerReset },
  ];

  return (
    <section aria-label="Process metrics" className="grid gap-3 md:grid-cols-4">
      {cards.map(({ label, value, helper, Icon }) => (
        <div key={label} className="rounded-xl border bg-muted/20 p-3">
          <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
            <span>{label}</span>
            <Icon className="size-4" />
          </div>
          <p className="mt-2 truncate text-lg font-semibold" title={value}>{value}</p>
          <p className="mt-1 truncate text-xs text-muted-foreground">{helper}</p>
        </div>
      ))}
    </section>
  );
}
