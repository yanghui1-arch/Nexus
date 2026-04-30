import { useMemo } from 'react';
import type { ApiVirtualPullRequestThread } from '@/api/types';
import {
  looksLikeDiffBlock,
  parseThreadSnippetHunk,
  stripDiffPrefix,
} from '../utils/threadUtils';

export function useThreadSnapshotData(thread: ApiVirtualPullRequestThread) {
  const snapshotHunk = useMemo(
    () =>
      thread.code_snapshot && looksLikeDiffBlock(thread.code_snapshot)
        ? parseThreadSnippetHunk(
          {
            filePath: thread.file_path,
            diffHunk: thread.diff_hunk,
          },
          thread.code_snapshot,
        )
        : null,
    [thread.code_snapshot, thread.diff_hunk, thread.file_path],
  );
  const fallbackSnapshotLines = useMemo(
    () =>
      snapshotHunk || !thread.code_snapshot
        ? []
        : thread.code_snapshot.replace(/\r\n/g, '\n').split('\n'),
    [snapshotHunk, thread.code_snapshot],
  );
  const snapshotSourceLines = useMemo(
    () =>
      snapshotHunk
        ? snapshotHunk.lines.filter(line => line.kind !== 'note').map(line => line.text)
        : fallbackSnapshotLines.map(stripDiffPrefix),
    [fallbackSnapshotLines, snapshotHunk],
  );

  return {
    snapshotHunk,
    fallbackSnapshotLines,
    snapshotSourceLines,
  };
}
