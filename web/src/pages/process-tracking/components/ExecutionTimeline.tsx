import { AlertCircle, CheckCircle2, Hammer, Save, Sparkles } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import type { ApiTaskMessage } from '@/api/types';
import { ScrollArea } from '@/components/ui/scroll-area';
import { cn } from '@/lib/utils';
import { timeAgo } from '@/lib/workspace-task-view';

type ExecutionTimelineProps = {
  events: ApiTaskMessage[];
  isLoading: boolean;
};

const PROMINENT_EVENTS = new Set(['SAVE_CHECKPOINT', 'COMPLETED', 'FAILED']);
const MUTED_EVENTS = new Set(['START', 'PROCESS']);

function isToolEvent(event: ApiTaskMessage): boolean {
  const type = event.status.toUpperCase();
  return type.includes('TOOL') || Array.isArray(event.data?.tools) || Array.isArray(event.data?.tool_names);
}

function isProminent(event: ApiTaskMessage): boolean {
  return PROMINENT_EVENTS.has(event.status.toUpperCase()) || isToolEvent(event);
}

function eventIcon(event: ApiTaskMessage) {
  const type = event.status.toUpperCase();
  if (type === 'FAILED') return AlertCircle;
  if (type === 'COMPLETED') return CheckCircle2;
  if (type === 'SAVE_CHECKPOINT') return Save;
  if (isToolEvent(event)) return Hammer;
  return Sparkles;
}

function eventTitle(event: ApiTaskMessage): string {
  const tools = event.data?.tools ?? event.data?.tool_names;
  if (Array.isArray(tools) && tools.length > 0) {
    return `TOOL · ${tools.join(', ')}`;
  }
  return event.status;
}

export function ExecutionTimeline({ events, isLoading }: ExecutionTimelineProps) {
  const { t } = useTranslation();
  const visibleEvents = events.filter(event => isProminent(event) || !MUTED_EVENTS.has(event.status.toUpperCase()));
  const mutedCount = events.length - visibleEvents.length;

  return (
    <section className="flex min-h-0 flex-1 flex-col rounded-xl border bg-background/60">
      <div className="shrink-0 border-b px-4 py-3">
        <p className="text-xs font-medium uppercase tracking-widest text-muted-foreground">{t('processTracking.timeline')}</p>
        <p className="mt-1 text-sm text-muted-foreground">
          {mutedCount > 0 ? t('processTracking.timelineMuted', { count: mutedCount }) : t('processTracking.timelineHint')}
        </p>
      </div>

      <ScrollArea className="min-h-0 flex-1">
        <div className="space-y-3 p-4">
          {isLoading ? <p className="text-sm text-muted-foreground">{t('processTracking.timelineLoading')}</p> : null}
          {!isLoading && visibleEvents.length === 0 ? (
            <p className="text-sm text-muted-foreground">{t('processTracking.timelineEmpty')}</p>
          ) : null}

          {visibleEvents.map((event, index) => {
            const Icon = eventIcon(event);
            const prominent = isProminent(event);
            const failed = event.status.toUpperCase() === 'FAILED';
            return (
              <article key={`${event.timestamp}-${index}`} className="relative pl-8">
                <span className="absolute left-3 top-7 h-[calc(100%+0.75rem)] w-px bg-border last:hidden" />
                <span className={cn('absolute left-0 top-1 flex size-6 items-center justify-center rounded-full border bg-background', prominent ? 'border-primary text-primary' : 'text-muted-foreground', failed && 'border-destructive text-destructive')}>
                  <Icon className="size-3.5" />
                </span>
                <div className={cn('rounded-lg border px-3 py-2', prominent ? 'bg-card shadow-sm' : 'bg-muted/30 opacity-75', failed && 'border-destructive/40 bg-destructive/10')}>
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-xs font-semibold uppercase tracking-wide">{eventTitle(event)}</p>
                    <time className="shrink-0 text-[11px] text-muted-foreground">{timeAgo(event.timestamp)}</time>
                  </div>
                  {event.description ? <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{event.description}</p> : null}
                </div>
              </article>
            );
          })}
        </div>
      </ScrollArea>
    </section>
  );
}
