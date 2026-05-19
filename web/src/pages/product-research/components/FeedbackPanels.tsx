import { Loader2 } from 'lucide-react';

export function LoadingPanel({ message }: { message: string }) {
  return (
    <div className="rounded-xl border bg-background px-4 py-10">
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="size-4 animate-spin" />
        {message}
      </div>
    </div>
  );
}

export function EmptyPanel({ message }: { message: string }) {
  return (
    <div className="rounded-xl border bg-background px-4 py-10 text-sm text-muted-foreground">
      {message}
    </div>
  );
}
