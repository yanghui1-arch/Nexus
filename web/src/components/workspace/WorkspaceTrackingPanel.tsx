import type { FormEvent } from 'react';
import { SendHorizontal } from 'lucide-react';
import type {
  AgentProfile,
  WorkspaceMessage,
  WorkspaceTask,
} from '@/data/workspaceMockData';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
} from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Select } from '@/components/ui/select';
import { cn } from '@/lib/utils';
import { STATUS_META, timeAgo } from './workspace-utils';

type WorkspaceTrackingPanelProps = {
  agents: AgentProfile[];
  messages: WorkspaceMessage[];
  selectedAgentId: string;
  selectedTask?: WorkspaceTask;
  tasksForAgent: WorkspaceTask[];
  repoNameById: (repoId: string) => string;
  input: string;
  onSelectedAgentChange: (agentId: string) => void;
  onInputChange: (next: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onSendQuickPrompt: (text: string) => void;
};

const QUICK_PROMPTS = [
  'ETA for current task?',
  'What is the blocker?',
  'Send latest checkpoint.',
];

function roleLabel(role: WorkspaceMessage['role']): string {
  if (role === 'user') return 'You';
  if (role === 'system') return 'System';
  return 'Agent';
}

export function WorkspaceTrackingPanel({
  agents,
  messages,
  selectedAgentId,
  selectedTask,
  tasksForAgent,
  repoNameById,
  input,
  onSelectedAgentChange,
  onInputChange,
  onSubmit,
  onSendQuickPrompt,
}: WorkspaceTrackingPanelProps) {
  return (
    <Card className="flex h-full min-h-0 flex-col">
      <CardHeader className="gap-4">
        <div className="flex flex-wrap items-center justify-end gap-2">
          <Badge variant="outline">Live session</Badge>
          <Badge variant="secondary">{messages.length} messages</Badge>
        </div>

        <div className="grid gap-4 rounded-lg border bg-muted/30 p-4 lg:grid-cols-[260px_minmax(0,1fr)]">
          <div className="flex flex-col gap-3">
            <div className="flex flex-col gap-2">
              <label htmlFor="tracking-agent" className="text-sm font-medium">
                Agent
              </label>
              <Select
                id="tracking-agent"
                value={selectedAgentId}
                onChange={event => onSelectedAgentChange(event.target.value)}
              >
                {agents.map(agent => (
                  <option key={agent.id} value={agent.id}>
                    {agent.name} - {agent.role}
                  </option>
                ))}
              </Select>
            </div>

            <div className="flex flex-wrap gap-2">
              {QUICK_PROMPTS.map(prompt => (
                <Button
                  key={prompt}
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={() => onSendQuickPrompt(prompt)}
                >
                  {prompt}
                </Button>
              ))}
            </div>
          </div>

          <div className="rounded-lg border bg-background p-3">
            {selectedTask ? (
              <div className="flex min-w-0 flex-col gap-2">
                <div className="flex min-w-0 items-center justify-between gap-2">
                  <p
                    className="min-w-0 truncate text-sm font-medium"
                    title={selectedTask.title}
                  >
                    {selectedTask.title}
                  </p>
                  <Badge
                    className="shrink-0"
                    variant={STATUS_META[selectedTask.status].badgeVariant}
                  >
                    {STATUS_META[selectedTask.status].label}
                  </Badge>
                </div>
                <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                  <span>{repoNameById(selectedTask.repoId)}</span>
                  <span>{selectedTask.progress}% progress</span>
                  <span>{timeAgo(selectedTask.createdAt)}</span>
                </div>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                No task currently assigned to this agent.
              </p>
            )}
          </div>
        </div>
      </CardHeader>

      <CardContent className="flex min-h-0 flex-1 flex-col">
        <div className="min-h-0 flex-1 rounded-lg border bg-background p-2">
          <ScrollArea className="h-full rounded-md p-2">
            {messages.length === 0 ? (
              <p className="text-sm text-muted-foreground">No messages yet.</p>
            ) : (
              <div className="flex flex-col gap-2 pr-2">
                {messages.map(message => (
                  <article
                    key={message.id}
                    className={cn(
                      'max-w-[90%] rounded-md px-3 py-2 text-sm',
                      message.role === 'user'
                        ? 'ml-auto bg-primary text-primary-foreground'
                        : message.role === 'system'
                          ? 'bg-secondary text-secondary-foreground'
                          : 'bg-muted',
                    )}
                  >
                    <p className="text-xs font-medium opacity-80">
                      {roleLabel(message.role)}
                    </p>
                    <p className="mt-1 break-words leading-snug">{message.text}</p>
                    <p className="mt-1 text-[11px] opacity-75">{timeAgo(message.time)}</p>
                  </article>
                ))}
              </div>
            )}
          </ScrollArea>
        </div>
      </CardContent>

      <CardFooter className="border-t pt-4">
        <form onSubmit={onSubmit} className="flex w-full items-center gap-2">
          <Input
            value={input}
            onChange={event => onInputChange(event.target.value)}
            placeholder={
              tasksForAgent.length > 0
                ? 'Ask for ETA, blockers, or checkpoints...'
                : 'This agent has no assigned tasks yet.'
            }
          />
          <Button type="submit" size="icon" aria-label="Send tracking message">
            <SendHorizontal data-icon="inline-start" />
          </Button>
        </form>
      </CardFooter>
    </Card>
  );
}
