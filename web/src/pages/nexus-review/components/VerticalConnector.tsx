import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';

type VerticalConnectorProps = {
  children: ReactNode;
  className?: string;
  lineClassName?: string;
};

export function VerticalConnector({
  children,
  className,
  lineClassName,
}: VerticalConnectorProps) {
  return (
    <div className={cn('relative', className)}>
      <div
        aria-hidden
        className={cn(
          'pointer-events-none absolute inset-y-0 left-0 w-px bg-border/70',
          lineClassName,
        )}
      />
      {children}
    </div>
  );
}
