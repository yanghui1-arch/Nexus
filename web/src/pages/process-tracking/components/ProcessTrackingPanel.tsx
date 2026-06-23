import { useEffect, useRef, useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { ChevronsUpDown, SendHorizontal } from 'lucide-react';
import { Link } from 'react-router-dom';
import type { ApiTaskExecutionEvent } from '@/api/types';
import { ExecutionTimeline } from '@/pages/process-tracking/components/ExecutionTimeline';
import type {
  WorkspaceAgentOption,
  WorkspaceConsultMessageView,
  WorkspaceTaskView,
} from '@/lib/workspace-task-view';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { CardTitle } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Select } from '@/components/ui/select';
import { cn } from '@/lib/utils';
import { STATUS_META, timeAgo } from '@/lib/workspace-task-view';

type ProcessTrackingPanelProps = {
  agents: WorkspaceAgentOption[];
  tasksForAgent: WorkspaceTaskView[];
  messages: WorkspaceConsultMessageView[];
  timelineEvents: ApiTaskExecutionEvent[];
  isLoadingTimeline: boolean;
  selectedAgentId: string;
  selectedTaskId: string;
  selectedTask?: WorkspaceTaskView;
  input: string;
  isLoadingAgents: boolean;
  isSending: boolean;
  onSelectedAgentChange: (agentId: string) => void;
  onSelectedTaskChange: (taskId: string) => void;
  onInputChange: (next: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
};

function detailValue(value: string | null | undefined): string {
  return value || '-';
}

export function ProcessTrackingPanel({
  agents,
  tasksForAgent,
  messages,
  timelineEvents,
  isLoadingTimeline,
  selectedAgentId,
  selectedTaskId,
  selectedTask,
  input,
  isLoadingAgents,
  isSending,
  onSelectedAgentChange,
  onSelectedTaskChange,
  onInputChange,
  onSubmit,
}: ProcessTrackingPanelProps) {
  const { t } = useTranslation();
  const [isTaskPickerOpen, setIsTaskPickerOpen] = useState(false);
  const bottomAnchorRef = useRef<HTMLDivElement | null>(null);

  const hasAgents = agents.length > 0;
  const hasTasks = tasksForAgent.length > 0;
  const canConsult = selectedTask?.status === 'running';
  const canSubmit = Boolean(selectedTask) && canConsult && input.trim().length > 0 && !isSending;

  useEffect(() => {
    if (messages.length === 0 && !isSending) return;
    const id = window.requestAnimationFrame(() => {
      bottomAnchorRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
    });
    return () => window.cancelAnimationFrame(id);
  }, [messages.length, selectedTaskId, isSending]);

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden rounded-xl border bg-card text-card-foreground shadow-sm">
      <div className="shrink-0 border-b px-6 py-5">
        <div className="grid grid-cols-2 items-start gap-6">
          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <label htmlFor="tracking-agent" className="text-sm font-medium">
                {t('common.agent')}
              </label>
              <Select id="tracking-agent" value={selectedAgentId} onChange={e => onSelectedAgentChange(e.target.value)} disabled={!hasAgents || isSending}>
                {isLoadingAgents && <option value="">{t('processTracking.loadingAgents')}</option>}
                {agents.map(agent => (
                  <option key={agent.id} value={agent.id} selected={agent.id === selectedAgentId}>
                    {agent.label} - {agent.subtitle}
                  </option>
                ))}
              </Select>
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium">{t('common.task')}</label>
              <Dialog open={isTaskPickerOpen} onOpenChange={setIsTaskPickerOpen}>
                <DialogTrigger asChild>
                  <Button type="button" variant="outline" className="w-full justify-between gap-3 px-3 font-normal" disabled={!hasTasks || isSending}>
                    <span className="truncate text-left">
                      {selectedTask ? selectedTask.question : selectedAgentId ? t('processTracking.chooseTask') : t('processTracking.selectAgentFirst')}
                    </span>
                    <ChevronsUpDown className="size-4 shrink-0 text-muted-foreground" />
                  </Button>
                </DialogTrigger>

                <DialogContent className="max-w-lg">
                  <DialogHeader>
                    <DialogTitle>{t('processTracking.selectTaskTitle')}</DialogTitle>
                    <DialogDescription>{t('processTracking.selectTaskDescription')}</DialogDescription>
                  </DialogHeader>
                  <ScrollArea className="max-h-[420px] -mx-1">
                    <div className="flex flex-col gap-1 px-1">
                      {tasksForAgent.map(task => {
                        const isSelected = task.id === selectedTaskId;
                        return (
                          <button
                            key={task.id}
                            type="button"
                            onClick={() => {
                              onSelectedTaskChange(task.id);
                              setIsTaskPickerOpen(false);
                            }}
                            className={cn('w-full rounded-lg border px-4 py-3 text-left transition-colors', isSelected ? 'border-primary bg-primary/5' : 'border-transparent hover:border-border hover:bg-muted/40')}
                          >
                            <div className="flex items-start justify-between gap-3">
                              <p className="line-clamp-2 text-sm font-medium leading-snug">{task.question}</p>
                              <Badge variant={STATUS_META[task.status].badgeVariant} className="mt-0.5 shrink-0">
                                {t(`status.${task.status}`)}
                              </Badge>
                            </div>
                            <div className="mt-1.5 flex items-center gap-2 text-xs text-muted-foreground">
                              <span className="truncate">{detailValue(task.repo)}</span>
                              <span className="shrink-0">·</span>
                              <span className="shrink-0">{task.agentLabel}</span>
                              <span className="ml-auto shrink-0">{timeAgo(task.updatedAt)}</span>
                            </div>
                          </button>
                        );
                      })}
                    </div>
                  </ScrollArea>
                </DialogContent>
              </Dialog>

              <p className="text-xs text-muted-foreground">
                {hasTasks ? t('processTracking.trackableTasksAvailable', { count: tasksForAgent.length }) : t('processTracking.noTrackableTasks')}
              </p>
            </div>
          </div>

          <div className="rounded-xl bg-muted/40 p-4">
            <div className="flex items-start justify-between gap-3">
              <p className="text-xs font-medium uppercase tracking-widest text-muted-foreground">{t('processTracking.selectedTask')}</p>
              {selectedTask ? <Badge variant={STATUS_META[selectedTask.status].badgeVariant}>{t(`status.${selectedTask.status}`)}</Badge> : null}
            </div>

            <CardTitle className="mt-2 line-clamp-2 text-sm font-semibold leading-snug" title={selectedTask?.question}>
              {selectedTask?.question ?? <span className="font-normal text-muted-foreground">{t('processTracking.noTaskSelected')}</span>}
            </CardTitle>

            <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3">
              {[
                [t('common.agent'), selectedTask?.agentLabel],
                [t('common.repository'), selectedTask?.repo],
                [t('common.project'), selectedTask?.project],
                [t('common.updated'), selectedTask ? timeAgo(selectedTask.updatedAt) : null],
              ].map(([label, value]) => (
                <div key={label}>
                  <dt className="text-xs text-muted-foreground">{label}</dt>
                  <dd className="mt-0.5 truncate text-sm" title={value ?? '-'}>{detailValue(value)}</dd>
                </div>
              ))}
            </dl>

            {selectedTask?.error ? <div className="mt-4 rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">{selectedTask.error}</div> : null}

            {selectedTask?.status === 'failed' ? (
              <Button asChild size="sm" variant="destructive" className="mt-4">
                <Link to={`/task/${selectedTask.id}`}>{t('processTracking.openRecovery')}</Link>
              </Button>
            ) : null}
          </div>
        </div>
      </div>

      <div className="grid min-h-0 flex-1 grid-cols-[minmax(0,1fr)_360px] gap-4 px-6 py-5">
        <div className="flex min-h-0 flex-col gap-4">
          <div className="shrink-0">
          <p className="text-xs font-medium uppercase tracking-widest text-muted-foreground">{t('processTracking.chat')}</p>
          <p className="mt-1 text-sm text-muted-foreground">
            {selectedTask?.status === 'failed'
              ? t('processTracking.chatHintFailed')
              : selectedTask
                ? t('processTracking.chatHintReady')
                : t('processTracking.chatHintEmpty')}
          </p>
        </div>

        <div className="min-h-0 flex-1">
          <ScrollArea className="h-full">
            <div className="flex flex-col gap-2 pb-2 pr-1">
              {messages.map(message => (
                <article key={message.id} className={cn('max-w-[88%] rounded-lg px-3 py-2 text-sm', 'transition-all duration-300 ease-out', 'motion-safe:animate-in motion-safe:fade-in-0 motion-safe:slide-in-from-bottom-2', message.role === 'user' ? 'ml-auto bg-primary text-primary-foreground' : 'bg-muted')}>
                  <p className="text-xs font-semibold opacity-70">{message.role === 'user' ? t('processTracking.you') : t('common.agent')}</p>
                  <p className="mt-1 break-words leading-relaxed">{message.text}</p>
                  <p className="mt-1 text-[11px] opacity-60">{timeAgo(message.time)}</p>
                </article>
              ))}

              {isSending && (
                <article className={cn('max-w-[88%] rounded-lg bg-muted px-3 py-2 text-sm', 'motion-safe:animate-in motion-safe:fade-in-0 motion-safe:slide-in-from-bottom-2', 'transition-all duration-300 ease-out')} aria-label={t('processTracking.agentTyping')}>
                  <p className="text-xs font-semibold opacity-70">{t('common.agent')}</p>
                  <div className="mb-1 mt-2 flex items-center gap-1.5">
                    <span className="size-2 animate-bounce rounded-full bg-current opacity-60" style={{ animationDelay: '0ms', animationDuration: '1s' }} />
                    <span className="size-2 animate-bounce rounded-full bg-current opacity-60" style={{ animationDelay: '160ms', animationDuration: '1s' }} />
                    <span className="size-2 animate-bounce rounded-full bg-current opacity-60" style={{ animationDelay: '320ms', animationDuration: '1s' }} />
                  </div>
                </article>
              )}

              <div ref={bottomAnchorRef} />
            </div>
          </ScrollArea>
        </div>

        <form onSubmit={onSubmit} className="shrink-0 flex flex-col gap-2">
          <div className="flex items-center gap-2">
            <Input value={input} onChange={e => onInputChange(e.target.value)} placeholder={canConsult ? t('processTracking.inputPlaceholderReady') : t('processTracking.inputPlaceholderEmpty')} disabled={!canConsult || isSending} />
            <Button type="submit" size="icon" aria-label={t('processTracking.consultTask')} disabled={!canSubmit}>
              <SendHorizontal />
            </Button>
          </div>
        </form>
        </div>

        <ExecutionTimeline events={timelineEvents} isLoading={isLoadingTimeline} />
      </div>
    </div>
  );
}
