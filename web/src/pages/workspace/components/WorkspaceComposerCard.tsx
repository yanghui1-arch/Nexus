import type { FormEvent } from 'react';
import type {
  WorkspaceAgentOption,
  WorkspaceComposerValues,
} from '../utils';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardFooter } from '@/components/ui/card';
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

  const hasAgents = agents.length > 0;
  const canSubmit =
    hasAgents &&
    value.question.trim().length > 0 &&
    value.repo.trim().length > 0 &&
    value.agentInstanceId.length > 0 &&
    !isSubmitting;

  return (
    <Card className="min-h-0 gap-0 border-0 bg-transparent py-0 shadow-none">
      <CardContent className="px-0 py-0">
        <form
          id="workspace-publish-task-form"
          onSubmit={onSubmit}
          className="flex flex-col gap-4"
        >
          <div className="flex flex-col gap-2">
            <label htmlFor="publish-question" className="text-sm font-medium">
              Question
            </label>
            <Textarea
              id="publish-question"
              rows={6}
              value={value.question}
              onChange={event => updateField('question', event.target.value)}
              placeholder="Describe the task the agent should execute."
              className="bg-background"
            />
          </div>

          <div className="rounded-xl bg-muted/30 p-4">
            <div className="mb-3 flex flex-col gap-1">
              <p className="text-xs font-medium uppercase tracking-[0.16em] text-muted-foreground">
                Routing
              </p>
              <p className="text-sm text-muted-foreground">
                Choose the repository, optional project, outer issue link, and target agent.
              </p>
            </div>

            <div className="grid gap-4 xl:grid-cols-2">
              <div className="flex flex-col gap-1.5">
                <label htmlFor="publish-repo" className="text-sm font-medium">
                  Repository
                </label>
                <Input
                  id="publish-repo"
                  value={value.repo}
                  onChange={event => updateField('repo', event.target.value)}
                  placeholder="owner/repo"
                  className="bg-background"
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <label htmlFor="publish-project" className="text-sm font-medium">
                  Project (optional)
                </label>
                <Input
                  id="publish-project"
                  value={value.project}
                  onChange={event => updateField('project', event.target.value)}
                  placeholder="web"
                  className="bg-background"
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <label htmlFor="publish-issue-url" className="text-sm font-medium">
                  Outer issue URL (optional)
                </label>
                <Input
                  id="publish-issue-url"
                  value={value.externalIssueUrl}
                  onChange={event => updateField('externalIssueUrl', event.target.value)}
                  placeholder="https://..."
                  className="bg-background"
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <label htmlFor="publish-agent-instance" className="text-sm font-medium">
                  Agent instance
                </label>
                <Select
                  id="publish-agent-instance"
                  value={value.agentInstanceId}
                  onChange={event => updateField('agentInstanceId', event.target.value)}
                  disabled={!hasAgents || isSubmitting}
                  className="bg-background"
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
            </div>
          </div>
        </form>
      </CardContent>

      <CardFooter className="flex flex-col items-stretch gap-3 px-0 pt-3 sm:flex-row sm:items-center sm:justify-between">
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
