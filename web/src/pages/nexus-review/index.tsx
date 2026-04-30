import type { NexusReviewPageProps } from './utils/types';
import { PullRequestDetailPage } from './pages/PullRequestDetailPage';
import { ReviewQueuePage } from './pages/ReviewQueuePage';
import { TaskReviewSummaryPage } from './pages/TaskReviewSummaryPage';

export function NexusReviewPage({ mode }: NexusReviewPageProps) {
  if (mode === 'queue') {
    return <ReviewQueuePage />;
  }
  if (mode === 'task') {
    return <TaskReviewSummaryPage />;
  }
  return <PullRequestDetailPage />;
}
