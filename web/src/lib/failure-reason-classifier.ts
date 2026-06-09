export type FailureReasonCategory =
  | 'workspace/config'
  | 'github/pr'
  | 'sandbox/dispatch'
  | 'agent/runtime'
  | 'unknown';

type FailureReasonRule = {
  category: Exclude<FailureReasonCategory, 'unknown'>;
  keywords: readonly string[];
};

const FAILURE_REASON_RULES: readonly FailureReasonRule[] = [
  {
    category: 'workspace/config',
    keywords: ['workspace', 'config', 'configuration', 'env', 'environment', 'secret', 'permission denied'],
  },
  {
    category: 'github/pr',
    keywords: ['github', 'pull request', 'pr ', 'merge conflict', 'branch', 'git push', 'repository not found'],
  },
  {
    category: 'sandbox/dispatch',
    keywords: ['sandbox', 'dispatch', 'celery', 'queue', 'container', 'docker', 'timeout'],
  },
  {
    category: 'agent/runtime',
    keywords: ['agent', 'runtime', 'traceback', 'exception', 'tool call', 'model', 'python'],
  },
] as const;

export function classifyFailureReason(
  errorText: string | null | undefined,
): FailureReasonCategory {
  const normalized = errorText?.trim().toLowerCase();
  if (!normalized) {
    return 'unknown';
  }

  return (
    FAILURE_REASON_RULES.find(rule =>
      rule.keywords.some(keyword => normalized.includes(keyword)),
    )?.category ?? 'unknown'
  );
}
