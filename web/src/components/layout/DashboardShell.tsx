import { type ReactNode } from 'react';
import { cn } from '@/lib/utils';

type DashboardShellProps = {
  title: string;
  description: string;
  topActions?: ReactNode;
  /** Override the default overflow-y-auto + padding. Use "p-0 overflow-hidden" for fixed-height panel layouts. */
  mainClassName?: string;
  children: ReactNode;
};

export function DashboardShell({
  title,
  description,
  topActions,
  mainClassName,
  children,
}: DashboardShellProps) {
  return (
    <>
      <header className="shrink-0 border-b bg-background/80 backdrop-blur-sm">
        <div className="mx-auto flex w-full max-w-[1600px] items-center gap-3 px-6 py-4">
          <div className="flex min-w-0 flex-col">
            <h1 className="truncate text-lg font-semibold">{title}</h1>
            <p className="text-sm text-muted-foreground">{description}</p>
          </div>

          {topActions ? (
            <div className="ml-auto flex items-center gap-2">{topActions}</div>
          ) : null}
        </div>
      </header>

      <main
        className={cn(
          'mx-auto flex w-full max-w-[1600px] min-h-0 flex-1 flex-col overflow-y-auto px-6 py-6',
          mainClassName,
        )}
      >
        {children}
      </main>
    </>
  );
}
