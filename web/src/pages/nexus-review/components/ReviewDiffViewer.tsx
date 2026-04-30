import {
  FileCode2,
  Loader2,
} from 'lucide-react';
import type {
  ApiVirtualPullRequestLineSide,
  ApiVirtualPullRequestThread,
} from '@/api/types';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';
import type { ParsedDiffFile } from '@/lib/reviewDiff';
import {
  diffLineGutterClass,
  diffLineRowClass,
  diffLineSymbol,
  diffLineTextClass,
  lineNumberValue,
} from '../utils/display';
import { shikiTokenStyle } from '../utils/highlighting';
import {
  isLineInSelection,
  isSelectionStart,
  locationKey,
} from '../utils/threadUtils';
import type {
  SelectedDiffLocation,
  ShikiToken,
} from '../utils/types';
import { InlineThreadCard } from './InlineThreadCard';

type ReviewDiffViewerProps = {
  activeFile: ParsedDiffFile | null;
  highlightedHunkTokens: Record<string, ShikiToken[][]>;
  selectedLocation: SelectedDiffLocation | null;
  commentLocation: SelectedDiffLocation | null;
  visibleInlineThreadId: string | null;
  replyDrafts: Record<string, string>;
  replyTargetCommentIds: Record<string, string | null>;
  savingReplyThreadId: string | null;
  threadAuthor: string;
  threadBody: string;
  isSavingThread: boolean;
  isSelectingLines: boolean;
  threadsByLineKey: Map<string, ApiVirtualPullRequestThread[]>;
  onSetSelectingLines: (value: boolean) => void;
  onSelectDiffLocation: (location: SelectedDiffLocation) => void;
  onExtendDiffSelection: (location: SelectedDiffLocation) => void;
  onSetCommentLocation: (location: SelectedDiffLocation | null) => void;
  onResetReplyComposer: (threadId: string) => void;
  onReplyDraftChange: (threadId: string, value: string) => void;
  onSubmitReply: (thread: ApiVirtualPullRequestThread) => void;
  onSelectReplyTarget: (threadId: string, commentId: string) => void;
  onThreadAuthorChange: (value: string) => void;
  onThreadBodyChange: (value: string) => void;
  onSubmitThread: () => void;
};

export function ReviewDiffViewer({
  activeFile,
  highlightedHunkTokens,
  selectedLocation,
  commentLocation,
  visibleInlineThreadId,
  replyDrafts,
  replyTargetCommentIds,
  savingReplyThreadId,
  threadAuthor,
  threadBody,
  isSavingThread,
  isSelectingLines,
  threadsByLineKey,
  onSetSelectingLines,
  onSelectDiffLocation,
  onExtendDiffSelection,
  onSetCommentLocation,
  onResetReplyComposer,
  onReplyDraftChange,
  onSubmitReply,
  onSelectReplyTarget,
  onThreadAuthorChange,
  onThreadBodyChange,
  onSubmitThread,
}: ReviewDiffViewerProps) {
  if (!activeFile) {
    return <div className="px-6 py-6 text-sm text-muted-foreground">Select a file to view the diff.</div>;
  }

  return (
    <div className="mx-auto max-w-[1240px] px-6 py-6">
      <div
        className="mb-4 overflow-hidden rounded-xl border border-border/60 bg-background shadow-sm"
        onMouseUp={() => onSetSelectingLines(false)}
        onMouseLeave={() => onSetSelectingLines(false)}
      >
        <div className="flex items-center justify-between gap-3 border-b bg-muted/25 px-4 py-3">
          <div className="flex min-w-0 items-center gap-2">
            <FileCode2 className="size-4 shrink-0 text-muted-foreground" />
            <p className="truncate font-mono text-sm font-medium">{activeFile.displayPath}</p>
          </div>
          <span className="shrink-0 font-mono text-xs text-muted-foreground">
            <span className="text-emerald-600">+{activeFile.additions}</span>
            {' / '}
            <span className="text-red-600">-{activeFile.deletions}</span>
          </span>
        </div>
        {activeFile.hunks.length > 0 ? (
          <div className="space-y-4 p-4">
            {activeFile.hunks.map(hunk => {
              const highlightedLines = highlightedHunkTokens[hunk.id] ?? [];
              return (
                <section
                  key={hunk.id}
                  className="overflow-hidden rounded-lg border border-border/60 bg-background"
                >
                  <div className="bg-[#ddf4ff] px-4 py-2 font-mono text-xs text-blue-800">
                    {hunk.header}
                  </div>
                  <div className="overflow-x-auto">
                    <div className="min-w-full w-max">
                      {hunk.lines.map((line, index) => {
                        const syntaxTokens = line.kind === 'note' ? [] : (highlightedLines[index] ?? []);
                        const hasSyntaxTokens = syntaxTokens.length > 0;
                        const selectable = line.newLineNumber != null || line.oldLineNumber != null;
                        const lineSide: ApiVirtualPullRequestLineSide = line.newLineNumber != null ? 'new' : 'old';
                        const startLine = line.newLineNumber ?? line.oldLineNumber ?? 1;
                        const rowLocation: SelectedDiffLocation = {
                          filePath: activeFile.displayPath,
                          startLine,
                          endLine: startLine,
                          lineSide,
                          diffHunk: hunk.header,
                        };
                        const rowKey = locationKey(rowLocation);
                        const selected = isLineInSelection(rowLocation, selectedLocation);
                        const isFirstSelectedLine = isSelectionStart(rowLocation, selectedLocation);
                        const isCommentingHere = commentLocation ? locationKey(commentLocation) === rowKey : false;
                        const canShowAddComment = selectable && isFirstSelectedLine && !isSelectingLines;
                        const rowThreads = visibleInlineThreadId
                          ? (threadsByLineKey.get(rowKey) ?? []).filter(thread => thread.id === visibleInlineThreadId)
                          : [];

                        return (
                          <div key={`${hunk.id}-${index}`} className="group">
                            <div
                              role="button"
                              tabIndex={selectable ? 0 : -1}
                              className={cn(
                                'relative grid w-full min-w-full grid-cols-[60px_60px_20px_minmax(max-content,1fr)_36px] text-left font-mono text-[12px] leading-6 transition-colors',
                                diffLineRowClass(line.kind),
                                selectable ? 'cursor-pointer hover:brightness-[0.99]' : 'cursor-default',
                                selected
                                  ? 'before:pointer-events-none before:absolute before:inset-y-0 before:left-0 before:z-20 before:w-1 before:bg-[#d4a72c] after:pointer-events-none after:absolute after:inset-0 after:bg-[#fff8c5]/70'
                                  : undefined,
                              )}
                              onMouseDown={event => {
                                if (!selectable || event.button !== 0) {
                                  return;
                                }
                                event.preventDefault();
                                onSetSelectingLines(true);
                                onSelectDiffLocation(rowLocation);
                              }}
                              onMouseEnter={() => {
                                if (!selectable || !isSelectingLines) {
                                  return;
                                }
                                onExtendDiffSelection(rowLocation);
                              }}
                              onMouseUp={() => {
                                onSetSelectingLines(false);
                              }}
                              onClick={event => {
                                if (!selectable) {
                                  return;
                                }
                                event.preventDefault();
                              }}
                              onKeyDown={event => {
                                if (!selectable || (event.key !== 'Enter' && event.key !== ' ')) {
                                  return;
                                }
                                event.preventDefault();
                                onSelectDiffLocation(rowLocation);
                              }}
                              aria-disabled={!selectable}
                            >
                              <div className={cn('relative z-10 px-2 text-right text-[11px] select-none', diffLineGutterClass(line.kind))}>
                                {lineNumberValue(line.oldLineNumber)}
                              </div>
                              <div className={cn('relative z-10 px-2 text-right text-[11px] select-none', diffLineGutterClass(line.kind))}>
                                {lineNumberValue(line.newLineNumber)}
                              </div>
                              <div className={cn('relative z-10 text-center text-[11px] font-semibold select-none', diffLineGutterClass(line.kind))}>
                                {diffLineSymbol(line.kind)}
                              </div>
                              <pre className={cn('relative z-10 px-3 pr-6 whitespace-pre', diffLineTextClass(line.kind))}>
                                {hasSyntaxTokens ? (
                                  syntaxTokens.map((token: ShikiToken, tokenIndex: number) => (
                                    <span key={`${hunk.id}-${index}-${tokenIndex}`} style={shikiTokenStyle(token)}>
                                      {token.content || (tokenIndex === syntaxTokens.length - 1 ? ' ' : '')}
                                    </span>
                                  ))
                                ) : (
                                  line.text || ' '
                                )}
                              </pre>
                              <div
                                className={cn(
                                  'sticky right-0 z-20 flex items-center justify-center px-1 shadow-[-10px_0_12px_-12px_rgba(31,35,40,0.35)]',
                                  diffLineGutterClass(line.kind),
                                )}
                              >
                                {canShowAddComment ? (
                                  <button
                                    type="button"
                                    className="inline-flex size-6 items-center justify-center rounded-md border border-border/60 bg-background text-sm font-semibold text-foreground shadow-sm transition hover:bg-accent"
                                    title="Add comment to selected lines"
                                    onMouseDown={event => {
                                      event.stopPropagation();
                                    }}
                                    onClick={event => {
                                      event.stopPropagation();
                                      onSetCommentLocation(selectedLocation ?? rowLocation);
                                    }}
                                  >
                                    +
                                  </button>
                                ) : null}
                              </div>
                            </div>

                            {rowThreads.length > 0 || isCommentingHere ? (
                              <div className={cn(diffLineRowClass(line.kind), 'px-4 py-3')}>
                                <div className="ml-[140px] space-y-3">
                                  {rowThreads.length > 0 ? (
                                    <div className="space-y-3">
                                      {rowThreads.map(thread => (
                                        <InlineThreadCard
                                          key={thread.id}
                                          thread={thread}
                                          replyValue={replyDrafts[thread.id] ?? ''}
                                          replyTargetCommentId={replyTargetCommentIds[thread.id] ?? null}
                                          isSavingReply={savingReplyThreadId === thread.id}
                                          onCancel={() => onResetReplyComposer(thread.id)}
                                          onReplyChange={value => onReplyDraftChange(thread.id, value)}
                                          onSubmitReply={() => onSubmitReply(thread)}
                                          onSelectReply={comment => onSelectReplyTarget(thread.id, comment.id)}
                                        />
                                      ))}
                                    </div>
                                  ) : null}

                                  {isCommentingHere ? (
                                    <div className="rounded-md border bg-background">
                                      <div className="border-b bg-muted/35 px-4 py-2.5 text-sm font-semibold">
                                        Add inline comment on lines {commentLocation?.startLine ?? startLine}
                                        {commentLocation?.endLine && commentLocation.endLine !== commentLocation.startLine
                                          ? `-${commentLocation.endLine}`
                                          : ''}
                                      </div>
                                      <div className="space-y-3 px-4 py-3">
                                        <Input
                                          value={threadAuthor}
                                          onChange={event => onThreadAuthorChange(event.target.value)}
                                          placeholder="Your name (optional)"
                                        />
                                        <Textarea
                                          rows={3}
                                          value={threadBody}
                                          onChange={event => onThreadBodyChange(event.target.value)}
                                          placeholder="Leave an inline comment…"
                                          indentOnTab
                                        />
                                        <div className="flex justify-end gap-2">
                                          <Button
                                            type="button"
                                            variant="ghost"
                                            size="sm"
                                            onClick={() => {
                                              onSetCommentLocation(null);
                                            }}
                                          >
                                            Cancel
                                          </Button>
                                          <Button
                                            type="button"
                                            size="sm"
                                            onClick={onSubmitThread}
                                            disabled={!threadBody.trim() || isSavingThread}
                                          >
                                            {isSavingThread ? <Loader2 className="size-3 animate-spin" /> : null}
                                            Start thread
                                          </Button>
                                        </div>
                                      </div>
                                    </div>
                                  ) : null}
                                </div>
                              </div>
                            ) : null}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </section>
              );
            })}
          </div>
        ) : (
          <div className="px-4 py-4 text-sm text-muted-foreground">
            No hunks were parsed for this file.
          </div>
        )}
      </div>
    </div>
  );
}
