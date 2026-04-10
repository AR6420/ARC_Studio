import * as React from "react"

import { cn } from "@/lib/utils"

/**
 * Textarea — flat, matches Input styling. 4px radius.
 */
function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(
        "flex field-sizing-content min-h-16 w-full rounded-sm border border-input bg-transparent px-3 py-2",
        "text-[0.8125rem] text-foreground leading-relaxed transition-colors outline-none",
        "placeholder:text-muted-foreground/60",
        "focus-visible:border-primary/60 focus-visible:ring-1 focus-visible:ring-primary/30",
        "disabled:cursor-not-allowed disabled:opacity-40",
        "aria-invalid:border-destructive/50 aria-invalid:ring-1 aria-invalid:ring-destructive/20",
        className
      )}
      {...props}
    />
  )
}

export { Textarea }
