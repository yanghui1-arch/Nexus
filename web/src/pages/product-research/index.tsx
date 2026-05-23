import { startTransition, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Link,
  Navigate,
  useLocation,
  useNavigate,
  useParams,
} from 'react-router-dom';
import { toast } from 'sonner';
import { getErrorDetail } from '@/api/client';
import {
  retryProductProposalPlanning,
  updateProductProposalStatus,
} from '@/api/product';
import { useAppLayout } from '@/components/layout/AppLayout';
import { Button } from '@/components/ui/button';
import {
  EmptyPanel,
  LoadingPanel,
} from './components/FeedbackPanels';
import { FeatureDetailCard } from './components/FeatureDetailCard';
import { FeatureFilters } from './components/FeatureFilters';
import { FeatureTable } from './components/FeatureTable';
import { ProposalDetailCard } from './components/ProposalDetailCard';
import { ProposalFilters } from './components/ProposalFilters';
import { ProposalTable } from './components/ProposalTable';
import { ALL_PROJECTS } from './constants';
import { useProductResearchSnapshot } from './hooks/useProductResearchSnapshot';
import type {
  ProposalFilter,
  ReviewActionState,
  ReviewActionStatus,
} from './types';
import {
  getFeatureEmptyMessage,
  getPageCount,
  getProjectOptions,
  getProposalEmptyMessage,
  getProposalSummaryCounts,
  getVisiblePage,
  matchesProjectFilter,
} from './utils';

export default function ProductResearchPage() {
  const { t } = useTranslation();
  const location = useLocation();
  const navigate = useNavigate();
  const { featureId, proposalId } = useParams<{
    featureId?: string;
    proposalId?: string;
  }>();
  const { features, isLoading, loadError, proposals, reloadSnapshot } =
    useProductResearchSnapshot();
  const [proposalFilter, setProposalFilter] = useState<ProposalFilter>('proposed');
  const proposalFilterSelectedRef = useRef(false);
  const [proposalProjectFilter, setProposalProjectFilter] =
    useState<string>(ALL_PROJECTS);
  const [featureProjectFilter, setFeatureProjectFilter] =
    useState<string>(ALL_PROJECTS);
  const [proposalPage, setProposalPage] = useState(1);
  const [featurePage, setFeaturePage] = useState(1);
  const [activeReview, setActiveReview] = useState<ReviewActionState>(null);
  const [recoveringPlanningProposalId, setRecoveringPlanningProposalId] = useState<string | null>(null);

  const isFeatureRoute = location.pathname.startsWith('/product-research/features');
  const viewMode = isFeatureRoute ? 'features' : 'proposals';
  const proposalSummaryCounts = getProposalSummaryCounts(proposals);

  function handleReviewPendingProposals(): void {
    setProposalFilter('proposed');
    setProposalPage(1);
    navigate('/product-research', { replace: true });
  }

  const statusFilteredProposals = proposals.filter(proposal => {
    if (proposalFilter === 'all') {
      return true;
    }
    if (proposalFilter === 'accepted') {
      return (
        proposal.status === 'approved' ||
        proposal.status === 'planned' ||
        proposal.status === 'completed'
      );
    }
    return proposal.status === proposalFilter;
  });
  const proposalProjectOptions = getProjectOptions(statusFilteredProposals, t);
  const activeProposalProjectFilter =
    proposalProjectFilter === ALL_PROJECTS ||
    proposalProjectOptions.some(option => option.value === proposalProjectFilter)
      ? proposalProjectFilter
      : ALL_PROJECTS;
  const filteredProposals = statusFilteredProposals.filter(proposal =>
    matchesProjectFilter(proposal.project, activeProposalProjectFilter),
  );
  const proposalPageCount = getPageCount(filteredProposals.length);
  const activeProposalPage = Math.min(proposalPage, proposalPageCount);
  const visibleProposals = getVisiblePage(filteredProposals, activeProposalPage);
  const approvalInboxStats = [
    { key: 'pending', value: proposalSummaryCounts.proposed, onClick: handleReviewPendingProposals },
    { key: 'accepted', value: proposalSummaryCounts.accepted },
    { key: 'rejected', value: proposalSummaryCounts.rejected },
  ];

  const trackedFeatures = (() => {
    const activeFeatures = features.filter(feature => feature.status !== 'closed');
    return activeFeatures.length > 0 ? activeFeatures : features;
  })();
  const featureProjectOptions = getProjectOptions(trackedFeatures, t);
  const activeFeatureProjectFilter =
    featureProjectFilter === ALL_PROJECTS ||
    featureProjectOptions.some(option => option.value === featureProjectFilter)
      ? featureProjectFilter
      : ALL_PROJECTS;
  const filteredFeatures = trackedFeatures.filter(feature =>
    matchesProjectFilter(feature.project, activeFeatureProjectFilter),
  );
  const featurePageCount = getPageCount(filteredFeatures.length);
  const activeFeaturePage = Math.min(featurePage, featurePageCount);
  const visibleFeatures = getVisiblePage(filteredFeatures, activeFeaturePage);

  const selectedProposal = proposals.find(proposal => proposal.id === proposalId) ?? null;
  const selectedProposalFeatures = proposalId
    ? features.filter(feature => feature.proposal_id === proposalId)
    : [];
  const selectedFeature = features.find(feature => feature.id === featureId) ?? null;

  useEffect(() => {
    if (proposalFilterSelectedRef.current || proposalId || proposals.length === 0) {
      return;
    }

    if (!proposals.some(proposal => proposal.status === 'proposed')) {
      setProposalFilter('accepted');
    }
  }, [proposalId, proposals]);

  useEffect(() => {
    if (viewMode !== 'proposals') {
      return;
    }

    if (proposalId && selectedProposal?.status === 'rejected') {
      setProposalFilter('rejected');
      return;
    }

    if (
      proposalId &&
      (selectedProposal?.status === 'approved' ||
        selectedProposal?.status === 'planned' ||
        selectedProposal?.status === 'completed')
    ) {
      setProposalFilter('accepted');
      return;
    }

    if (proposalId && selectedProposal?.status === 'proposed') {
      setProposalFilter('proposed');
    }
  }, [proposalId, selectedProposal, viewMode]);

  useEffect(() => {
    setProposalPage(1);
  }, [proposalFilter, proposalProjectFilter]);

  useEffect(() => {
    setFeaturePage(1);
  }, [featureProjectFilter]);

  async function handleReview(
    currentProposalId: string,
    status: ReviewActionStatus,
  ): Promise<void> {
    startTransition(() => {
      setActiveReview({ proposalId: currentProposalId, status });
    });

    try {
      await updateProductProposalStatus(currentProposalId, { status });
      toast.success(
        status === 'approved'
          ? t('productResearch.requirementApprovedPlanningStarted')
          : t('productResearch.requirementRejected'),
      );
      await reloadSnapshot('mutation');
      setProposalFilter(status === 'approved' ? 'accepted' : 'rejected');
    } catch (error) {
      toast.error(t('productResearch.updateProposalFailed'), {
        description: getErrorDetail(error, t('productResearch.updateProposalFailedDescription')),
      });
    } finally {
      startTransition(() => {
        setActiveReview(null);
      });
    }
  }

  async function handleRecoverPlanning(currentProposalId: string): Promise<void> {
    startTransition(() => {
      setRecoveringPlanningProposalId(currentProposalId);
    });

    try {
      await retryProductProposalPlanning(currentProposalId);
      toast.success(t('productResearch.planningRecoverStarted'));
      await reloadSnapshot('mutation');
    } catch (error) {
      toast.error(t('productResearch.planningRecoverFailed'), {
        description: getErrorDetail(
          error,
          t('productResearch.planningRecoverFailedDescription'),
        ),
      });
    } finally {
      startTransition(() => {
        setRecoveringPlanningProposalId(null);
      });
    }
  }

  useAppLayout({
    title: t('productResearch.title'),
    description: t('productResearch.description'),
  });

  if (proposalId && !isLoading && !selectedProposal) {
    return <Navigate to="/product-research" replace />;
  }

  if (featureId && !isLoading && !selectedFeature) {
    return <Navigate to="/product-research/features" replace />;
  }

  if (proposalId) {
    return (
      <div className="flex flex-col gap-4">
        <div className="flex items-center gap-2">
          <Button asChild variant="ghost" size="sm">
            <Link to="/product-research">{t('productResearch.backToRequirements')}</Link>
          </Button>
        </div>

        {isLoading || !selectedProposal ? (
          <LoadingPanel message={t('productResearch.loadingProposal')} />
        ) : (
          <ProposalDetailCard
            proposal={selectedProposal}
            relatedFeatures={selectedProposalFeatures}
            activeReview={activeReview}
            onReview={handleReview}
            onRecoverPlanning={handleRecoverPlanning}
            recoveringPlanning={recoveringPlanningProposalId === selectedProposal.id}
          />
        )}
      </div>
    );
  }

  if (featureId) {
    return (
      <div className="flex flex-col gap-4">
        <div className="flex items-center gap-2">
          <Button asChild variant="ghost" size="sm">
            <Link to="/product-research/features">{t('productResearch.backToFeatures')}</Link>
          </Button>
        </div>

        {isLoading || !selectedFeature ? (
          <LoadingPanel message={t('productResearch.loadingFeature')} />
        ) : (
          <FeatureDetailCard feature={selectedFeature} />
        )}
      </div>
    );
  }

  return (
    <section className="flex flex-col gap-6">
      {viewMode === 'proposals' ? (
        <div className="flex flex-col gap-4">
          <section className="border-y px-1 py-3">
            <dl className="grid gap-6 sm:grid-cols-3">
              {approvalInboxStats.map(({ key, value, onClick }) => (
                <button
                  key={key}
                  type="button"
                  className="border-l px-4 py-2 text-left transition-colors hover:border-primary hover:text-primary"
                  onClick={onClick}
                >
                  <dt className="text-muted-foreground text-sm font-medium">
                    {t(`productResearch.approvalInbox.${key}`)}
                  </dt>
                  <dd className="mt-2 text-3xl font-semibold">{value}</dd>
                </button>
              ))}
            </dl>
          </section>

          <ProposalFilters
            proposalFilter={proposalFilter}
            projectFilter={activeProposalProjectFilter}
            projectOptions={proposalProjectOptions}
            onProposalFilterChange={filter => {
              proposalFilterSelectedRef.current = true;
              setProposalFilter(filter);
            }}
            onProjectFilterChange={setProposalProjectFilter}
          />

          {isLoading ? (
            <LoadingPanel message={t('productResearch.loadingRequirements')} />
          ) : filteredProposals.length === 0 ? (
            <EmptyPanel
              message={getProposalEmptyMessage({
                loadError,
                proposalFilter,
                activeProjectFilter: activeProposalProjectFilter,
                t,
              })}
            />
          ) : (
            <ProposalTable
              page={activeProposalPage}
              pageCount={proposalPageCount}
              proposals={visibleProposals}
              totalCount={filteredProposals.length}
              onSelect={currentProposalId =>
                navigate(`/product-research/proposals/${currentProposalId}`)
              }
              onPageChange={setProposalPage}
            />
          )}
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          <FeatureFilters
            projectFilter={activeFeatureProjectFilter}
            projectOptions={featureProjectOptions}
            onProjectFilterChange={setFeatureProjectFilter}
          />

          {isLoading ? (
            <LoadingPanel message={t('productResearch.loadingFeatures')} />
          ) : filteredFeatures.length === 0 ? (
            <EmptyPanel
              message={getFeatureEmptyMessage({
                loadError,
                activeProjectFilter: activeFeatureProjectFilter,
                t,
              })}
            />
          ) : (
            <FeatureTable
              features={visibleFeatures}
              page={activeFeaturePage}
              pageCount={featurePageCount}
              totalCount={filteredFeatures.length}
              onSelect={currentFeatureId =>
                navigate(`/product-research/features/${currentFeatureId}`)
              }
              onPageChange={setFeaturePage}
            />
          )}
        </div>
      )}
    </section>
  );
}
