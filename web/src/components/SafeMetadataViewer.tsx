import type { SafeMetadata, SafeMetadataValue } from '@/api/types';
import type { ReactNode } from 'react';

const SUMMARY_LIMIT = 180;

function stringifySafeValue(value: SafeMetadataValue): string {
  if (typeof value === 'string') return value;
  return JSON.stringify(value, null, 2) ?? '';
}

function truncate(value: string): string {
  return value.length > SUMMARY_LIMIT ? `${value.slice(0, SUMMARY_LIMIT)}…` : value;
}

function SafeMetadataCell({ value }: { value: SafeMetadataValue }) {
  const text = stringifySafeValue(value);
  const isLong = text.length > SUMMARY_LIMIT;

  if (!isLong) {
    return <span className="whitespace-pre-wrap break-words">{text}</span>;
  }

  return (
    <details className="group">
      <summary className="cursor-pointer whitespace-pre-wrap break-words text-muted-foreground marker:text-muted-foreground">
        {truncate(text)}
      </summary>
      <pre className="mt-2 max-h-72 overflow-auto whitespace-pre-wrap break-words rounded bg-background p-2 text-xs">
        {text}
      </pre>
    </details>
  );
}

export function SafeMetadataViewer({
  metadata,
  emptyFallback = null,
}: {
  metadata?: SafeMetadata | null;
  emptyFallback?: ReactNode;
}) {
  const entries = Object.entries(metadata ?? {});

  if (entries.length === 0) {
    return <>{emptyFallback}</>;
  }

  return (
    <dl className="grid gap-2">
      {entries.map(([key, value]) => (
        <div key={key} className="rounded-md border bg-muted/20 px-3 py-2">
          <dt className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">
            {key}
          </dt>
          <dd className="mt-1 text-sm">
            <SafeMetadataCell value={value} />
          </dd>
        </div>
      ))}
    </dl>
  );
}
