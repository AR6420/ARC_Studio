/**
 * Live time estimate component.
 *
 * Displays estimated campaign duration based on agent count and max iterations.
 * Uses the useTimeEstimate hook which calls POST /api/estimate.
 * Updates in real-time as the user adjusts configuration sliders.
 */

import { Clock, Zap } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useTimeEstimate } from '@/hooks/use-time-estimate'
import { Skeleton } from '@/components/ui/skeleton'

interface TimeEstimateProps {
  agentCount: number
  maxIterations: number
}

export function TimeEstimate({ agentCount, maxIterations }: TimeEstimateProps) {
  const { data, isLoading, isError } = useTimeEstimate(agentCount, maxIterations)

  return (
    <div
      className={cn(
        'flex items-start gap-4 rounded-xl border px-5 py-4 transition-colors',
        'border-primary/20 bg-primary/[0.04]'
      )}
    >
      <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-primary/10">
        <Clock className="size-5 text-primary" />
      </div>

      <div className="min-w-0 flex-1 space-y-1">
        {isLoading ? (
          <div className="space-y-2">
            <Skeleton className="h-5 w-32 bg-primary/10" />
            <Skeleton className="h-3.5 w-48 bg-primary/5" />
          </div>
        ) : isError ? (
          <div className="space-y-0.5">
            <div className="text-sm font-medium text-muted-foreground">
              Unable to estimate
            </div>
            <div className="text-xs text-muted-foreground/70">
              The API server may be offline. Duration depends on your configuration.
            </div>
          </div>
        ) : data ? (
          <div className="space-y-0.5">
            <div className="flex items-center gap-2">
              <span className="text-lg font-semibold tabular-nums text-foreground">
                ~{data.estimated_minutes} min
              </span>
              {data.estimated_minutes <= 5 && (
                <span className="inline-flex items-center gap-1 rounded-full bg-score-green/15 px-2 py-0.5 text-[11px] font-medium text-score-green">
                  <Zap className="size-3" />
                  Fast
                </span>
              )}
            </div>
            <div className="text-xs leading-relaxed text-muted-foreground">
              {data.formula}
            </div>
          </div>
        ) : (
          <div className="text-sm text-muted-foreground">
            Adjust configuration to see estimate
          </div>
        )}
      </div>
    </div>
  )
}
