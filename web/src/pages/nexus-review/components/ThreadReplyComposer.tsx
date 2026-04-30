import { Loader2 } from 'lucide-react';
import type { ApiVirtualPullRequestComment } from '@/api/types';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';
import { summarizeQuotedComment } from '../utils/threadUtils';

type ThreadReplyComposerProps = {
  replyValue: string;
  isSavingReply: boolean;
  onCancel: () => void;
  onReplyChange: (value: string) => void;
  onSubmitReply: () => void;
  placeholder: string;
  quotedComment?: ApiVirtualPullRequestComment | null;
  className?: string;
};

export function ThreadReplyComposer({
  replyValue,
  isSavingReply,
  onCancel,
  onReplyChange,
  onSubmitReply,
  placeholder,
  quotedComment,
  className,
}: ThreadReplyComposerProps) {
  const quotedPreview = quotedComment ? summarizeQuotedComment(quotedComment) : null;

  return (
    <div className={cn('bg-muted/15 px-4 py-3', className)}>
      {quotedComment ? (
        <div className="mb-3 rounded-md border bg-background px-3 py-2.5">
          <div className="text-xs font-semibold text-foreground">
            Replying to {quotedComment.author ?? 'Anonymous'}
          </div>
          {quotedPreview ? (
            <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{quotedPreview}</p>
          ) : null}
        </div>
      ) : null}
      <Textarea
        rows={quotedComment ? 3 : 2}
        value={replyValue}
        onChange={event => onReplyChange(event.target.value)}
        placeholder={placeholder}
        autoFocus={Boolean(quotedComment)}
        indentOnTab
      />
      <div className="mt-2 flex justify-end gap-2">
        <Button type="button" size="sm" variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={onSubmitReply}
          disabled={!replyValue.trim() || isSavingReply}
        >
          {isSavingReply ? <Loader2 className="size-3 animate-spin" /> : null}
          Reply
        </Button>
      </div>
    </div>
  );
}
