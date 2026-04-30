import { useState } from 'react';
import { MoreHorizontal } from 'lucide-react';
import { Button } from '@/components/ui/button';

export function CommentActionMenu({ onQuoteReply }: { onQuoteReply: () => void }) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div
      className="relative shrink-0"
      onBlur={event => {
        if (!event.currentTarget.contains(event.relatedTarget as Node | null)) {
          setIsOpen(false);
        }
      }}
    >
      <Button
        type="button"
        size="icon"
        variant="ghost"
        className="size-7 rounded-full text-muted-foreground"
        aria-haspopup="menu"
        aria-expanded={isOpen}
        aria-label="Open comment actions"
        onClick={() => setIsOpen(current => !current)}
      >
        <MoreHorizontal className="size-4" />
      </Button>
      {isOpen ? (
        <div
          role="menu"
          className="absolute top-full right-0 z-10 mt-1 min-w-32 overflow-hidden rounded-md border bg-background shadow-lg"
        >
          <button
            type="button"
            className="block w-full px-3 py-2 text-left text-sm hover:bg-accent"
            onClick={() => {
              setIsOpen(false);
              onQuoteReply();
            }}
          >
            Quote reply
          </button>
        </div>
      ) : null}
    </div>
  );
}
