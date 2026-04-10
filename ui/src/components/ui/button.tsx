import { Button as ButtonPrimitive } from "@base-ui/react/button"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

/**
 * Button — flat, precise, no decorative glow.
 * Structure from border + spacing, not from shadows.
 */
const buttonVariants = cva(
  [
    "group/button inline-flex shrink-0 items-center justify-center rounded-md",
    "border border-transparent bg-clip-padding font-medium whitespace-nowrap",
    "text-[0.8125rem] tracking-[-0.005em] transition-colors duration-150",
    "outline-none select-none",
    "focus-visible:border-ring focus-visible:ring-1 focus-visible:ring-ring/60",
    "disabled:pointer-events-none disabled:opacity-40",
    "aria-invalid:border-destructive aria-invalid:ring-1 aria-invalid:ring-destructive/30",
    "[&_svg]:pointer-events-none [&_svg]:shrink-0",
    "[&_svg:not([class*='size-'])]:size-3.5",
  ].join(" "),
  {
    variants: {
      variant: {
        default:
          "bg-primary text-primary-foreground hover:bg-primary/90 [a]:hover:bg-primary/90",
        outline:
          "border-border text-foreground hover:border-foreground/20 hover:bg-foreground/[0.03] aria-expanded:border-foreground/20 aria-expanded:bg-foreground/[0.04]",
        secondary:
          "bg-foreground/[0.05] text-foreground hover:bg-foreground/[0.08] aria-expanded:bg-foreground/[0.08]",
        ghost:
          "text-foreground/80 hover:text-foreground hover:bg-foreground/[0.04] aria-expanded:bg-foreground/[0.04]",
        destructive:
          "bg-transparent text-destructive border-destructive/30 hover:bg-destructive/[0.08] hover:border-destructive/50",
        link: "text-primary underline-offset-4 hover:underline h-auto px-0",
      },
      size: {
        default:
          "h-8 gap-1.5 px-3 has-data-[icon=inline-end]:pr-2.5 has-data-[icon=inline-start]:pl-2.5",
        xs: "h-6 gap-1 rounded-sm px-1.5 text-[0.7rem] [&_svg:not([class*='size-'])]:size-3",
        sm: "h-7 gap-1 rounded-sm px-2 text-[0.75rem] [&_svg:not([class*='size-'])]:size-3",
        lg: "h-9 gap-1.5 px-3.5",
        icon: "size-8",
        "icon-xs": "size-6 rounded-sm [&_svg:not([class*='size-'])]:size-3",
        "icon-sm": "size-7 rounded-sm [&_svg:not([class*='size-'])]:size-3",
        "icon-lg": "size-9",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

function Button({
  className,
  variant = "default",
  size = "default",
  ...props
}: ButtonPrimitive.Props & VariantProps<typeof buttonVariants>) {
  return (
    <ButtonPrimitive
      data-slot="button"
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  )
}

export { Button, buttonVariants }
