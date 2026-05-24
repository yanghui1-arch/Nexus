import type { FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import type { WorkspaceAgentOption } from '@/lib/workspace-task-view';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardFooter } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import type { WorkspaceComposerValues } from '../types';

type PublishTaskComposerCardProps = {
  value: WorkspaceComposerValues;
  agents: WorkspaceAgentOption[];
  selectedAgent: WorkspaceAgentOption | null;
  hasWorkspaceContext: boolean;
  isSubmitting: boolean;
  onValueChange: (next: WorkspaceComposerValues) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
};

export function PublishTaskComposerCard({
  value,
  agents,
  selectedAgent,
  hasWorkspaceContext,
  isSubmitting,
  onValueChange,
  onSubmit,
}: PublishTaskComposerCardProps) {
  const { t } = useTranslation();
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
    value.agentInstanceId.length > 0 &&
    hasWorkspaceContext &&
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
              {t('publishTask.question')}
            </label>
            <Textarea
              id="publish-question"
              rows={6}
              value={value.question}
              onChange={event => updateField('question', event.target.value)}
              placeholder={t('publishTask.questionPlaceholder')}
              className="bg-background"
            />
          </div>

          <div className="rounded-xl bg-muted/30 p-4">
            <div className="mb-3 flex flex-col gap-1">
              <p className="text-xs font-medium uppercase tracking-[0.16em] text-muted-foreground">
                {t('publishTask.routing')}
              </p>
              <p className="text-sm text-muted-foreground">
                {t('publishTask.routingDescription')}
              </p>
            </div>

            <div className="grid gap-4 xl:grid-cols-2">
              <div className="flex flex-col gap-1.5">
                <label htmlFor="publish-issue-url" className="text-sm font-medium">
                  {t('publishTask.outerIssueUrlOptional')}
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
                  {t('publishTask.agentInstance')}
                </label>
                <Select
                  id="publish-agent-instance"
                  value={value.agentInstanceId}
                  onChange={event => updateField('agentInstanceId', event.target.value)}
                  disabled={!hasAgents || isSubmitting}
                  className="bg-background"
                >
                  {!hasAgents ? (
                    <option value="">{t('publishTask.noActiveAgents')}</option>
                  ) : null}
                  {hasAgents ? <option value="">{t('publishTask.selectAgent')}</option> : null}
                  {agents.map(agent => (
                    <option key={agent.id} value={agent.id}>
                      {agent.label} - {agent.subtitle}
                    </option>
                  ))}
                </Select>
                {!hasAgents ? (
                  <p className="text-xs text-muted-foreground">
                    {t('publishTask.activateAgentHint')}
                  </p>
                ) : null}
              </div>
            </div>

            <div className="mt-4 rounded-lg border bg-background p-4">
              <div className="flex flex-col gap-1">
                <p className="text-sm font-medium">{t('publishTask.selectedWorkspace')}</p>
                {selectedAgent && hasWorkspaceContext ? (
                  <>
                    <p className="text-sm text-muted-foreground">
                      {t('publishTask.selectedWorkspaceDescription')}
                    </p>
                    <div className="mt-2 grid gap-3 sm:grid-cols-2">
                      <div className="rounded-md bg-muted/40 p-3">
                        <div className="text-xs uppercase tracking-[0.12em] text-muted-foreground">
                          {t('common.repository')}
                        </div>
                        <div className="mt-1 font-mono text-sm">
                          {selectedAgent.workspaceRepo}
                        </div>
                      </div>
                      <div className="rounded-md bg-muted/40 p-3">
                        <div className="text-xs uppercase tracking-[0.12em] text-muted-foreground">
                          {t('common.project')}
                        </div>
                        <div className="mt-1 text-sm">
                          {selectedAgent.workspaceProject}
                        </div>
                      </div>
                    </div>
                  </>
                ) : (
                  <p className="text-sm text-muted-foreground">
                    {t('publishTask.workspaceRequiredDescription')}{' '}
                    <Link to="/workspace-settings" className="font-medium text-foreground underline underline-offset-4">
                      {t('publishTask.workspaceRequiredAction')}
                    </Link>
                  </p>
                )}
              </div>
            </div>
          </div>
        </form>
      </CardContent>

      <CardFooter className="flex flex-col items-stretch gap-3 px-0 pt-3 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-xs text-muted-foreground">
          {t('publishTask.footerHint')}
        </p>
        <Button
          type="submit"
          form="workspace-publish-task-form"
          disabled={!canSubmit}
        >
          {isSubmitting ? t('publishTask.publishing') : t('publishTask.publish')}
        </Button>
      </CardFooter>
    </Card>
  );
}
