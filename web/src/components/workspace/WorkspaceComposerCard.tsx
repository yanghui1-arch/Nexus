import type { FormEvent } from 'react';
import type {
  AgentProfile,
  RepoProfile,
  WorkspaceUrgency,
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
import { Select } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';

export type WorkspaceComposerValues = {
  title: string;
  notes: string;
  repoId: string;
  agentId: string;
  urgency: WorkspaceUrgency;
};

type WorkspaceComposerCardProps = {
  value: WorkspaceComposerValues;
  repos: RepoProfile[];
  agents: AgentProfile[];
  onValueChange: (next: WorkspaceComposerValues) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
};

const URGENCY_OPTIONS: Array<{ value: WorkspaceUrgency; label: string }> = [
  { value: 'critical', label: 'Critical' },
  { value: 'high', label: 'High' },
  { value: 'normal', label: 'Normal' },
];

const URGENCY_BADGE_VARIANT: Record<
  WorkspaceUrgency,
  'default' | 'secondary' | 'destructive' | 'outline'
> = {
  critical: 'destructive',
  high: 'default',
  normal: 'secondary',
};

export function WorkspaceComposerCard({
  value,
  repos,
  agents,
  onValueChange,
  onSubmit,
}: WorkspaceComposerCardProps) {
  const updateField = <K extends keyof WorkspaceComposerValues>(
    key: K,
    nextValue: WorkspaceComposerValues[K],
  ) => {
    onValueChange({
      ...value,
      [key]: nextValue,
    });
  };

  const selectedRepo = repos.find(repo => repo.id === value.repoId);
  const selectedAgent = agents.find(agent => agent.id === value.agentId);

  const resetDraft = () => {
    onValueChange({
      ...value,
      title: '',
      notes: '',
      urgency: 'high',
    });
  };

  return (
    <Card className="min-h-0">
      <CardHeader className="gap-4">
        <div className="flex flex-wrap items-center justify-end gap-2">
          <Badge variant="outline">Draft</Badge>
          <Badge variant="secondary">Ready to route</Badge>
        </div>

        <div className="grid gap-3 rounded-lg border bg-muted/30 p-4 md:grid-cols-3">
          <div className="flex min-w-0 flex-col gap-1">
            <p className="text-xs text-muted-foreground">Repository Scope</p>
            <p className="truncate text-sm font-medium" title={selectedRepo?.fullName ?? '-'}>
              {selectedRepo?.fullName ?? '-'}
            </p>
          </div>
          <div className="flex min-w-0 flex-col gap-1">
            <p className="text-xs text-muted-foreground">Assigned Agent</p>
            <p
              className="truncate text-sm font-medium"
              title={selectedAgent ? `${selectedAgent.name} - ${selectedAgent.role}` : '-'}
            >
              {selectedAgent ? `${selectedAgent.name} - ${selectedAgent.role}` : '-'}
            </p>
          </div>
          <div className="flex min-w-0 flex-col gap-1">
            <p className="text-xs text-muted-foreground">Urgency</p>
            <div>
              <Badge variant={URGENCY_BADGE_VARIANT[value.urgency]}>
                {URGENCY_OPTIONS.find(option => option.value === value.urgency)?.label ??
                  value.urgency}
              </Badge>
            </div>
          </div>
        </div>
      </CardHeader>

      <CardContent>
        <form
          id="workspace-publish-task-form"
          onSubmit={onSubmit}
          className="flex flex-col gap-6"
        >
          <div className="flex flex-col gap-2">
            <label htmlFor="publish-title" className="text-sm font-medium">
              Task title
            </label>
            <Input
              id="publish-title"
              className="h-11"
              value={value.title}
              onChange={event => updateField('title', event.target.value)}
              placeholder="Example: Fix retry storm in payment confirmation"
            />
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <div className="flex flex-col gap-2 rounded-lg border p-4">
              <label htmlFor="publish-repo" className="text-sm font-medium">
                Repository
              </label>
              <Select
                id="publish-repo"
                value={value.repoId}
                onChange={event => updateField('repoId', event.target.value)}
              >
                {repos.map(repo => (
                  <option key={repo.id} value={repo.id}>
                    {repo.fullName}
                  </option>
                ))}
              </Select>
            </div>

            <div className="flex flex-col gap-2 rounded-lg border p-4">
              <label htmlFor="publish-agent" className="text-sm font-medium">
                Assign agent
              </label>
              <Select
                id="publish-agent"
                value={value.agentId}
                onChange={event => updateField('agentId', event.target.value)}
              >
                {agents.map(agent => (
                  <option key={agent.id} value={agent.id}>
                    {agent.name} - {agent.role}
                  </option>
                ))}
              </Select>
            </div>
          </div>

          <div className="grid gap-4 lg:grid-cols-[220px_minmax(0,1fr)]">
            <div className="flex flex-col gap-2 rounded-lg border p-4">
              <label htmlFor="publish-urgency" className="text-sm font-medium">
                Urgency
              </label>
              <Select
                id="publish-urgency"
                value={value.urgency}
                onChange={event =>
                  updateField('urgency', event.target.value as WorkspaceUrgency)
                }
              >
                {URGENCY_OPTIONS.map(option => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </Select>
            </div>

            <div className="flex flex-col gap-2 rounded-lg border p-4">
              <label htmlFor="publish-notes" className="text-sm font-medium">
                Notes
              </label>
              <Textarea
                id="publish-notes"
                rows={8}
                value={value.notes}
                onChange={event => updateField('notes', event.target.value)}
                placeholder="Context, dependencies, rollback notes..."
              />
            </div>
          </div>
        </form>
      </CardContent>

      <CardFooter className="flex items-center justify-between gap-3 border-t pt-4">
        <p className="text-xs text-muted-foreground">
          Published tasks immediately enter workspace queue.
        </p>
        <div className="flex items-center gap-2">
          <Button type="button" variant="outline" onClick={resetDraft}>
            Reset Draft
          </Button>
          <Button
            type="submit"
            form="workspace-publish-task-form"
            disabled={value.title.trim().length === 0}
          >
            Publish Task
          </Button>
        </div>
      </CardFooter>
    </Card>
  );
}
