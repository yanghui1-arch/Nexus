import type { FormEvent } from 'react';
import type {
  WorkspaceAgentOption,
  WorkspaceComposerValues,
} from '../utils';
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

type WorkspaceComposerCardProps = {
  value: WorkspaceComposerValues;
  agents: WorkspaceAgentOption[];
  isSubmitting: boolean;
  onValueChange: (next: WorkspaceComposerValues) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
};

export function WorkspaceComposerCard({
  value,
  agents,
  isSubmitting,
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

  const selectedAgent = agents.find(agent => agent.id === value.agentInstanceId);
  const hasAgents = agents.length > 0;
  const canSubmit =
    hasAgents &&
    value.question.trim().length > 0 &&
    value.repo.trim().length > 0 &&
    value.agentInstanceId.length > 0 &&
    !isSubmitting;

  return (
    <Card className="min-h-0">
      <CardHeader className="gap-4">
        <div className="flex flex-wrap items-center justify-end gap-2">
          <Badge variant="outline">Draft</Badge>
          <Badge variant="secondary">API aligned</Badge>
        </div>

        <div className="grid gap-3 rounded-lg border bg-muted/30 p-4 md:grid-cols-3">
          <div className="flex min-w-0 flex-col gap-1">
            <p className="text-xs text-muted-foreground">Repository Scope</p>
            <p className="truncate text-sm font-medium" title={value.repo || '-'}>
              {value.repo || '-'}
            </p>
          </div>
          <div className="flex min-w-0 flex-col gap-1">
            <p className="text-xs text-muted-foreground">Assigned Agent</p>
            <p
              className="truncate text-sm font-medium"
              title={selectedAgent ? `${selectedAgent.label} - ${selectedAgent.subtitle}` : '-'}
            >
              {selectedAgent ? `${selectedAgent.label} - ${selectedAgent.subtitle}` : '-'}
            </p>
          </div>
          <div className="flex min-w-0 flex-col gap-1">
            <p className="text-xs text-muted-foreground">Project</p>
            <p className="truncate text-sm font-medium" title={value.project || '-'}>
              {value.project || '-'}
            </p>
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
            <label htmlFor="publish-question" className="text-sm font-medium">
              Question
            </label>
            <Textarea
              id="publish-question"
              rows={8}
              value={value.question}
              onChange={event => updateField('question', event.target.value)}
              placeholder="Describe the task the agent should execute."
            />
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <div className="flex flex-col gap-2 rounded-lg border p-4">
              <label htmlFor="publish-repo" className="text-sm font-medium">
                Repository
              </label>
              <Input
                id="publish-repo"
                value={value.repo}
                onChange={event => updateField('repo', event.target.value)}
                placeholder="owner/repo"
              />
            </div>

            <div className="flex flex-col gap-2 rounded-lg border p-4">
              <label htmlFor="publish-project" className="text-sm font-medium">
                Project (optional)
              </label>
              <Input
                id="publish-project"
                value={value.project}
                onChange={event => updateField('project', event.target.value)}
                placeholder="web"
              />
            </div>
          </div>

          <div className="flex flex-col gap-2 rounded-lg border p-4">
            <label htmlFor="publish-agent-instance" className="text-sm font-medium">
              Agent instance
            </label>
            <Select
              id="publish-agent-instance"
              value={value.agentInstanceId}
              onChange={event => updateField('agentInstanceId', event.target.value)}
              disabled={!hasAgents || isSubmitting}
            >
              {!hasAgents ? (
                <option value="">No active agent instances available</option>
              ) : null}
              {hasAgents ? <option value="">Select an agent instance</option> : null}
              {agents.map(agent => (
                <option key={agent.id} value={agent.id}>
                  {agent.label} - {agent.subtitle}
                </option>
              ))}
            </Select>
            {!hasAgents ? (
              <p className="text-xs text-muted-foreground">
                Create or activate an agent instance before publishing a task.
              </p>
            ) : null}
          </div>
        </form>
      </CardContent>

      <CardFooter className="flex flex-col items-stretch gap-3 border-t pt-4 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-xs text-muted-foreground">
          Published tasks are submitted directly to the backend queue.
        </p>
        <Button
          type="submit"
          form="workspace-publish-task-form"
          disabled={!canSubmit}
        >
          {isSubmitting ? 'Publishing...' : 'Publish Task'}
        </Button>
      </CardFooter>
    </Card>
  );
}
