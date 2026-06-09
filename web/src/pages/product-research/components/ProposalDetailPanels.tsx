import { MarkdownContent } from '@/components/ui/markdown-content';
import type { ProposalOverviewItem } from './proposalDetailPanel';

export function ProposalOverviewPanel({ items }: { items: ProposalOverviewItem[] }) {
  return (
    <div className="grid gap-3 md:grid-cols-2">
      {items.map(item => (
        <section key={item.label} className="rounded-lg border bg-card p-4">
          <h3 className="text-sm font-semibold text-muted-foreground">{item.label}</h3>
          <p className="mt-2 text-sm leading-6">{item.content}</p>
        </section>
      ))}
    </div>
  );
}

export function ProposalDetailPanel({
  content,
  fallback,
}: {
  content: string | undefined;
  fallback: string;
}) {
  return (
    <div className="rounded-lg border bg-card p-4 text-sm leading-6">
      {content?.trim() ? (
        <MarkdownContent content={content} />
      ) : (
        <p className="text-muted-foreground">{fallback}</p>
      )}
    </div>
  );
}
