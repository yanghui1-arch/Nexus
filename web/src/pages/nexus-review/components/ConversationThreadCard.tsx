import { useMemo } from 'react';
import { sortByCreatedAt } from '../utils/display';
import { useThreadSnapshotData } from '../hooks/useThreadSnapshotData';
import { buildThreadCommentTree, threadLineLabel } from '../utils/threadUtils';
import type { ThreadCardProps } from '../utils/types';
import { MiniDiffPreview } from './MiniDiffPreview';
import { ThreadCommentTreeNode } from './ThreadCommentTreeNode';
import { ThreadReplyComposer } from './ThreadReplyComposer';

export function ConversationThreadCard({
  thread,
  replyValue,
  replyTargetCommentId,
  isSavingReply,
  onCancel,
  onReplyChange,
  onSubmitReply,
  onSelectReply,
  onOpenFile,
}: ThreadCardProps) {
  const orderedComments = useMemo(
    () => sortByCreatedAt(thread.comments),
    [thread.comments],
  );
  const { snapshotHunk, fallbackSnapshotLines, snapshotSourceLines } = useThreadSnapshotData(thread);
  const commentTree = useMemo(
    () => buildThreadCommentTree(orderedComments),
    [orderedComments],
  );
  const hasReplyTarget = Boolean(
    replyTargetCommentId &&
    orderedComments.some(comment => comment.id === replyTargetCommentId),
  );

  return (
    <div className="overflow-hidden rounded-md border bg-background">
      <div className="border-b bg-muted/35 px-4 py-2.5">
        <div className="flex min-w-0 flex-wrap items-center gap-2 text-sm">
          {onOpenFile && thread.file_path ? (
            <button
              type="button"
              onClick={onOpenFile}
              className="truncate font-mono text-xs text-primary underline underline-offset-2 hover:text-primary/80"
            >
              {threadLineLabel(thread)}
            </button>
          ) : (
            <span className="truncate font-mono text-xs text-muted-foreground">
              {threadLineLabel(thread)}
            </span>
          )}
        </div>
      </div>
      {snapshotHunk ? (
        <div className="border-b bg-muted/10 px-4 py-3">
          <MiniDiffPreview hunk={snapshotHunk} />
        </div>
      ) : fallbackSnapshotLines.length > 0 ? (
        <div className="border-b bg-muted/10 px-4 py-3">
          <div className="overflow-hidden rounded-md border bg-background">
            <div className="overflow-x-auto py-2 font-mono text-xs">
              {fallbackSnapshotLines.map((line, index) => (
                <div
                  key={index}
                  className="grid min-w-max grid-cols-[64px_minmax(0,1fr)] leading-5"
                >
                  <div className="select-none border-r px-3 text-right text-muted-foreground/80">
                    {thread.start_line == null ? '' : thread.start_line + index}
                  </div>
                  <pre className="px-3 whitespace-pre text-foreground">{line || ' '}</pre>
                </div>
              ))}
            </div>
          </div>
        </div>
      ) : null}
      <div className="px-4 py-4">
        <div className="space-y-4">
          {commentTree.map(node => (
            <ThreadCommentTreeNode
              key={node.comment.id}
              node={node}
              thread={thread}
              depth={0}
              snapshotSourceLines={snapshotSourceLines}
              replyValue={replyValue}
              activeReplyTargetCommentId={hasReplyTarget ? replyTargetCommentId : null}
              isSavingReply={isSavingReply}
              onCancelReply={onCancel}
              onReplyChange={onReplyChange}
              onSubmitReply={onSubmitReply}
              onSelectReply={onSelectReply}
            />
          ))}
        </div>
      </div>
      {!hasReplyTarget ? (
        <ThreadReplyComposer
          replyValue={replyValue}
          isSavingReply={isSavingReply}
          onCancel={onCancel}
          onReplyChange={onReplyChange}
          onSubmitReply={onSubmitReply}
          placeholder="Reply to this thread…"
          className="border-t"
        />
      ) : null}
    </div>
  );
}
