import { type ReactNode } from 'react';
import { FaGithub } from 'react-icons/fa';
import type { ApiTask } from '@/api/types';

export const UNKNOWN_TASK_DISPLAY_VALUE = 'unknown';
export const TASK_ERROR_PREVIEW_LIMIT = 160;

type TaskDisplayInput = Pick<
  ApiTask,
  'category' | 'external_issue_url' | 'external_pull_request_url' | 'error'
>;

function present(value: string | null | undefined): string {
  const normalized = value?.trim();
  return normalized || UNKNOWN_TASK_DISPLAY_VALUE;
}

export function taskCategoryLabel(category: string | null | undefined): string {
  return present(category);
}

export function truncateTaskError(
  error: string | null | undefined,
  limit = TASK_ERROR_PREVIEW_LIMIT,
): string | null {
  if (!error) {
    return null;
  }

  const normalized = error.trim();
  if (!normalized) {
    return null;
  }

  return normalized.length > limit ? `${normalized.slice(0, limit - 1)}…` : normalized;
}

export function getTaskSourceUrl(task: TaskDisplayInput): string | null {
  return task.external_issue_url?.trim() || task.external_pull_request_url?.trim() || null;
}

export function taskSourceLabel(task: TaskDisplayInput): string {
  return getTaskSourceUrl(task) ?? UNKNOWN_TASK_DISPLAY_VALUE;
}

export function taskSourceNode(task: TaskDisplayInput): ReactNode {
  const sourceUrl = getTaskSourceUrl(task);
  if (!sourceUrl) {
    return UNKNOWN_TASK_DISPLAY_VALUE;
  }

  return (
    <a
      href={sourceUrl}
      target="_blank"
      rel="noreferrer"
      className="inline-flex min-w-0 items-center gap-1 break-all text-foreground underline-offset-4 hover:underline"
    >
      <FaGithub className="size-3 shrink-0" />
      {sourceUrl}
    </a>
  );
}
