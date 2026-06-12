import type { WorkspaceTaskView } from '@/lib/workspace-task-view';

const TIMELINE_STEPS = [
  { key: 'createdAt', label: 'Created' },
  { key: 'startedAt', label: 'Started' },
  { key: 'updatedAt', label: 'Updated' },
  { key: 'finishedAt', label: 'Finished' },
] as const;

function formatTime(value: string | null | undefined): string {
  if (!value) return '-';
  return new Intl.DateTimeFormat('en', {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  }).format(new Date(value));
}

export function ProcessTrackingTimeline({ selectedTask }: { selectedTask?: WorkspaceTaskView }) {
  if (!selectedTask) {
    return (
      <section aria-label="Process timeline" className="rounded-xl border bg-muted/20 p-4 text-sm text-muted-foreground">
        No timeline events yet.
      </section>
    );
  }

  return (
    <section aria-label="Process timeline" className="rounded-xl border bg-muted/20 p-4">
      <h3 className="text-sm font-semibold">Timeline</h3>
      <ol className="mt-3 space-y-3">
        {TIMELINE_STEPS.map(step => {
          const value = selectedTask[step.key];
          return (
            <li key={step.key} className="flex gap-3 text-sm">
              <span className="mt-1 size-2 rounded-full bg-primary" />
              <div>
                <p className="font-medium">{step.label}</p>
                <time className="text-muted-foreground" dateTime={value ?? undefined}>{formatTime(value)}</time>
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
