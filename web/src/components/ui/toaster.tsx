import { Toaster as Sonner } from "sonner";

export function Toaster() {
  return (
    <Sonner
      position="bottom-right"
      toastOptions={{
        classNames: {
          toast:
            "group flex items-start gap-3 rounded-lg border bg-background px-4 py-3 shadow-lg text-sm text-foreground",
          error:
            "border-destructive/40 bg-destructive/10 text-destructive [&>[data-icon]]:text-destructive",
          success:
            "border-green-500/30 bg-green-500/10 text-green-700 dark:text-green-400",
          description: "text-muted-foreground text-xs mt-0.5",
          actionButton:
            "bg-primary text-primary-foreground text-xs px-2 py-1 rounded",
          cancelButton:
            "bg-muted text-muted-foreground text-xs px-2 py-1 rounded",
        },
      }}
    />
  );
}
