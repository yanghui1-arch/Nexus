import type { ParsedDiffLineKind } from '@/lib/reviewDiff';

export function shortCommit(value: string | null | undefined): string {
  if (!value) {
    return '-';
  }
  return value.slice(0, 8);
}

export function createdAtTimestamp(value: string | null | undefined): number {
  if (!value) {
    return 0;
  }
  const timestamp = Date.parse(value);
  return Number.isNaN(timestamp) ? 0 : timestamp;
}

export function sortByCreatedAt<T extends { created_at: string }>(items: T[]): T[] {
  return [...items].sort(
    (left, right) => createdAtTimestamp(left.created_at) - createdAtTimestamp(right.created_at),
  );
}

export function lineNumberValue(value: number | null): string {
  return value == null ? '' : String(value);
}

export function diffLineRowClass(kind: ParsedDiffLineKind): string {
  switch (kind) {
    case 'add':
      return 'bg-[#E6FFED]';
    case 'remove':
      return 'bg-[#FFEBE9]';
    case 'note':
      return 'bg-[#DDF4FF]';
    default:
      return 'bg-background';
  }
}

export function diffLineGutterClass(kind: ParsedDiffLineKind): string {
  switch (kind) {
    case 'add':
      return 'bg-[#CCFFD8] text-black';
    case 'remove':
      return 'bg-[#FFD7D5] text-black';
    case 'note':
      return 'bg-[#B6E3FF] text-black';
    default:
      return 'bg-muted/35 text-muted-foreground';
  }
}

export function diffLineTextClass(kind: ParsedDiffLineKind): string {
  switch (kind) {
    case 'add':
    case 'remove':
    case 'context':
      return 'text-black';
    case 'note':
      return 'text-blue-800';
    default:
      return 'text-foreground';
  }
}

export function diffLineSymbol(kind: ParsedDiffLineKind): string {
  switch (kind) {
    case 'add':
      return '+';
    case 'remove':
      return '-';
    case 'note':
      return '@';
    default:
      return ' ';
  }
}
