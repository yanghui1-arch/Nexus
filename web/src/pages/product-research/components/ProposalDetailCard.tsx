import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import type { ApiFeature, ApiProductProposal } from '@/api/types';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
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
import { ProposalDetailPanel, ProposalOverviewPanel } from './ProposalDetailPanels';
import {
  combineProposalSections,
  summarizeProposalLine,
  type ProposalDetailTabKey,
  type ProposalOverviewItem,
} from './proposalDetailPanel';

type ProposalDetailCardProps = {
  activeReview: ReviewActionState;
  onReview: (proposalId: string, status: ReviewActionStatus) => Promise<void>;
  onRecoverPlanning: (proposalId: string) => Promise<void>;
  proposal: ApiProductProposal;
  relatedFeatures: ApiFeature[];
  recoveringPlanning: boolean;
};

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
  const [activeTab, setActiveTab] = useState<ProposalDetailTabKey>('overview');
  const visibleTab = activeTab === 'plan-list' && !canOpenPlanList
    ? 'overview'
    : activeTab;
  const scopeContent = combineProposalSections(
    proposalAnswer.sections.proposedScope,
    proposalAnswer.sections.nonGoals
      ? `## ${t('productResearch.detailNonGoals')}\n${proposalAnswer.sections.nonGoals}`
      : undefined,
  );
  const evidenceContent = combineProposalSections(
    proposalAnswer.sections.repositoryEvidence,
    proposalAnswer.sections.externalEvidence,
  );
  const breakdownContent = proposalAnswer.sections.suggestedSmallFeatureBreakdown;
  const fullDescription = proposalAnswer.fullText || proposal.summary;
  const overviewItems: ProposalOverviewItem[] = [
    {
      label: t('productResearch.overviewConclusion'),
      content: summarizeProposalLine(
        proposal.summary || proposalAnswer.sections.problemOpportunity,
        t('productResearch.decisionBriefUnavailable'),
      ),
    },
    {
      label: t('productResearch.overviewUsersValue'),
      content: summarizeProposalLine(proposalAnswer.sections.userBusinessImpact, t('productResearch.decisionBriefUnavailable')),
    },
    {
      label: t('productResearch.overviewApprovalAdvice'),
      content: t(isPending ? 'productResearch.overviewApprovalAdvicePending' : 'productResearch.overviewApprovalAdviceReviewed'),
    },
    {
      label: t('productResearch.overviewHighestRisk'),
      content: summarizeProposalLine(proposalAnswer.sections.risksMitigations, t('productResearch.overviewNoRisk')),
    },
    {
      label: t('productResearch.overviewPrimaryAction'),
      content: summarizeProposalLine(breakdownContent, t('productResearch.overviewPrimaryActionFallback')),
    },
  ];
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
          setActiveTab(value as ProposalDetailTabKey);
        }}
        className="gap-3"
      >
        <TabsList className="flex h-auto flex-wrap justify-start">
          <TabsTrigger value="overview">
            {t('productResearch.detailOverview')}
          </TabsTrigger>
          <TabsTrigger value="scope">
            {t('productResearch.detailScope')}
          </TabsTrigger>
          <TabsTrigger value="evidence">
            {t('productResearch.detailEvidence')}
          </TabsTrigger>
          <TabsTrigger value="risk">
            {t('productResearch.detailRisk')}
          </TabsTrigger>
          <TabsTrigger value="breakdown">
            {t('productResearch.detailBreakdown')}
          </TabsTrigger>
          <TabsTrigger value="description">
            {t('productResearch.detailDescription')}
          </TabsTrigger>
          <TabsTrigger value="plan-list" disabled={!canOpenPlanList}>
            {t('productResearch.planList')}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="overview">
          <ProposalOverviewPanel items={overviewItems} />
        </TabsContent>

        <TabsContent value="scope">
          <ProposalDetailPanel content={scopeContent} fallback={t('productResearch.decisionBriefUnavailable')} />
        </TabsContent>
        <TabsContent value="evidence">
          <ProposalDetailPanel content={evidenceContent} fallback={t('productResearch.decisionBriefUnavailable')} />
        </TabsContent>
        <TabsContent value="risk">
          <ProposalDetailPanel content={proposalAnswer.sections.risksMitigations} fallback={t('productResearch.decisionBriefUnavailable')} />
        </TabsContent>
        <TabsContent value="breakdown">
          <ProposalDetailPanel content={breakdownContent} fallback={t('productResearch.decisionBriefUnavailable')} />
        </TabsContent>
        <TabsContent value="description">
          <ProposalDetailPanel content={fullDescription} fallback={t('productResearch.decisionBriefUnavailable')} />
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
