import { cn } from '@/lib/utils';
import type { ParsedDiffHunk } from '@/lib/reviewDiff';
import {
  diffLineGutterClass,
  diffLineRowClass,
  diffLineSymbol,
  diffLineTextClass,
  lineNumberValue,
} from '../utils/display';

export function MiniDiffPreview({
  hunk,
  className,
}: {
  hunk: ParsedDiffHunk;
  className?: string;
}) {
  return (
    <div className={cn('overflow-hidden rounded-md border bg-background', className)}>
      <div className="font-mono text-xs leading-5">
        {hunk.lines.map((line, index) => (
          <div
            key={`${hunk.id}-${index}`}
            className={cn(
              'grid grid-cols-[44px_44px_28px_minmax(0,1fr)] border-b border-border/30 last:border-b-0',
              diffLineRowClass(line.kind),
            )}
          >
            <div className={cn('border-r px-1.5 py-0.5 text-right font-mono text-xs select-none', diffLineGutterClass(line.kind))}>
              {lineNumberValue(line.oldLineNumber)}
            </div>
            <div className={cn('border-r px-1.5 py-0.5 text-right font-mono text-xs select-none', diffLineGutterClass(line.kind))}>
              {lineNumberValue(line.newLineNumber)}
            </div>
            <div className={cn('border-r py-0.5 text-center font-mono text-xs font-semibold select-none', diffLineGutterClass(line.kind))}>
              {diffLineSymbol(line.kind)}
            </div>
            <pre className={cn('overflow-x-auto px-3 py-0.5 font-mono text-xs whitespace-pre', diffLineTextClass(line.kind))}>
              {line.text || ' '}
            </pre>
          </div>
        ))}
      </div>
    </div>
  );
}
