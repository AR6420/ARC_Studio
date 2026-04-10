"use client"

import { Tabs as TabsPrimitive } from "@base-ui/react/tabs"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

/**
 * Tabs — minimal. Line variant is the only one we use.
 * Active state = thin amber bar under the label. No filled pills.
 */

function Tabs({
  className,
  orientation = "horizontal",
  ...props
}: TabsPrimitive.Root.Props) {
  return (
    <TabsPrimitive.Root
      data-slot="tabs"
      data-orientation={orientation}
      className={cn(
        "group/tabs flex gap-0 data-horizontal:flex-col",
        className
      )}
      {...props}
    />
  )
}

const tabsListVariants = cva(
  [
    "group/tabs-list inline-flex items-center text-muted-foreground",
    "group-data-horizontal/tabs:h-9 group-data-vertical/tabs:h-fit group-data-vertical/tabs:flex-col",
    "data-[variant=line]:rounded-none data-[variant=line]:w-full data-[variant=line]:border-b data-[variant=line]:border-border",
  ].join(" "),
  {
    variants: {
      variant: {
        default: "bg-foreground/[0.04] rounded-sm p-[3px] gap-0.5",
        line: "gap-6 bg-transparent",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

function TabsList({
  className,
  variant = "default",
  ...props
}: TabsPrimitive.List.Props & VariantProps<typeof tabsListVariants>) {
  return (
    <TabsPrimitive.List
      data-slot="tabs-list"
      data-variant={variant}
      className={cn(tabsListVariants({ variant }), className)}
      {...props}
    />
  )
}

function TabsTrigger({ className, ...props }: TabsPrimitive.Tab.Props) {
  return (
    <TabsPrimitive.Tab
      data-slot="tabs-trigger"
      className={cn(
        "relative inline-flex h-full items-center justify-center gap-1.5",
        "border border-transparent px-0 py-0 text-[0.78rem] font-medium tracking-[0.01em] whitespace-nowrap",
        "text-foreground/50 transition-colors duration-150",
        "hover:text-foreground/80",
        "focus-visible:outline-1 focus-visible:outline-ring",
        "disabled:pointer-events-none disabled:opacity-40",
        "[&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-3.5",
        // Default variant (filled pill) — rarely used, kept for API
        "group-data-[variant=default]/tabs-list:h-[calc(100%-2px)] group-data-[variant=default]/tabs-list:rounded-[3px] group-data-[variant=default]/tabs-list:px-2.5 group-data-[variant=default]/tabs-list:data-active:bg-background group-data-[variant=default]/tabs-list:data-active:text-foreground",
        // Line variant (the main one)
        "group-data-[variant=line]/tabs-list:bg-transparent group-data-[variant=line]/tabs-list:px-0 group-data-[variant=line]/tabs-list:h-9",
        "group-data-[variant=line]/tabs-list:data-active:text-foreground",
        // Active underline bar — 1px, primary colour
        "after:absolute after:left-0 after:right-0 after:bottom-[-1px] after:h-px after:bg-primary after:opacity-0 after:transition-opacity",
        "group-data-[variant=line]/tabs-list:data-active:after:opacity-100",
        className
      )}
      {...props}
    />
  )
}

function TabsContent({ className, ...props }: TabsPrimitive.Panel.Props) {
  return (
    <TabsPrimitive.Panel
      data-slot="tabs-content"
      className={cn("flex-1 text-sm outline-none", className)}
      {...props}
    />
  )
}

export { Tabs, TabsList, TabsTrigger, TabsContent, tabsListVariants }
