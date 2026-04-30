import type { ApiVirtualPullRequestComment, ApiVirtualPullRequestThread } from '@/api/types';
import { MarkdownContent } from '@/components/ui/markdown-content';
import { timeAgo } from '../utils/status';
import {
  buildSuggestionDiffRaw,
  extractCommentSuggestion,
  parseThreadSnippetHunk,
} from '../utils/threadUtils';
import type { ThreadCommentNode } from '../utils/types';
import { CommentActionMenu } from './CommentActionMenu';
import { MiniDiffPreview } from './MiniDiffPreview';
import { ThreadReplyComposer } from './ThreadReplyComposer';
import { VerticalConnector } from './VerticalConnector';

type ThreadCommentTreeNodeProps = {
  node: ThreadCommentNode;
  thread: ApiVirtualPullRequestThread;
  depth: number;
  snapshotSourceLines: string[];
  replyValue: string;
  activeReplyTargetCommentId?: string | null;
  isSavingReply: boolean;
  onCancelReply: () => void;
  onReplyChange: (value: string) => void;
  onSubmitReply: () => void;
  onSelectReply?: (comment: ApiVirtualPullRequestComment) => void;
};

export function ThreadCommentTreeNode({
  node,
  thread,
  depth,
  snapshotSourceLines,
  replyValue,
  activeReplyTargetCommentId,
  isSavingReply,
  onCancelReply,
  onReplyChange,
  onSubmitReply,
  onSelectReply,
}: ThreadCommentTreeNodeProps) {
  const { message, suggestionCode, diffBlock } = extractCommentSuggestion(node.comment.body);
  const suggestionDiffRaw = diffBlock ?? (
    suggestionCode
      ? buildSuggestionDiffRaw(snapshotSourceLines, suggestionCode)
      : null
  );
  const suggestionHunk = suggestionDiffRaw
    ? parseThreadSnippetHunk(
      {
        filePath: thread.file_path,
        diffHunk: thread.diff_hunk,
      },
      suggestionDiffRaw,
    )
    : null;
  const isReplyTarget = activeReplyTargetCommentId === node.comment.id;
  const content = (
    <>
      <div className="rounded-md bg-background">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
              <span className="font-semibold text-foreground">{node.comment.author ?? 'Anonymous'}</span>
              <span>commented {timeAgo(node.comment.created_at)}</span>
            </div>
          </div>
          {onSelectReply ? (
            <CommentActionMenu onQuoteReply={() => onSelectReply(node.comment)} />
          ) : null}
        </div>
        {message ? (
          <MarkdownContent content={message} className="mt-2" />
        ) : null}
        {suggestionHunk ? (
          <MiniDiffPreview hunk={suggestionHunk} className="mt-3" />
        ) : null}
      </div>
      {node.children.length > 0 ? (
        <div className="mt-3 space-y-4">
          {node.children.map(child => (
            <ThreadCommentTreeNode
              key={child.comment.id}
              node={child}
              thread={thread}
              depth={depth + 1}
              snapshotSourceLines={snapshotSourceLines}
              replyValue={replyValue}
              activeReplyTargetCommentId={activeReplyTargetCommentId}
              isSavingReply={isSavingReply}
              onCancelReply={onCancelReply}
              onReplyChange={onReplyChange}
              onSubmitReply={onSubmitReply}
              onSelectReply={onSelectReply}
            />
          ))}
        </div>
      ) : null}
      {isReplyTarget ? (
        <VerticalConnector className="mt-3 pl-4">
          <ThreadReplyComposer
            replyValue={replyValue}
            isSavingReply={isSavingReply}
            onCancel={onCancelReply}
            onReplyChange={onReplyChange}
            onSubmitReply={onSubmitReply}
            placeholder="Reply to this comment…"
            quotedComment={node.comment}
            className="rounded-md border bg-background"
          />
        </VerticalConnector>
      ) : null}
    </>
  );

  return depth > 0 ? <VerticalConnector className="pl-4">{content}</VerticalConnector> : content;
}
