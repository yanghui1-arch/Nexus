import * as React from "react"

import { cn } from "@/lib/utils"

function ScrollArea({
  className,
  children,
  ...props
}: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="scroll-area"
      className={cn("relative overflow-hidden", className)}
      {...props}
    >
      <div
        data-slot="scroll-area-viewport"
        className="h-full w-full rounded-[inherit] overflow-auto"
      >
        {children}
      </div>
    </div>
  )
}

function ScrollBar({
  className,
  orientation = "vertical",
  ...props
}: React.ComponentProps<"div"> & {
  orientation?: "vertical" | "horizontal"
}) {
  return (
    <div
      data-slot="scroll-bar"
      data-orientation={orientation}
      className={cn(
        "flex touch-none transition-colors select-none",
        orientation === "vertical" &&
          "h-full w-2.5 border-l border-l-transparent p-[1px]",
        orientation === "horizontal" &&
          "h-2.5 flex-col border-t border-t-transparent p-[1px]",
        className
      )}
      {...props}
    >
      <div className="bg-border relative flex-1 rounded-full" />
    </div>
  )
}

export { ScrollArea, ScrollBar }
