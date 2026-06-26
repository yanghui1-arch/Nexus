import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { FolderGit2, Send, Link2 } from 'lucide-react';
import { useAppLayout } from '@/components/layout/AppLayout';
import { useWorkspaceRecords } from '@/lib/useWorkspaceRecords';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { usePublishTask } from './hooks/usePublishTask';

export default function PublishTaskPage() {
  const { t } = useTranslation();

  useAppLayout({
    title: t('publishTask.title'),
    description: t('publishTask.description'),
  });

  const data = useWorkspaceRecords();
  const codingAgentOptions = useMemo(
    () => data.agentOptions.filter(agent => agent.agent !== 'assistant'),
    [data.agentOptions],
  );
  const codingAgentInstances = useMemo(
    () => data.agentInstances.filter(instance => instance.agent !== 'assistant'),
    [data.agentInstances],
  );
  const publisher = usePublishTask({
    ...data,
    agentInstances: codingAgentInstances,
    agentOptions: codingAgentOptions,
  });

  const hasAgents = codingAgentOptions.length > 0;
  const canSubmit =
    hasAgents &&
    publisher.composerValues.question.trim().length > 0 &&
    publisher.composerValues.agentInstanceId.length > 0 &&
    publisher.hasWorkspaceContext &&
    !publisher.isSubmitting;

  return (
    <div className="mx-auto max-w-3xl">
      <div className="rounded-2xl border border-gray-200/60 bg-white">
        <form
          id="workspace-publish-task-form"
          onSubmit={publisher.publishTask}
        >
          <div className="px-6 py-5">
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
              rows={6}
              value={publisher.composerValues.question}
              onChange={event => publisher.setComposerValues({ ...publisher.composerValues, question: event.target.value })}
              placeholder={t('publishTask.questionPlaceholder')}
              className="min-h-[140px] text-[15px] leading-relaxed resize-y"
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

            <div className="mb-4">
              <label htmlFor="publish-issue-url" className="text-xs font-medium text-gray-500">
                {t('publishTask.outerIssueUrlOptional')}
              </label>
              <Input
                id="publish-issue-url"
                value={publisher.composerValues.externalIssueUrl}
                onChange={event => publisher.setComposerValues({ ...publisher.composerValues, externalIssueUrl: event.target.value })}
                placeholder="https://github.com/owner/repo/issues/..."
                className="mt-1.5 h-10 text-sm"
              />
            </div>

            <div>
              <p className="text-xs font-medium text-gray-500 mb-1.5">
                {t('publishTask.agentInstance')}
              </p>
              {codingAgentOptions.length === 0 ? (
                <p className="text-sm text-gray-400">{t('publishTask.noActiveAgents')}</p>
              ) : (
                <div className="flex flex-col gap-2">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {codingAgentOptions.map(agent => (
                      <label
                        key={agent.id}
                        className={`flex items-center gap-2.5 rounded-xl border p-3 cursor-pointer transition-all ${
                          publisher.composerValues.agentInstanceId === agent.id
                            ? 'border-[hsl(80,85%,55%)] bg-[hsl(80,85%,97%)]'
                            : 'border-gray-200/60 hover:border-gray-300'
                        }`}
                      >
                        <input
                          type="radio"
                          name="agent"
                          value={agent.id}
                          checked={publisher.composerValues.agentInstanceId === agent.id}
                          onChange={() => publisher.setComposerValues({ ...publisher.composerValues, agentInstanceId: agent.id })}
                          className="sr-only"
                        />
                        <div className={`size-4 rounded-full border-2 flex items-center justify-center shrink-0 ${
                          publisher.composerValues.agentInstanceId === agent.id
                            ? 'border-[hsl(80,85%,55%)]'
                            : 'border-gray-300'
                        }`}>
                          {publisher.composerValues.agentInstanceId === agent.id && (
                            <div className="size-2 rounded-full bg-[hsl(80,85%,55%)]" />
                          )}
                        </div>
                        <div className="min-w-0 flex-1">
                          <p className="text-sm font-medium text-[hsl(0,0%,8%)] truncate">{agent.label}</p>
                          <p className="text-xs text-gray-400 truncate">{agent.subtitle}</p>
                        </div>
                      </label>
                    ))}
                  </div>
                  {publisher.selectedAgent && publisher.hasWorkspaceContext && (
                    <div className="flex items-center gap-3 rounded-lg bg-blue-50/50 border border-blue-100 px-4 py-2.5">
                      <FolderGit2 className="size-4 text-blue-400 shrink-0" />
                      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 text-xs">
                        <span className="text-gray-500">{t('common.repository')}:</span>
                        <span className="font-mono font-medium text-[hsl(0,0%,8%)]">{publisher.selectedAgent.workspaceRepo}</span>
                        <span className="text-gray-300 hidden sm:inline">/</span>
                        <span className="text-gray-500">{t('common.project')}:</span>
                        <span className="font-medium text-[hsl(0,0%,8%)]">{publisher.selectedAgent.workspaceProject}</span>
                      </div>
                    </div>
                  )}
                  {(!publisher.selectedAgent || !publisher.hasWorkspaceContext) && (
                    <div className="rounded-lg bg-amber-50 border border-amber-200 px-4 py-2.5">
                      <p className="text-xs text-amber-700">
                        {t('publishTask.workspaceRequiredDescription')}{' '}
                        <Link to="/workspace-settings" className="font-medium underline underline-offset-2 hover:text-amber-800">
                          {t('publishTask.workspaceRequiredAction')}
                        </Link>
                      </p>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          <div className="border-t border-gray-100 px-6 py-5 flex items-center justify-between">
            <p className="text-xs text-gray-400">{t('publishTask.footerHint')}</p>
            <Button
              type="submit"
              form="workspace-publish-task-form"
              disabled={!canSubmit}
              className="h-10 rounded-xl bg-[hsl(0,0%,8%)] text-white hover:bg-[hsl(0,0%,20%)] px-6 text-sm gap-2"
            >
              <Send className="size-4" />
              {publisher.isSubmitting ? t('publishTask.publishing') : t('publishTask.publish')}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
