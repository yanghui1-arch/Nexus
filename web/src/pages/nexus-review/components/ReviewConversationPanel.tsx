import { useMemo } from 'react';
import {
  Archive,
  CheckCircle2,
  MessageSquare,
  RotateCcw,
} from 'lucide-react';
import type {
  ApiVirtualPullRequestDetail,
  ApiVirtualPullRequestReview,
  ApiVirtualPullRequestThread,
} from '@/api/types';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { MarkdownContent } from '@/components/ui/markdown-content';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Textarea } from '@/components/ui/textarea';
import { REVIEW_DECISION_LABEL, REVIEW_STATUS_META } from '../utils/constants';
import { createdAtTimestamp, shortCommit } from '../utils/display';
import { timeAgo } from '../utils/status';
import { ConversationThreadCard } from './ConversationThreadCard';
import { VerticalConnector } from './VerticalConnector';

type ReviewConversationPanelProps = {
  detail: ApiVirtualPullRequestDetail;
  conversationThreads: ApiVirtualPullRequestThread[];
  replyDrafts: Record<string, string>;
  replyTargetCommentIds: Record<string, string | null>;
  savingReplyThreadId: string | null;
  threadAuthor: string;
  threadBody: string;
  isSavingThread: boolean;
  onThreadAuthorChange: (value: string) => void;
  onThreadBodyChange: (value: string) => void;
  onResetReplyComposer: (threadId: string) => void;
  onReplyDraftChange: (threadId: string, value: string) => void;
  onSubmitReply: (thread: ApiVirtualPullRequestThread) => void;
  onSelectReplyTarget: (threadId: string, commentId: string) => void;
  onOpenThreadFile: (thread: ApiVirtualPullRequestThread) => void;
  onSubmitGeneralThread: () => void;
};

type ReviewTimelineItem =
  | {
      kind: 'review';
      activityAt: string;
      review: ApiVirtualPullRequestReview;
    }
  | {
      kind: 'thread';
      activityAt: string;
      thread: ApiVirtualPullRequestThread;
    };

function reviewActivityIcon(decision: ApiVirtualPullRequestReview['decision']) {
  if (decision === 'approved') {
    return <CheckCircle2 className="size-4 text-violet-600" />;
  }
  if (decision === 'closed') {
    return <Archive className="size-4 text-red-600" />;
  }
  if (decision === 'reopened') {
    return <RotateCcw className="size-4 text-emerald-600" />;
  }
  return <MessageSquare className="size-4 text-muted-foreground" />;
}

function timelineMarker(item: ReviewTimelineItem) {
  if (item.kind === 'review') {
    return reviewActivityIcon(item.review.decision);
  }
  return <MessageSquare className="size-4 text-muted-foreground" />;
}

export function ReviewConversationPanel({
  detail,
  conversationThreads,
  replyDrafts,
  replyTargetCommentIds,
  savingReplyThreadId,
  threadAuthor,
  threadBody,
  isSavingThread,
  onThreadAuthorChange,
  onThreadBodyChange,
  onResetReplyComposer,
  onReplyDraftChange,
  onSubmitReply,
  onSelectReplyTarget,
  onOpenThreadFile,
  onSubmitGeneralThread,
}: ReviewConversationPanelProps) {
  const fileCount = detail.virtual_pr.changed_files.length;
  const timelineItems = useMemo<ReviewTimelineItem[]>(() => {
    const reviewItems: ReviewTimelineItem[] = detail.reviews.map(review => ({
      kind: 'review',
      activityAt: review.created_at,
      review,
    }));
    const threadItems: ReviewTimelineItem[] = conversationThreads.map(thread => ({
      kind: 'thread',
      activityAt: thread.comments.reduce((latest, comment) => {
        return createdAtTimestamp(comment.created_at) > createdAtTimestamp(latest)
          ? comment.created_at
          : latest;
      }, thread.created_at),
      thread,
    }));
    return [...reviewItems, ...threadItems].sort(
      (left, right) => createdAtTimestamp(left.activityAt) - createdAtTimestamp(right.activityAt),
    );
  }, [conversationThreads, detail.reviews]);

  return (
    <ScrollArea className="min-h-0 flex-1">
      <div className="mx-auto grid max-w-[1400px] gap-6 px-6 py-6 lg:grid-cols-[minmax(0,1fr)_300px]">
        <div className="space-y-4">
          <div className="overflow-hidden rounded-md border bg-background">
            <div className="border-b bg-muted/35 px-4 py-2.5 text-sm font-semibold">
              Pull request summary
            </div>
            <div className="px-4 py-4">
              <MarkdownContent
                content={detail.virtual_pr.summary || detail.work_item.description}
                emptyState="No summary provided."
              />
            </div>
          </div>

          {timelineItems.length > 0 ? (
            <VerticalConnector className="space-y-4 pl-11" lineClassName="left-4 top-5 bottom-5">
              {timelineItems.map(item => {
                const key = item.kind === 'review' ? item.review.id : item.thread.id;

                if (item.kind === 'review') {
                  const { review } = item;
                  return (
                    <div key={key} className="relative">
                      <div className="absolute top-1 left-[-44px] z-10 flex size-8 shrink-0 items-center justify-center rounded-full border bg-background shadow-sm">
                        {timelineMarker(item)}
                      </div>
                      <div className="min-w-0 overflow-hidden rounded-md border bg-background">
                        <div className="border-b bg-muted/35 px-4 py-2.5 text-sm">
                          <span className="font-semibold">{review.reviewer ?? 'Anonymous reviewer'}</span>{' '}
                          <span className="text-muted-foreground">
                            {REVIEW_DECISION_LABEL[review.decision]} {timeAgo(review.created_at)}
                          </span>
                        </div>
                        {review.comment ? (
                          <div className="px-4 py-3">
                            <MarkdownContent content={review.comment} />
                          </div>
                        ) : null}
                      </div>
                    </div>
                  );
                }

                const { thread } = item;
                return (
                  <div key={key} className="relative">
                    <div className="absolute top-1 left-[-44px] z-10 flex size-8 shrink-0 items-center justify-center rounded-full border bg-background shadow-sm">
                      {timelineMarker(item)}
                    </div>
                    <ConversationThreadCard
                      thread={thread}
                      replyValue={replyDrafts[thread.id] ?? ''}
                      replyTargetCommentId={replyTargetCommentIds[thread.id] ?? null}
                      isSavingReply={savingReplyThreadId === thread.id}
                      onCancel={() => onResetReplyComposer(thread.id)}
                      onReplyChange={value => onReplyDraftChange(thread.id, value)}
                      onSubmitReply={() => onSubmitReply(thread)}
                      onSelectReply={comment => onSelectReplyTarget(thread.id, comment.id)}
                      onOpenFile={
                        thread.kind === 'inline'
                          ? () => onOpenThreadFile(thread)
                          : undefined
                      }
                    />
                  </div>
                );
              })}
            </VerticalConnector>
          ) : null}

          <div className="overflow-hidden rounded-md border bg-background">
            <div className="border-b bg-muted/35 px-4 py-2.5 text-sm font-semibold">
              Add to conversation
            </div>
            <div className="space-y-3 px-4 py-4">
              <Input
                value={threadAuthor}
                onChange={event => onThreadAuthorChange(event.target.value)}
                placeholder="Your name (optional)"
              />
              <Textarea
                rows={5}
                value={threadBody}
                onChange={event => onThreadBodyChange(event.target.value)}
                placeholder="Leave a comment…"
                indentOnTab
              />
              <div className="flex justify-end">
                <Button
                  type="button"
                  onClick={onSubmitGeneralThread}
                  disabled={!threadBody.trim() || isSavingThread}
                >
                  Comment
                </Button>
              </div>
            </div>
          </div>
        </div>

        <aside className="space-y-4">
          <div className="rounded-md border bg-background">
            <div className="border-b px-4 py-3 text-sm font-semibold">Details</div>
            <div className="space-y-3 px-4 py-4 text-sm">
              <div className="flex items-center justify-between gap-3">
                <span className="text-muted-foreground">Status</span>
                <Badge
                  variant={REVIEW_STATUS_META[detail.virtual_pr.status].badgeVariant}
                  className={REVIEW_STATUS_META[detail.virtual_pr.status].badgeClassName}
                >
                  {REVIEW_STATUS_META[detail.virtual_pr.status].label}
                </Badge>
              </div>
              <div className="flex items-center justify-between gap-3">
                <span className="text-muted-foreground">Agent</span>
                <span className="font-mono text-xs">{detail.task.agent}</span>
              </div>
              <div className="flex items-center justify-between gap-3">
                <span className="text-muted-foreground">Repo</span>
                <span className="truncate font-mono text-xs">{detail.task.repo ?? '—'}</span>
              </div>
              <div className="flex items-center justify-between gap-3">
                <span className="text-muted-foreground">Range</span>
                <code className="rounded bg-muted px-1.5 py-0.5 text-xs">
                  {shortCommit(detail.virtual_pr.base_commit)}..{shortCommit(detail.virtual_pr.head_commit)}
                </code>
              </div>
              <div className="flex items-center justify-between gap-3">
                <span className="text-muted-foreground">Files changed</span>
                <span>{fileCount}</span>
              </div>
              <div className="flex items-center justify-between gap-3">
                <span className="text-muted-foreground">Diff</span>
                <span className="font-mono text-xs">
                  <span className="text-emerald-600">+{detail.virtual_pr.additions}</span>
                  {' / '}
                  <span className="text-red-600">-{detail.virtual_pr.deletions}</span>
                </span>
              </div>
            </div>
          </div>
        </aside>
      </div>
    </ScrollArea>
  );
}
