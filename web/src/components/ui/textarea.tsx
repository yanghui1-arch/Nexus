import * as React from "react"

import { cn } from "@/lib/utils"

type TextareaProps = React.ComponentProps<"textarea"> & {
  indentOnTab?: boolean
}

function Textarea({ className, indentOnTab = false, onKeyDown, ...props }: TextareaProps) {
  const handleKeyDown = React.useCallback((event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    onKeyDown?.(event)

    if (
      event.defaultPrevented ||
      !indentOnTab ||
      event.key !== "Tab" ||
      event.shiftKey ||
      event.altKey ||
      event.ctrlKey ||
      event.metaKey
    ) {
      return
    }

    event.preventDefault()

    const target = event.currentTarget
    const start = target.selectionStart
    const end = target.selectionEnd
    const nextValue = `${target.value.slice(0, start)}    ${target.value.slice(end)}`

    target.value = nextValue
    target.setSelectionRange(start + 4, start + 4)
    target.dispatchEvent(new Event("input", { bubbles: true }))
  }, [indentOnTab, onKeyDown])

  return (
    <textarea
      data-slot="textarea"
      className={cn(
        "border-input placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-ring/50 aria-invalid:ring-destructive/20 dark:aria-invalid:ring-destructive/40 aria-invalid:border-destructive flex min-h-16 w-full rounded-md border bg-transparent px-3 py-2 text-sm shadow-xs transition-[color,box-shadow] outline-none disabled:cursor-not-allowed disabled:opacity-50 focus-visible:ring-[3px]",
        className
      )}
      onKeyDown={handleKeyDown}
      {...props}
    />
  )
}

export { Textarea }
