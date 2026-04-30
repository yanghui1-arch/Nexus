import type {
  ApiVirtualPullRequestComment,
  ApiVirtualPullRequestLineSide,
  ApiVirtualPullRequestThread,
} from '@/api/types';
import type { ParsedDiffFile } from '@/lib/reviewDiff';

export type ReviewTab = 'conversation' | 'files';

export type SelectedDiffLocation = {
  filePath: string;
  startLine: number;
  endLine: number;
  lineSide: ApiVirtualPullRequestLineSide;
  diffHunk: string | null;
};

export type NexusReviewPageProps = {
  mode: 'queue' | 'task' | 'pull-request';
};

export type FileTreeNode = FileTreeDirectoryNode | FileTreeLeafNode;

export type FileTreeDirectoryNode = {
  type: 'directory';
  key: string;
  name: string;
  children: FileTreeNode[];
};

export type FileTreeLeafNode = {
  type: 'file';
  key: string;
  name: string;
  file: ParsedDiffFile;
};

export type MutableFileTreeDirectoryNode = {
  key: string;
  name: string;
  directories: Map<string, MutableFileTreeDirectoryNode>;
  files: FileTreeLeafNode[];
};

export type ShikiToken = {
  content: string;
  color?: string;
  fontStyle?: number;
};

export type ThreadSnippetTarget = {
  filePath: string | null | undefined;
  diffHunk: string | null | undefined;
};

export type ThreadCommentNode = {
  comment: ApiVirtualPullRequestComment;
  children: ThreadCommentNode[];
};

export type ThreadCardProps = {
  thread: ApiVirtualPullRequestThread;
  replyValue: string;
  replyTargetCommentId?: string | null;
  isSavingReply: boolean;
  onCancel: () => void;
  onReplyChange: (value: string) => void;
  onSubmitReply: () => void;
  onSelectReply?: (comment: ApiVirtualPullRequestComment) => void;
  onOpenFile?: () => void;
};
