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
  proposal: ApiProductProposal;
  relatedFeatures: ApiFeature[];
  recoveringPlanning: boolean;
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
    <details className="group border-t py-4" open>
      <summary className="flex cursor-pointer list-none items-center gap-2 text-base font-medium">
        <span className="text-muted-foreground transition-transform group-open:rotate-90" aria-hidden="true">
          ›
        </span>
        <h3 className="text-base font-semibold">{title}</h3>
      </summary>
      <div className="mt-3 text-sm leading-6">
        {content?.trim() ? (
          <MarkdownContent content={content} />
        ) : (
          <p className="text-muted-foreground">{fallback}</p>
        )}
      </div>
    </details>
  );
}

export function ProposalDetailCard({
  activeReview,
  onReview,
  onRecoverPlanning,
  proposal,
  relatedFeatures,
  recoveringPlanning,
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
  const fallbackBriefContent = proposalAnswer.status === 'unrecognized'
    ? [proposal.summary, proposal.answer].filter(Boolean).join('\n\n')
    : undefined;
  const [activeTab, setActiveTab] = useState<DetailTabKey>('decision-brief');
  const visibleTab = activeTab === 'plan-list' && !canOpenPlanList
    ? 'decision-brief'
    : activeTab;
  const decisionContext = fallbackBriefContent ?? [
    proposal.summary,
    proposalAnswer.sections.proposedScope,
    proposalAnswer.sections.problemOpportunity,
  ].filter(Boolean).join('\n\n');
  const approachContent = fallbackBriefContent
    ? undefined
    : proposalAnswer.sections.suggestedSmallFeatureBreakdown || proposal.summary;
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
    <article className="flex flex-col gap-5">
      <header className="flex flex-col gap-3 border-b pb-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div className="flex min-w-0 flex-col gap-2">
            <h2 className="text-2xl font-semibold tracking-tight">{proposal.title}</h2>
            <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm text-muted-foreground">
              <span>{proposal.repo ?? t('common.noRepository')}</span>
              <span>{proposal.project ?? t('common.noProject')}</span>
              <span>{t('common.updatedRelative', { time: formatRelativeTime(proposal.updated_at) })}</span>
            </div>
            {planningMessage ? (
              <p className="text-sm text-red-700">{planningMessage}</p>
            ) : null}
          </div>

          <div className="flex flex-col items-start gap-2 lg:items-end">
            <div className="flex flex-wrap items-center justify-end gap-2">
              <Badge variant={statusMeta.variant} className={statusMeta.className}>
                {t(`productResearch.proposalStatus.${proposal.status}`)}
              </Badge>
              {planningStatus ? (
                <Badge
                  variant={PROPOSAL_PLANNING_STATUS_META[planningStatus].variant}
                  className={PROPOSAL_PLANNING_STATUS_META[planningStatus].className}
                >
                  {t(`productResearch.planningRunStatus.${planningStatus}`)}
                </Badge>
              ) : null}
            </div>

            <div className="flex flex-wrap items-center justify-end gap-2">
                {showViewTask ? (
                <Button asChild type="button" size="sm" variant="outline">
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

      <Tabs
        value={visibleTab}
        onValueChange={value => {
          if (value === 'plan-list' && !canOpenPlanList) {
            return;
          }
          setActiveTab(value as DetailTabKey);
        }}
        className="gap-3"
      >
        <TabsList>
          <TabsTrigger value="decision-brief">
            {t('productResearch.decisionBrief')}
          </TabsTrigger>
          <TabsTrigger value="plan-list" disabled={!canOpenPlanList}>
            {t('productResearch.planList')}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="decision-brief" className="flex flex-col">
          <BriefDisclosure
            title={fallbackBriefContent
              ? t('productResearch.decisionBriefOriginalContent')
              : t('productResearch.decisionBriefDecision')}
            content={decisionContext}
            fallback={t('productResearch.decisionBriefUnavailable')}
          />
          {fallbackBriefContent ? null : (
            <>
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
            </>
          )}
        </TabsContent>


        <TabsContent value="plan-list">
          <ProposalPlanList features={relatedFeatures} />
        </TabsContent>
      </Tabs>

      {isPending ? (
        <footer className="flex justify-end pt-1">
          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="outline"
              disabled={isBusy}
              onClick={() => void onReview(proposal.id, 'rejected')}
            >
              {isRejecting ? t('productResearch.rejecting') : t('productResearch.reject')}
            </Button>
            <Button
              type="button"
              disabled={isBusy}
              onClick={() => void onReview(proposal.id, 'approved')}
            >
              {isApproving ? t('productResearch.approving') : t('productResearch.approve')}
            </Button>
          </div>
        </footer>
      ) : null}
    </article>
  );
}
