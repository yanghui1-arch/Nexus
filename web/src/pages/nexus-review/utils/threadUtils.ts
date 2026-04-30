import type { ApiVirtualPullRequestComment } from '@/api/types';
import { parseUnifiedDiff, type ParsedDiffHunk } from '@/lib/reviewDiff';
import type {
  SelectedDiffLocation,
  ThreadCommentNode,
  ThreadSnippetTarget,
} from './types';

export function threadLineLabel(thread: {
  file_path?: string | null;
  start_line?: number | null;
  end_line?: number | null;
}): string {
  if (!thread.file_path) {
    return 'General conversation';
  }
  if (thread.end_line && thread.start_line && thread.end_line !== thread.start_line) {
    return `${thread.file_path}:${thread.start_line}-${thread.end_line}`;
  }
  return `${thread.file_path}:${thread.start_line ?? '-'}`;
}

export function locationKey(location: SelectedDiffLocation): string {
  return `${location.filePath}:${location.lineSide}:${location.startLine}`;
}

export function isLineInSelection(
  location: SelectedDiffLocation,
  selection: SelectedDiffLocation | null,
): boolean {
  if (!selection) {
    return false;
  }
  return location.filePath === selection.filePath &&
    location.lineSide === selection.lineSide &&
    location.startLine >= selection.startLine &&
    location.startLine <= selection.endLine;
}

export function isSelectionStart(
  location: SelectedDiffLocation,
  selection: SelectedDiffLocation | null,
): boolean {
  return Boolean(
    selection &&
    location.filePath === selection.filePath &&
    location.lineSide === selection.lineSide &&
    location.startLine === selection.startLine,
  );
}

function splitThreadFilePath(filePath: string): { oldPath: string; newPath: string } {
  const renamedParts = filePath.split(' → ');
  if (renamedParts.length === 2) {
    return { oldPath: renamedParts[0], newPath: renamedParts[1] };
  }
  return { oldPath: filePath, newPath: filePath };
}

export function looksLikeDiffBlock(raw: string): boolean {
  const nonEmptyLines = raw.replace(/\r\n/g, '\n').split('\n').filter(line => line.length > 0);
  return nonEmptyLines.length > 0 && nonEmptyLines.every(line => /^[ +-]/.test(line));
}

export function buildThreadSnippetDiff(
  target: ThreadSnippetTarget,
  rawLines: string,
): string | null {
  if (!target.filePath || !target.diffHunk || !rawLines.trim()) {
    return null;
  }
  const { oldPath, newPath } = splitThreadFilePath(target.filePath);
  return [
    `diff --git a/${oldPath} b/${newPath}`,
    `--- a/${oldPath}`,
    `+++ b/${newPath}`,
    target.diffHunk,
    rawLines,
  ].join('\n');
}

export function parseThreadSnippetHunk(
  target: ThreadSnippetTarget,
  rawLines: string,
): ParsedDiffHunk | null {
  const syntheticDiff = buildThreadSnippetDiff(target, rawLines);
  if (!syntheticDiff) {
    return null;
  }
  return parseUnifiedDiff(syntheticDiff).files[0]?.hunks[0] ?? null;
}

export function stripDiffPrefix(line: string): string {
  return /^[ +-]/.test(line) ? line.slice(1) : line;
}

export function buildSuggestionDiffRaw(originalLines: string[], suggestedCode: string): string | null {
  const nextLines = suggestedCode.replace(/\r\n/g, '\n').replace(/\n$/, '').split('\n');
  if (nextLines.length === 0) {
    return null;
  }
  return [
    ...originalLines.map(line => `-${line}`),
    ...nextLines.map(line => `+${line}`),
  ].join('\n');
}

export function extractCommentSuggestion(body: string): {
  message: string;
  suggestionCode: string | null;
  diffBlock: string | null;
} {
  const fencedBlockMatch = /```([a-zA-Z0-9_-]+)?\n([\s\S]*?)```/.exec(body);
  if (fencedBlockMatch) {
    const language = (fencedBlockMatch[1] ?? '').toLowerCase();
    const content = fencedBlockMatch[2].replace(/\r\n/g, '\n').replace(/\n$/, '');
    const message = `${body.slice(0, fencedBlockMatch.index)}${body.slice(fencedBlockMatch.index + fencedBlockMatch[0].length)}`.trim();
    if (language === 'diff' && looksLikeDiffBlock(content)) {
      return { message, suggestionCode: null, diffBlock: content };
    }
    if (language === 'suggestion') {
      return { message, suggestionCode: content, diffBlock: null };
    }
  }

  return {
    message: body,
    suggestionCode: null,
    diffBlock: null,
  };
}

export function buildThreadCommentTree(comments: ApiVirtualPullRequestComment[]): ThreadCommentNode[] {
  const nodes = new Map<string, ThreadCommentNode>();
  for (const comment of comments) {
    nodes.set(comment.id, { comment, children: [] });
  }

  const roots: ThreadCommentNode[] = [];
  for (const comment of comments) {
    const node = nodes.get(comment.id);
    if (!node) {
      continue;
    }
    const parentNode = comment.parent_comment_id ? nodes.get(comment.parent_comment_id) : null;
    if (parentNode && parentNode.comment.id !== comment.id) {
      parentNode.children.push(node);
    } else {
      roots.push(node);
    }
  }

  return roots;
}

export function summarizeQuotedComment(comment: ApiVirtualPullRequestComment): string | null {
  const { message } = extractCommentSuggestion(comment.body);
  const previewSource = (message || comment.body).replace(/\r\n/g, '\n').trim();
  if (!previewSource) {
    return null;
  }
  const preview = previewSource
    .split('\n')
    .map(line => line.trim())
    .filter(Boolean)
    .join(' ');
  return preview.length > 160 ? `${preview.slice(0, 157)}...` : preview;
}
