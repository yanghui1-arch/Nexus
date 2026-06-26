import type { FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { Send, Link2 } from 'lucide-react';
import type { WorkspaceAgentOption } from '@/lib/workspace-task-view';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
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
  selectedAgent: _selectedAgent,
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
    <div className="rounded-2xl border border-gray-200/60 bg-white">
      <form
        id="workspace-publish-task-form"
        onSubmit={onSubmit}
        className="flex flex-col"
      >
        <div className="p-6">
          <div className="flex items-center gap-2 mb-4">
            <div className="flex size-8 items-center justify-center rounded-lg bg-[hsl(80,85%,92%)]">
              <Send className="size-4 text-[hsl(80,70%,35%)]" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-[hsl(0,0%,8%)]">{t('publishTask.question')}</h3>
              <p className="text-xs text-gray-400">{t('publishTask.questionPlaceholder')}</p>
            </div>
          </div>

          <Textarea
            id="publish-question"
            rows={8}
            value={value.question}
            onChange={event => updateField('question', event.target.value)}
            placeholder={t('publishTask.questionPlaceholder')}
            className="min-h-[160px] text-[15px] leading-relaxed"
          />
        </div>

        <div className="border-t border-gray-100 px-6 py-5">
          <div className="flex items-center gap-2 mb-4">
            <div className="flex size-8 items-center justify-center rounded-lg bg-purple-50">
              <Link2 className="size-4 text-purple-500" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-[hsl(0,0%,8%)]">{t('publishTask.routing')}</h3>
              <p className="text-xs text-gray-400">{t('publishTask.routingDescription')}</p>
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <label htmlFor="publish-issue-url" className="text-xs font-medium text-gray-500">
              {t('publishTask.outerIssueUrlOptional')}
            </label>
            <Input
              id="publish-issue-url"
              value={value.externalIssueUrl}
              onChange={event => updateField('externalIssueUrl', event.target.value)}
              placeholder="https://github.com/owner/repo/issues/..."
              className="h-10"
            />
          </div>
        </div>

        <div className="border-t border-gray-100 px-6 py-5 flex items-center justify-between">
          <p className="text-xs text-gray-400">
            {isSubmitting ? t('publishTask.publishing') : t('publishTask.publish')}
          </p>
          <Button
            type="submit"
            form="workspace-publish-task-form"
            disabled={!canSubmit}
            className="h-10 rounded-xl bg-[hsl(0,0%,8%)] text-white hover:bg-[hsl(0,0%,20%)] px-6"
          >
            <Send className="size-4" />
            {isSubmitting ? t('publishTask.publishing') : t('publishTask.publish')}
          </Button>
        </div>
      </form>
    </div>
  );
}
