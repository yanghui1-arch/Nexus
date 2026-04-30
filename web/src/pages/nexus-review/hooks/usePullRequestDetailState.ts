import { startTransition, useCallback, useEffect, useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import type {
  ApiVirtualPullRequestCommentCreateRequest,
  ApiVirtualPullRequestDetail,
  ApiVirtualPullRequestThread,
  ApiVirtualPullRequestThreadCreateRequest,
} from '@/api/types';
import { getErrorDetail } from '@/api/client';
import {
  createTaskVirtualPullRequestComment,
  createTaskVirtualPullRequestThread,
  getTaskVirtualPullRequest,
} from '@/api/tasks';
import { usePolling } from '@/lib/usePolling';
import { parseUnifiedDiff } from '@/lib/reviewDiff';
import { sortByCreatedAt } from '../utils/display';
import {
  buildFileTree,
  collectDirectoryKeys,
  directoryAncestors,
  normalizeFileMatch,
} from '../utils/fileTree';
import { useHighlightedHunkTokens } from '../utils/highlighting';
import type {
  ReviewTab,
  SelectedDiffLocation,
} from '../utils/types';

export function usePullRequestDetailState() {
  const { taskId, virtualPrId } = useParams<{ taskId: string; virtualPrId: string }>();
  const [detail, setDetail] = useState<ApiVirtualPullRequestDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<ReviewTab>('conversation');
  const [activeFilePath, setActiveFilePath] = useState('');
  const [expandedDirectories, setExpandedDirectories] = useState<Record<string, boolean>>({});
  const [selectedLocation, setSelectedLocation] = useState<SelectedDiffLocation | null>(null);
  const [threadBody, setThreadBody] = useState('');
  const [threadAuthor, setThreadAuthor] = useState('');
  const [isSelectingLines, setIsSelectingLines] = useState(false);
  const [selectionAnchor, setSelectionAnchor] = useState<SelectedDiffLocation | null>(null);
  const [commentLocation, setCommentLocation] = useState<SelectedDiffLocation | null>(null);
  const [visibleInlineThreadId, setVisibleInlineThreadId] = useState<string | null>(null);
  const [replyDrafts, setReplyDrafts] = useState<Record<string, string>>({});
  const [replyTargetCommentIds, setReplyTargetCommentIds] = useState<Record<string, string | null>>({});
  const [isSavingThread, setIsSavingThread] = useState(false);
  const [savingReplyThreadId, setSavingReplyThreadId] = useState<string | null>(null);

  const refreshDetail = useCallback(async () => {
    if (!taskId || !virtualPrId) {
      return;
    }

    try {
      const nextDetail = await getTaskVirtualPullRequest(taskId, virtualPrId);
      startTransition(() => {
        setDetail(nextDetail);
        setError(null);
        setIsLoading(false);
      });
    } catch (nextError) {
      startTransition(() => {
        setError(getErrorDetail(nextError, 'Failed to load pull request detail.'));
        setIsLoading(false);
      });
    }
  }, [taskId, virtualPrId]);

  useEffect(() => {
    void refreshDetail();
  }, [refreshDetail]);

  usePolling(refreshDetail, 5_000, {
    enabled: Boolean(taskId && virtualPrId),
    runImmediately: false,
  });

  const parsedDiff = useMemo(
    () => parseUnifiedDiff(detail?.diff ?? ''),
    [detail?.diff],
  );

  useEffect(() => {
    if (!parsedDiff.files.length) {
      setActiveFilePath('');
      return;
    }

    setActiveFilePath(current => {
      if (current && parsedDiff.files.some(file => file.displayPath === current)) {
        return current;
      }
      return parsedDiff.files[0].displayPath;
    });
  }, [parsedDiff.files]);

  const activeFile = useMemo(
    () =>
      parsedDiff.files.find(file => file.displayPath === activeFilePath) ??
      parsedDiff.files[0] ??
      null,
    [activeFilePath, parsedDiff.files],
  );
  const highlightedHunkTokens = useHighlightedHunkTokens(activeFile);
  const fileTree = useMemo(
    () => buildFileTree(parsedDiff.files),
    [parsedDiff.files],
  );
  const directoryKeys = useMemo(
    () => collectDirectoryKeys(fileTree),
    [fileTree],
  );

  useEffect(() => {
    if (!directoryKeys.length) {
      return;
    }

    setExpandedDirectories(current => {
      let changed = false;
      const next = { ...current };
      for (const key of directoryKeys) {
        if (!(key in next)) {
          next[key] = true;
          changed = true;
        }
      }
      return changed ? next : current;
    });
  }, [directoryKeys]);

  useEffect(() => {
    if (!activeFilePath) {
      return;
    }

    const ancestorKeys = directoryAncestors(activeFilePath);
    if (!ancestorKeys.length) {
      return;
    }

    setExpandedDirectories(current => {
      let changed = false;
      const next = { ...current };
      for (const key of ancestorKeys) {
        if (next[key] !== true) {
          next[key] = true;
          changed = true;
        }
      }
      return changed ? next : current;
    });
  }, [activeFilePath]);

  const conversationThreads = useMemo(
    () => sortByCreatedAt(detail?.threads ?? []),
    [detail?.threads],
  );

  const inlineThreads = useMemo(
    () => conversationThreads.filter(thread => thread.kind === 'inline'),
    [conversationThreads],
  );

  const threadsByLineKey = useMemo(() => {
    const next = new Map<string, ApiVirtualPullRequestThread[]>();
    for (const thread of inlineThreads) {
      if (!thread.file_path || !thread.line_side || thread.start_line == null) {
        continue;
      }
      const matchedFile = parsedDiff.files.find(file => normalizeFileMatch(file, thread.file_path ?? ''));
      const key = `${matchedFile?.displayPath ?? thread.file_path}:${thread.line_side}:${thread.start_line}`;
      const existing = next.get(key) ?? [];
      existing.push(thread);
      next.set(key, existing);
    }
    return next;
  }, [inlineThreads, parsedDiff.files]);

  const openThreadCount = detail?.threads.filter(thread => thread.status === 'open').length ?? 0;
  const fileCount = detail?.virtual_pr.changed_files.length ?? 0;
  const reviewCount = detail?.reviews.length ?? 0;

  const toggleDirectory = (directoryKey: string) => {
    setExpandedDirectories(current => ({
      ...current,
      [directoryKey]: current[directoryKey] === false,
    }));
  };

  const resetReplyComposer = (threadId: string) => {
    setReplyDrafts(current => ({ ...current, [threadId]: '' }));
    setReplyTargetCommentIds(current => ({ ...current, [threadId]: null }));
  };

  const updateReplyDraft = (threadId: string, value: string) => {
    setReplyDrafts(current => ({ ...current, [threadId]: value }));
  };

  const selectReplyTarget = (threadId: string, commentId: string) => {
    setReplyTargetCommentIds(current => ({ ...current, [threadId]: commentId }));
  };

  const submitThread = async (options: { forceGeneral?: boolean } = {}) => {
    if (!taskId || !virtualPrId || !threadBody.trim()) {
      return;
    }

    const inlineTarget = options.forceGeneral ? null : (commentLocation ?? selectedLocation);
    const payload: ApiVirtualPullRequestThreadCreateRequest = inlineTarget
      ? {
          kind: 'inline',
          created_by: threadAuthor.trim() || null,
          body: threadBody.trim(),
          file_path: inlineTarget.filePath,
          start_line: inlineTarget.startLine,
          end_line: inlineTarget.endLine,
          line_side: inlineTarget.lineSide,
          diff_hunk: inlineTarget.diffHunk,
        }
      : {
          kind: 'general',
          created_by: threadAuthor.trim() || null,
          body: threadBody.trim(),
        };

    setIsSavingThread(true);
    try {
      const createdThread = await createTaskVirtualPullRequestThread(taskId, virtualPrId, payload);
      await refreshDetail();
      startTransition(() => {
        setThreadBody('');
        setSelectedLocation(null);
        setIsSelectingLines(false);
        setSelectionAnchor(null);
        setCommentLocation(null);
        setVisibleInlineThreadId(createdThread.kind === 'inline' ? createdThread.id : null);
        setIsSavingThread(false);
      });
    } catch (nextError) {
      startTransition(() => {
        setError(getErrorDetail(nextError, 'Failed to create review thread.'));
        setIsSavingThread(false);
      });
    }
  };

  const submitReply = async (thread: ApiVirtualPullRequestThread) => {
    if (!taskId || !virtualPrId) {
      return;
    }
    const body = replyDrafts[thread.id]?.trim();
    if (!body) {
      return;
    }

    const payload: ApiVirtualPullRequestCommentCreateRequest = {
      author: threadAuthor.trim() || null,
      parent_comment_id: replyTargetCommentIds[thread.id] ?? null,
      body,
    };

    setSavingReplyThreadId(thread.id);
    try {
      await createTaskVirtualPullRequestComment(taskId, virtualPrId, thread.id, payload);
      await refreshDetail();
      startTransition(() => {
        resetReplyComposer(thread.id);
        setSavingReplyThreadId(null);
      });
    } catch (nextError) {
      startTransition(() => {
        setError(getErrorDetail(nextError, 'Failed to add thread reply.'));
        setSavingReplyThreadId(null);
      });
    }
  };

  const openThreadFile = (thread: ApiVirtualPullRequestThread) => {
    if (!thread.file_path) {
      return;
    }
    const matchedFile = parsedDiff.files.find(file => normalizeFileMatch(file, thread.file_path ?? ''));
    if (matchedFile) {
      setActiveFilePath(matchedFile.displayPath);
    }
    setSelectedLocation(null);
    setIsSelectingLines(false);
    setSelectionAnchor(null);
    setCommentLocation(null);
    setVisibleInlineThreadId(thread.id);
    setActiveTab('files');
  };

  const selectDiffLocation = (location: SelectedDiffLocation) => {
    setVisibleInlineThreadId(null);
    setCommentLocation(null);
    setSelectionAnchor(location);
    setSelectedLocation(location);
  };

  const extendDiffSelection = (location: SelectedDiffLocation) => {
    if (!selectionAnchor ||
      selectionAnchor.filePath !== location.filePath ||
      selectionAnchor.lineSide !== location.lineSide
    ) {
      setSelectionAnchor(location);
      setSelectedLocation(location);
      return;
    }
    setSelectedLocation({
      ...selectionAnchor,
      startLine: Math.min(selectionAnchor.startLine, location.startLine),
      endLine: Math.max(selectionAnchor.startLine, location.startLine),
      diffHunk: selectionAnchor.diffHunk ?? location.diffHunk,
    });
  };

  const selectTab = (tab: ReviewTab) => {
    if (tab === 'files') {
      setVisibleInlineThreadId(null);
    }
    setActiveTab(tab);
  };

  return {
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
  };
}
