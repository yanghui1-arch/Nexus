import type {
  ApiVirtualPullRequestDetail,
  ApiVirtualPullRequestThread,
} from '@/api/types';
import { ScrollArea } from '@/components/ui/scroll-area';
import type {
  ParsedDiffFile,
  ParsedUnifiedDiff,
} from '@/lib/reviewDiff';
import type {
  FileTreeNode,
  SelectedDiffLocation,
  ShikiToken,
} from '../utils/types';
import { ChangedFilesTree } from './ChangedFilesTree';
import { ReviewDiffViewer } from './ReviewDiffViewer';

type ReviewFilesPanelProps = {
  detail: ApiVirtualPullRequestDetail;
  parsedDiff: ParsedUnifiedDiff;
  fileTree: FileTreeNode[];
  activeFilePath: string;
  expandedDirectories: Record<string, boolean>;
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
  onToggleDirectory: (directoryKey: string) => void;
  onSelectFile: (filePath: string) => void;
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

export function ReviewFilesPanel({
  detail,
  parsedDiff,
  fileTree,
  activeFilePath,
  expandedDirectories,
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
  onToggleDirectory,
  onSelectFile,
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
}: ReviewFilesPanelProps) {
  return (
    <div className="grid min-h-0 flex-1 grid-cols-[320px_minmax(0,1fr)] overflow-hidden">
      <div className="flex min-h-0 flex-col overflow-hidden border-r bg-muted/10">
        <div className="border-b bg-background/60 px-4 py-3">
          <p className="text-sm font-semibold">Changed files</p>
          <p className="mt-1 font-mono text-xs text-muted-foreground">
            <span className="text-emerald-600">+{detail.virtual_pr.additions}</span>
            {' / '}
            <span className="text-red-600">-{detail.virtual_pr.deletions}</span>
          </p>
        </div>
        <ScrollArea className="flex-1">
          <div className="px-2 py-3">
            {parsedDiff.files.length === 0 ? (
              <div className="px-4 py-4 text-xs text-muted-foreground">No changed files.</div>
            ) : (
              <ChangedFilesTree
                nodes={fileTree}
                activeFilePath={activeFilePath}
                expandedDirectories={expandedDirectories}
                onToggleDirectory={onToggleDirectory}
                onSelectFile={onSelectFile}
              />
            )}
          </div>
        </ScrollArea>
      </div>

      <ScrollArea className="min-h-0 bg-muted/10">
        <ReviewDiffViewer
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
          onSetSelectingLines={onSetSelectingLines}
          onSelectDiffLocation={onSelectDiffLocation}
          onExtendDiffSelection={onExtendDiffSelection}
          onSetCommentLocation={onSetCommentLocation}
          onResetReplyComposer={onResetReplyComposer}
          onReplyDraftChange={onReplyDraftChange}
          onSubmitReply={onSubmitReply}
          onSelectReplyTarget={onSelectReplyTarget}
          onThreadAuthorChange={onThreadAuthorChange}
          onThreadBodyChange={onThreadBodyChange}
          onSubmitThread={onSubmitThread}
        />
      </ScrollArea>
    </div>
  );
}
