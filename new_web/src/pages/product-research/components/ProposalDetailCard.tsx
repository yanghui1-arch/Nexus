import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import type { ApiFeature, ApiProductProposal } from '@/api/types';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { MarkdownContent } from '@/components/ui/markdown-content';
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '@/components/ui/tabs';
import { PROPOSAL_PLANNING_STATUS_META, PROPOSAL_STATUS_META } from '../constants';
import { parseProposalAnswerSections } from '../proposalAnswerParser';
import type { ReviewActionState, ReviewActionStatus } from '../types';
import {
  formatRelativeTime,
  getProposalPlanningDisplayStatus,
  hasValidatedProposalPlan,
} from '../utils';
import { ProposalPlanList } from './ProposalPlanList';

type DetailTabKey = 'decision-brief' | 'plan-list';

type ProposalDetailCardProps = {
  activeReview: ReviewActionState;
  onReview: (proposalId: string, status: ReviewActionStatus) => Promise<void>;
  onRecoverPlanning: (proposalId: string) => Promise<void>;
  onRetryFeatureItem: (featureItemId: string) => Promise<void>;
  proposal: ApiProductProposal;
  relatedFeatures: ApiFeature[];
  recoveringPlanning: boolean;
  retryingFeatureItemId: string | null;
};

function BriefDisclosure({
  content,
  fallback,
  title,
}: {
  content: string | undefined;
  fallback: string;
  title: string;
}) {
  return (
    <details className="group border-t border-gray-100 py-4" open>
      <summary className="flex cursor-pointer list-none items-center gap-2 text-sm font-semibold text-[hsl(0,0%,8%)]">
        <span className="text-gray-400 transition-transform group-open:rotate-90" aria-hidden="true">
          ›
        </span>
        <h3>{title}</h3>
      </summary>
      <div className="mt-3 text-sm leading-6 text-gray-600">
        {content?.trim() ? (
          <MarkdownContent>{content}</MarkdownContent>
        ) : (
          <p className="text-gray-400">{fallback}</p>
        )}
      </div>
    </details>
  );
}

export function ProposalDetailCard({
  activeReview,
  onReview,
  onRecoverPlanning,
  onRetryFeatureItem,
  proposal,
  relatedFeatures,
  recoveringPlanning,
  retryingFeatureItemId,
}: ProposalDetailCardProps) {
  const { t } = useTranslation();
  const statusMeta = PROPOSAL_STATUS_META[proposal.status];
  const planningStatus = getProposalPlanningDisplayStatus(proposal);
  const planningRun = proposal.latest_planning_run;
  const isApproving =
    activeReview?.proposalId === proposal.id && activeReview.status === 'approved';
  const isRejecting =
    activeReview?.proposalId === proposal.id && activeReview.status === 'rejected';
  const isBusy = isApproving || isRejecting;
  const isPending = proposal.status === 'proposed';
  const canOpenPlanList =
    hasValidatedProposalPlan(proposal) && relatedFeatures.length > 0;
  const proposalAnswer = parseProposalAnswerSections(proposal.answer);
  const [activeTab, setActiveTab] = useState<DetailTabKey>('decision-brief');
  const visibleTab = activeTab === 'plan-list' && !canOpenPlanList
    ? 'decision-brief'
    : activeTab;
  const decisionContext = [
    proposalAnswer.sections.problemOpportunity,
    proposal.summary,
    proposalAnswer.sections.proposedScope,
  ].filter(Boolean).join('\n\n');
  const approachContent = proposalAnswer.sections.suggestedSmallFeatureBreakdown
    || proposal.summary;
  const showRetryPlanning = planningStatus === 'failed';
  const showRecoverPlanning =
    planningStatus === 'missing_run' || planningStatus === 'missing_task';
  const showViewTask = Boolean(
    planningRun?.task_id && (
      planningStatus === 'queued' ||
      planningStatus === 'running' ||
      planningStatus === 'failed'
    ),
  );
  const planningMessage = planningStatus === 'failed'
    ? planningRun?.error ?? t('productResearch.planningFailedInlineFallback')
    : planningStatus === 'missing_run'
      ? t('productResearch.planningMissingRunInline')
      : planningStatus === 'missing_task'
        ? t('productResearch.planningMissingTaskInline')
      : null;

  return (
    <article className="rounded-2xl border border-gray-200/60 bg-white">
      <header className="border-b border-gray-100 p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="flex min-w-0 flex-col gap-2">
            <h2 className="text-xl font-bold tracking-tight text-[hsl(0,0%,8%)]">{proposal.title}</h2>
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-gray-500">
              <span>{proposal.repo ?? t('common.noRepository')}</span>
              <span>{proposal.project ?? t('common.noProject')}</span>
              <span>{t('common.updatedRelative', { time: formatRelativeTime(proposal.updated_at) })}</span>
            </div>
            {planningMessage ? (
              <p className="text-sm text-red-600">{planningMessage}</p>
            ) : null}
          </div>

          <div className="flex flex-col items-start gap-3 lg:items-end">
            <div className="flex flex-wrap items-center justify-end gap-2">
              <Badge variant="outline" className={statusMeta.className}>
                {t(`productResearch.proposalStatus.${proposal.status}` as never)}
              </Badge>
              {planningStatus ? (
                <Badge
                  variant="outline"
                  className={PROPOSAL_PLANNING_STATUS_META[planningStatus].className}
                >
                  {t(`productResearch.planningRunStatus.${planningStatus}` as never)}
                </Badge>
              ) : null}
            </div>

            <div className="flex flex-wrap items-center justify-end gap-2">
              {showViewTask ? (
                <Button asChild type="button" size="sm" variant="outline" className="h-8 rounded-lg">
                  <Link to={`/task/${planningRun?.task_id}`}>
                    {t('productResearch.planningViewTask')}
                  </Link>
                </Button>
              ) : null}
              {showRecoverPlanning ? (
                <Button
                  type="button"
                  size="sm"
                  disabled={recoveringPlanning}
                  onClick={() => void onRecoverPlanning(proposal.id)}
                  className="h-8 rounded-lg bg-[hsl(0,0%,8%)] text-white hover:bg-[hsl(0,0%,20%)]"
                >
                  {recoveringPlanning
                    ? t('productResearch.planningRecovering')
                    : planningStatus === 'missing_task'
                      ? t('productResearch.planningRecreateTask')
                      : t('productResearch.planningRecover')}
                </Button>
              ) : null}
              {showRetryPlanning ? (
                <Button
                  type="button"
                  size="sm"
                  disabled={recoveringPlanning}
                  onClick={() => void onRecoverPlanning(proposal.id)}
                  className="h-8 rounded-lg bg-[hsl(0,0%,8%)] text-white hover:bg-[hsl(0,0%,20%)]"
                >
                  {recoveringPlanning
                    ? t('productResearch.planningRetrying')
                    : t('productResearch.planningRetry')}
                </Button>
              ) : null}
            </div>
          </div>
        </div>
      </header>

      <div className="p-6">
        <Tabs
          value={visibleTab}
          onValueChange={value => {
            if (value === 'plan-list' && !canOpenPlanList) {
              return;
            }
            setActiveTab(value as DetailTabKey);
          }}
        >
          <TabsList className="bg-gray-100">
            <TabsTrigger value="decision-brief" className="data-[state=active]:bg-white data-[state=active]:shadow-sm">
              {t('productResearch.decisionBrief')}
            </TabsTrigger>
            <TabsTrigger value="plan-list" disabled={!canOpenPlanList} className="data-[state=active]:bg-white data-[state=active]:shadow-sm">
              {t('productResearch.planList')}
            </TabsTrigger>
          </TabsList>

          <TabsContent value="decision-brief" className="mt-4 flex flex-col">
            <BriefDisclosure
              title={t('productResearch.decisionBriefDecision')}
              content={decisionContext}
              fallback={t('productResearch.decisionBriefUnavailable')}
            />
            <BriefDisclosure
              title={t('productResearch.decisionBriefApproach')}
              content={approachContent}
              fallback={t('productResearch.decisionBriefUnavailable')}
            />
            <BriefDisclosure
              title={t('productResearch.decisionBriefValue')}
              content={proposalAnswer.sections.userBusinessImpact}
              fallback={t('productResearch.decisionBriefUnavailable')}
            />
          </TabsContent>

          <TabsContent value="plan-list">
            <ProposalPlanList
              features={relatedFeatures}
              retryingFeatureItemId={retryingFeatureItemId}
              onRetryFeatureItem={onRetryFeatureItem}
            />
          </TabsContent>
        </Tabs>
      </div>

      {isPending ? (
        <footer className="flex justify-end border-t border-gray-100 p-6">
          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="outline"
              disabled={isBusy}
              onClick={() => void onReview(proposal.id, 'rejected')}
              className="h-9 rounded-lg"
            >
              {isRejecting ? t('productResearch.rejecting') : t('productResearch.reject')}
            </Button>
            <Button
              type="button"
              disabled={isBusy}
              onClick={() => void onReview(proposal.id, 'approved')}
              className="h-9 rounded-lg bg-[hsl(80,85%,55%)] text-[hsl(0,0%,10%)] hover:bg-[hsl(80,85%,45%)]"
            >
              {isApproving ? t('productResearch.approving') : t('productResearch.approve')}
            </Button>
          </div>
        </footer>
      ) : null}
    </article>
  );
}
