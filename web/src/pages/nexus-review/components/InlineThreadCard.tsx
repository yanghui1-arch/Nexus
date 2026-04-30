import { useMemo } from 'react';
import { sortByCreatedAt } from '../utils/display';
import { useThreadSnapshotData } from '../hooks/useThreadSnapshotData';
import { buildThreadCommentTree } from '../utils/threadUtils';
import type { ThreadCardProps } from '../utils/types';
import { ThreadCommentTreeNode } from './ThreadCommentTreeNode';
import { ThreadReplyComposer } from './ThreadReplyComposer';

export function InlineThreadCard({
  thread,
  replyValue,
  replyTargetCommentId,
  isSavingReply,
  onCancel,
  onReplyChange,
  onSubmitReply,
  onSelectReply,
}: ThreadCardProps) {
  const orderedComments = useMemo(
    () => sortByCreatedAt(thread.comments),
    [thread.comments],
  );
  const { snapshotSourceLines } = useThreadSnapshotData(thread);
  const commentTree = useMemo(
    () => buildThreadCommentTree(orderedComments),
    [orderedComments],
  );
  const hasReplyTarget = Boolean(
    replyTargetCommentId &&
    orderedComments.some(comment => comment.id === replyTargetCommentId),
  );

  return (
    <div className="w-[48rem] max-w-[calc(100vw-18rem)] overflow-hidden rounded-md border bg-background">
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
