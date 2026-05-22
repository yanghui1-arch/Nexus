import type { TFunction } from 'i18next';
import { getProductFeature, listProductFeatures, listProductProposals } from '@/api/product';
import type { ApiFeatureItem, ApiProductProposal, ApiTask } from '@/api/types';
import { ALL_PROJECTS, NO_PROJECT, PAGE_SIZE } from './constants';
import type {
  ProductResearchSnapshot,
  ProjectOption,
  ProposalPlanningDisplayStatus,
  ProposalFilter,
} from './types';

export function getTaskPullRequestUrl(task: ApiTask | null | undefined): string | null {
  return task?.external_pull_request_url ?? null;
}

export async function loadProductResearchSnapshot(): Promise<ProductResearchSnapshot> {
  const [proposals, featureSummaries] = await Promise.all([
    listProductProposals({ limit: 300 }),
    listProductFeatures({ limit: 200 }),
  ]);
  // The list endpoint does not include feature items, so hydrate each feature for live progress tracking.
  const features = await Promise.all(
    featureSummaries.map(feature => getProductFeature(feature.id)),
  );

  return {
    proposals: sortByNewest(proposals),
    features: sortByNewest(features),
  };
}

export function sortByNewest<T extends { updated_at: string; created_at: string }>(
  records: T[],
): T[] {
  return [...records].sort(
    (left, right) =>
      Date.parse(right.updated_at || right.created_at) -
      Date.parse(left.updated_at || left.created_at),
  );
}

export function formatDateTime(value: string | null): string {
  if (!value) {
    return '-';
  }

  const timestamp = Date.parse(value);
  if (Number.isNaN(timestamp)) {
    return '-';
  }

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(timestamp);
}

export function formatRelativeTime(value: string | null): string {
  if (!value) {
    return 'unknown';
  }

  const timestamp = Date.parse(value);
  if (Number.isNaN(timestamp)) {
    return 'unknown';
  }

  const deltaMs = Date.now() - timestamp;
  const minuteMs = 60_000;
  const hourMs = 60 * minuteMs;
  const dayMs = 24 * hourMs;

  if (deltaMs < minuteMs) {
    return 'just now';
  }
  if (deltaMs < hourMs) {
    return `${Math.round(deltaMs / minuteMs)}m ago`;
  }
  if (deltaMs < dayMs) {
    return `${Math.round(deltaMs / hourMs)}h ago`;
  }
  return `${Math.round(deltaMs / dayMs)}d ago`;
}

export function shortId(value: string): string {
  return value.slice(0, 8);
}

export function hasValidatedProposalPlan(proposal: ApiProductProposal): boolean {
  return proposal.status === 'planned' || proposal.status === 'completed';
}

export function getProposalPlanningDisplayStatus(
  proposal: ApiProductProposal,
): ProposalPlanningDisplayStatus | null {
  if (proposal.status === 'approved') {
    if (proposal.latest_planning_run == null) {
      return 'missing_run';
    }
    if (proposal.latest_planning_task_exists === false) {
      return 'missing_task';
    }
    return proposal.latest_planning_run.status;
  }

  if (hasValidatedProposalPlan(proposal)) {
    return proposal.latest_planning_run?.status ?? 'completed';
  }

  return proposal.latest_planning_run?.status ?? null;
}

export function calculateFeatureCompletion(
  items: ApiFeatureItem[] | null | undefined,
): number {
  if (!items || items.length === 0) {
    return 0;
  }

  const finishedItems = items.filter(
    item => item.status === 'completed' || item.status === 'closed',
  ).length;

  return Math.round((finishedItems / items.length) * 100);
}

export function getProjectFilterValue(project: string | null | undefined): string {
  const normalizedProject = project?.trim();
  return normalizedProject ? normalizedProject : NO_PROJECT;
}

export function getProjectLabel(project: string | null | undefined, t?: TFunction): string {
  const normalizedProject = project?.trim();
  return normalizedProject ? normalizedProject : t ? t('common.noProject') : 'No project';
}

export function getProjectOptions<T extends { project: string | null | undefined }>(
  records: T[],
  t?: TFunction,
): ProjectOption[] {
  return [...new Set(records.map(record => getProjectFilterValue(record.project)))]
    .map(value => ({
      value,
      label: value === NO_PROJECT ? (t ? t('common.noProject') : 'No project') : value,
    }))
    .sort((left, right) => left.label.localeCompare(right.label));
}

export function matchesProjectFilter(
  project: string | null | undefined,
  filter: string,
): boolean {
  return filter === ALL_PROJECTS || getProjectFilterValue(project) === filter;
}

export function getPageCount(total: number): number {
  return Math.max(1, Math.ceil(total / PAGE_SIZE));
}

export function getVisiblePage<T>(records: T[], page: number): T[] {
  const start = (page - 1) * PAGE_SIZE;
  return records.slice(start, start + PAGE_SIZE);
}

export function getProposalEmptyMessage({
  loadError,
  proposalFilter,
  activeProjectFilter,
  t,
}: {
  loadError: string | null;
  proposalFilter: ProposalFilter;
  activeProjectFilter: string;
  t: TFunction;
}): string {
  if (loadError) {
    return loadError;
  }

  if (activeProjectFilter !== ALL_PROJECTS) {
    return t('productResearch.emptyRequirementsProject');
  }

  if (proposalFilter === 'proposed') {
    return t('productResearch.emptyRequirementsPending');
  }
  if (proposalFilter === 'accepted') {
    return t('productResearch.emptyRequirementsAccepted');
  }
  if (proposalFilter === 'rejected') {
    return t('productResearch.emptyRequirementsRejected');
  }

  return t('productResearch.emptyRequirements');
}

export function getFeatureEmptyMessage({
  loadError,
  activeProjectFilter,
  t,
}: {
  loadError: string | null;
  activeProjectFilter: string;
  t: TFunction;
}): string {
  if (loadError) {
    return loadError;
  }

  if (activeProjectFilter !== ALL_PROJECTS) {
    return t('productResearch.emptyFeaturesProject');
  }

  return t('productResearch.emptyFeatures');
}
