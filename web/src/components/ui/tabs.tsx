import * as React from "react"

import { cn } from "@/lib/utils"

type TabsContextValue = {
  baseId: string
  setValue: (value: string) => void
  value: string
}

const TabsContext = React.createContext<TabsContextValue | null>(null)

function useTabsContext() {
  const context = React.useContext(TabsContext)

  if (!context) {
    throw new Error("Tabs components must be used within Tabs.")
  }

  return context
}

function Tabs({
  children,
  className,
  defaultValue,
  onValueChange,
  value: valueProp,
  ...props
}: React.ComponentProps<"div"> & {
  defaultValue?: string
  onValueChange?: (value: string) => void
  value?: string
}) {
  const baseId = React.useId()
  const [uncontrolledValue, setUncontrolledValue] = React.useState(defaultValue ?? "")
  const value = valueProp ?? uncontrolledValue

  const setValue = React.useCallback(
    (nextValue: string) => {
      if (valueProp === undefined) {
        setUncontrolledValue(nextValue)
      }
      onValueChange?.(nextValue)
    },
    [onValueChange, valueProp]
  )

  return (
    <TabsContext.Provider value={{ baseId, setValue, value }}>
      <div data-slot="tabs" className={cn("flex flex-col gap-4", className)} {...props}>
        {children}
      </div>
    </TabsContext.Provider>
  )
}

function TabsList({
  className,
  ...props
}: React.ComponentProps<"div">) {
  return (
    <div
      role="tablist"
      data-slot="tabs-list"
      className={cn(
        "bg-muted text-muted-foreground inline-flex h-10 w-fit items-center rounded-lg p-1",
        className
      )}
      {...props}
    />
  )
}

function TabsTrigger({
  children,
  className,
  disabled,
  value,
  ...props
}: React.ComponentProps<"button"> & {
  value: string
}) {
  const context = useTabsContext()
  const isActive = context.value === value
  const triggerId = `${context.baseId}-trigger-${value}`
  const contentId = `${context.baseId}-content-${value}`

  return (
    <button
      type="button"
      role="tab"
      id={triggerId}
      aria-controls={contentId}
      aria-selected={isActive}
      data-slot="tabs-trigger"
      data-state={isActive ? "active" : "inactive"}
      disabled={disabled}
      className={cn(
        "inline-flex h-8 items-center justify-center rounded-md px-3 text-sm font-medium whitespace-nowrap transition-all outline-none",
        "data-[state=active]:bg-background data-[state=active]:text-foreground data-[state=active]:shadow-sm",
        "disabled:pointer-events-none disabled:opacity-50",
        className
      )}
      onClick={() => context.setValue(value)}
      {...props}
    >
      {children}
    </button>
  )
}

function TabsContent({
  children,
  className,
  value,
  ...props
}: React.ComponentProps<"div"> & {
  value: string
}) {
  const context = useTabsContext()
  const isActive = context.value === value
  const triggerId = `${context.baseId}-trigger-${value}`
  const contentId = `${context.baseId}-content-${value}`

  if (!isActive) {
    return null
  }

  return (
    <div
      role="tabpanel"
      id={contentId}
      aria-labelledby={triggerId}
      data-slot="tabs-content"
      className={cn("outline-none", className)}
      {...props}
    >
      {children}
    </div>
  )
}

export { Tabs, TabsContent, TabsList, TabsTrigger }
