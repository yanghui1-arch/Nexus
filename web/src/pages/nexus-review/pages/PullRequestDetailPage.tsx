import { startTransition, useState } from 'react';
import {
  Archive,
  ArrowLeft,
  CheckCircle2,
  ExternalLink,
  GitPullRequest,
  Loader2,
  RotateCcw,
} from 'lucide-react';
import { getErrorDetail } from '@/api/client';
import {
  reviewTaskVirtualPullRequest,
} from '@/api/tasks';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import {
  Link,
  Navigate,
} from 'react-router-dom';
import { TAB_OPTIONS, REVIEW_STATUS_META } from '../utils/constants';
import { shortCommit } from '../utils/display';
import { ReviewConversationPanel } from '../components/ReviewConversationPanel';
import { ReviewFilesPanel } from '../components/ReviewFilesPanel';
import { usePullRequestDetailState } from '../hooks/usePullRequestDetailState';

export function PullRequestDetailPage() {
  const {
    taskId,
    virtualPrId,
    detail,
    isLoading,
    error,
    activeTab,
    activeFilePath,
    expandedDirectories,
    selectedLocation,
    threadBody,
    threadAuthor,
    isSelectingLines,
    commentLocation,
    visibleInlineThreadId,
    replyDrafts,
    replyTargetCommentIds,
    isSavingThread,
    savingReplyThreadId,
    parsedDiff,
    activeFile,
    highlightedHunkTokens,
    fileTree,
    conversationThreads,
    threadsByLineKey,
    openThreadCount,
    fileCount,
    reviewCount,
    refreshDetail,
    selectTab,
    setActiveFilePath,
    toggleDirectory,
    setThreadBody,
    setThreadAuthor,
    setIsSelectingLines,
    setCommentLocation,
    resetReplyComposer,
    updateReplyDraft,
    selectReplyTarget,
    submitThread,
    submitReply,
    openThreadFile,
    selectDiffLocation,
    extendDiffSelection,
  } = usePullRequestDetailState();
  const [activeAction, setActiveAction] = useState<'approve' | 'close' | 'reopen' | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  if (!taskId || !virtualPrId) {
    return <Navigate to="/workspace/code-review/nexus" replace />;
  }

  const isClosed = detail?.virtual_pr.status === 'closed';
  const isMerged = detail?.task.status === 'merged';
  const canApprove = Boolean(
    detail &&
      detail.virtual_pr.status === 'ready_for_review' &&
      !isMerged,
  );
  const canToggleClosed = Boolean(detail && !isMerged);

  const handleApprove = async () => {
    if (!detail) {
      return;
    }

    setActiveAction('approve');
    try {
      await reviewTaskVirtualPullRequest(taskId, virtualPrId, { decision: 'approved' });
      await refreshDetail();
      startTransition(() => {
        setActionError(null);
        setActiveAction(null);
      });
    } catch (nextError) {
      startTransition(() => {
        setActionError(getErrorDetail(nextError, 'Failed to approve pull request.'));
        setActiveAction(null);
      });
    }
  };

  const handleToggleClosed = async () => {
    if (!detail) {
      return;
    }

    setActiveAction(isClosed ? 'reopen' : 'close');
    try {
      await reviewTaskVirtualPullRequest(taskId, virtualPrId, {
        decision: isClosed ? 'reopened' : 'closed',
      });
      await refreshDetail();
      startTransition(() => {
        setActionError(null);
        setActiveAction(null);
      });
    } catch (nextError) {
      startTransition(() => {
        setActionError(
          getErrorDetail(
            nextError,
            isClosed ? 'Failed to reopen pull request.' : 'Failed to close pull request.',
          ),
        );
        setActiveAction(null);
      });
    }
  };

  return (
    <div className="min-h-screen bg-[linear-gradient(180deg,hsl(var(--background)),hsl(var(--muted)/0.55))] lg:h-screen lg:overflow-hidden">
      <div className="flex min-h-screen flex-col lg:h-screen">
        <div className="flex min-h-0 flex-1 flex-col overflow-hidden bg-background">
          <div className="shrink-0 border-b bg-muted/25 px-6 py-5">
            <div className="mx-auto max-w-[1400px]">
              <div className="mb-4">
                <Button asChild variant="ghost" size="sm" className="-ml-2">
                  <Link to={`/workspace/code-review/nexus/tasks/${taskId}`}>
                    <ArrowLeft className="size-4" />
                    Back to pull requests
                  </Link>
                </Button>
              </div>
              {isLoading ? (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Loader2 className="size-4 animate-spin" />
                  Loading pull request...
                </div>
              ) : !detail ? (
                <p className="text-sm text-muted-foreground">Pull request detail is unavailable.</p>
              ) : (
                <>
                  <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                    <div className="min-w-0">
                      <h2 className="text-2xl font-semibold leading-tight">
                        {detail.work_item.title}
                      </h2>
                      <div className="mt-3 flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
                        <Badge
                          variant={REVIEW_STATUS_META[detail.virtual_pr.status].badgeVariant}
                          className={cn(
                            'gap-1 rounded-full px-3',
                            REVIEW_STATUS_META[detail.virtual_pr.status].badgeClassName,
                          )}
                        >
                          <GitPullRequest className="size-3.5" />
                          {REVIEW_STATUS_META[detail.virtual_pr.status].label}
                        </Badge>
                        <span>{detail.task.agent} wants to merge</span>
                        <code className="rounded bg-background px-1.5 py-0.5 text-xs">
                          {shortCommit(detail.virtual_pr.head_commit)}
                        </code>
                        <span>into</span>
                        <code className="rounded bg-background px-1.5 py-0.5 text-xs">
                          {shortCommit(detail.virtual_pr.base_commit)}
                        </code>
                      </div>
                    </div>
                    {detail.task.external_issue_url ? (
                      <Button asChild variant="outline" size="sm">
                        <a href={detail.task.external_issue_url} target="_blank" rel="noreferrer">
                          <ExternalLink className="size-4" />
                          Open issue
                        </a>
                      </Button>
                    ) : null}
                  </div>
                  <div className="mt-5 flex flex-wrap items-end justify-between gap-3 border-b">
                    <div className="-mb-px flex items-center gap-5">
                      {TAB_OPTIONS.map(option => (
                        <button
                          key={option.id}
                          type="button"
                          onClick={() => selectTab(option.id)}
                          className={cn(
                            'inline-flex items-center gap-2 border-b-2 px-0 pb-3 text-sm font-medium transition-colors',
                            activeTab === option.id
                              ? 'border-foreground font-semibold text-foreground'
                              : 'border-transparent text-muted-foreground hover:text-foreground',
                          )}
                        >
                          <span>{option.label}</span>
                          <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                            {option.id === 'conversation' ? openThreadCount + reviewCount : fileCount}
                          </span>
                        </button>
                      ))}
                    </div>
                    <div className="flex items-center gap-2 pb-2">
                      {canApprove ? (
                        <Button
                          type="button"
                          size="sm"
                          disabled={activeAction !== null}
                          onClick={() => void handleApprove()}
                        >
                          {activeAction === 'approve' ? (
                            <Loader2 className="size-4 animate-spin" />
                          ) : (
                            <CheckCircle2 className="size-4" />
                          )}
                          Approve
                        </Button>
                      ) : null}
                      {canToggleClosed ? (
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          disabled={activeAction !== null}
                          onClick={() => void handleToggleClosed()}
                        >
                          {activeAction === 'close' || activeAction === 'reopen' ? (
                            <Loader2 className="size-4 animate-spin" />
                          ) : isClosed ? (
                            <RotateCcw className="size-4" />
                          ) : (
                            <Archive className="size-4" />
                          )}
                          {isClosed ? 'Reopen' : 'Close'}
                        </Button>
                      ) : null}
                    </div>
                  </div>
                </>
              )}
            </div>
          </div>

          {error ? (
            <div className="mx-auto w-full max-w-[1400px] px-6 pt-4">
              <p className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                {error}
              </p>
            </div>
          ) : null}
          {actionError ? (
            <div className="mx-auto w-full max-w-[1400px] px-6 pt-4">
              <p className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                {actionError}
              </p>
            </div>
          ) : null}

          {isLoading || !detail ? null : activeTab === 'conversation' ? (
            <ReviewConversationPanel
              detail={detail}
              conversationThreads={conversationThreads}
              replyDrafts={replyDrafts}
              replyTargetCommentIds={replyTargetCommentIds}
              savingReplyThreadId={savingReplyThreadId}
              threadAuthor={threadAuthor}
              threadBody={threadBody}
              isSavingThread={isSavingThread}
              onThreadAuthorChange={setThreadAuthor}
              onThreadBodyChange={setThreadBody}
              onResetReplyComposer={resetReplyComposer}
              onReplyDraftChange={updateReplyDraft}
              onSubmitReply={thread => void submitReply(thread)}
              onSelectReplyTarget={selectReplyTarget}
              onOpenThreadFile={openThreadFile}
              onSubmitGeneralThread={() => void submitThread({ forceGeneral: true })}
            />
          ) : (
            <ReviewFilesPanel
              detail={detail}
              parsedDiff={parsedDiff}
              fileTree={fileTree}
              activeFilePath={activeFilePath}
              expandedDirectories={expandedDirectories}
              activeFile={activeFile}
              highlightedHunkTokens={highlightedHunkTokens}
              selectedLocation={selectedLocation}
              commentLocation={commentLocation}
              visibleInlineThreadId={visibleInlineThreadId}
              replyDrafts={replyDrafts}
              replyTargetCommentIds={replyTargetCommentIds}
              savingReplyThreadId={savingReplyThreadId}
              threadAuthor={threadAuthor}
              threadBody={threadBody}
              isSavingThread={isSavingThread}
              isSelectingLines={isSelectingLines}
              threadsByLineKey={threadsByLineKey}
              onToggleDirectory={toggleDirectory}
              onSelectFile={setActiveFilePath}
              onSetSelectingLines={setIsSelectingLines}
              onSelectDiffLocation={selectDiffLocation}
              onExtendDiffSelection={extendDiffSelection}
              onSetCommentLocation={setCommentLocation}
              onResetReplyComposer={resetReplyComposer}
              onReplyDraftChange={updateReplyDraft}
              onSubmitReply={thread => void submitReply(thread)}
              onSelectReplyTarget={selectReplyTarget}
              onThreadAuthorChange={setThreadAuthor}
              onThreadBodyChange={setThreadBody}
              onSubmitThread={() => void submitThread()}
            />
          )}
        </div>
      </div>
    </div>
  );
}
