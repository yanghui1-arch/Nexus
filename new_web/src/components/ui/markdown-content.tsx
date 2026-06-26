import Markdown from "markdown-to-jsx"
import { cn } from "@/lib/utils"

type MarkdownContentProps = {
  children: string
  className?: string
}

export function MarkdownContent({ children, className }: MarkdownContentProps) {
  return (
    <Markdown
      className={cn(
        "prose prose-sm max-w-none text-foreground",
        "prose-headings:font-semibold prose-headings:tracking-tight",
        "prose-a:text-primary prose-a:no-underline hover:prose-a:underline",
        "prose-code:rounded prose-code:bg-muted prose-code:px-1.5 prose-code:py-0.5 prose-code:text-sm prose-code:font-medium",
        "prose-pre:rounded-lg prose-pre:bg-muted/50",
        className
      )}
    >
      {children}
    </Markdown>
  )
}
