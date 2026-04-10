import { mergeProps } from "@base-ui/react/merge-props"
import { useRender } from "@base-ui/react/use-render"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

/**
 * Badge — sharp, angular 2px radius. No pill shape.
 * Used for tags, categories, status labels. Data, not decoration.
 */
const badgeVariants = cva(
  [
    "group/badge inline-flex h-[18px] w-fit shrink-0 items-center justify-center gap-1",
    "overflow-hidden rounded-sm border border-transparent px-1.5",
    "text-[0.65rem] font-semibold tracking-[0.06em] uppercase whitespace-nowrap",
    "transition-colors",
    "focus-visible:border-ring focus-visible:ring-1 focus-visible:ring-ring/50",
    "has-data-[icon=inline-end]:pr-1 has-data-[icon=inline-start]:pl-1",
    "aria-invalid:border-destructive aria-invalid:ring-destructive/20",
    "[&>svg]:pointer-events-none [&>svg]:size-2.5!",
  ].join(" "),
  {
    variants: {
      variant: {
        default: "bg-primary/15 text-primary",
        secondary: "bg-foreground/[0.06] text-foreground/80",
        destructive: "bg-destructive/12 text-destructive",
        outline: "border-border text-foreground/80",
        ghost: "text-foreground/60 hover:text-foreground",
        link: "text-primary underline-offset-4 hover:underline",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

function Badge({
  className,
  variant = "default",
  render,
  ...props
}: useRender.ComponentProps<"span"> & VariantProps<typeof badgeVariants>) {
  return useRender({
    defaultTagName: "span",
    props: mergeProps<"span">(
      {
        className: cn(badgeVariants({ variant }), className),
      },
      props
    ),
    render,
    state: {
      slot: "badge",
      variant,
    },
  })
}

export { Badge, badgeVariants }
