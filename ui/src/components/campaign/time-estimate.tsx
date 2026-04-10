/**
 * Inline campaign duration estimate.
 *
 * Renders as a single line of monospace text meant to sit next to the
 * Run button. No card, no icon container, no separate section.
 */

import { useTimeEstimate } from '@/hooks/use-time-estimate';
import { cn } from '@/lib/utils';

interface TimeEstimateProps {
  agentCount: number;
  maxIterations: number;
  className?: string;
}

export function TimeEstimate({
  agentCount,
  maxIterations,
  className,
}: TimeEstimateProps) {
  const { data, isLoading, isError } = useTimeEstimate(
    agentCount,
    maxIterations,
  );

  let body: React.ReactNode;
  if (isLoading) {
    body = <span className="text-muted-foreground/55">estimating…</span>;
  } else if (isError || !data) {
    body = <span className="text-muted-foreground/55">— — —</span>;
  } else {
    body = (
      <>
        <span className="text-foreground/85">
          ~{data.estimated_minutes}m
        </span>
        <span className="ml-2 hidden text-muted-foreground/50 lg:inline">
          · {data.formula}
        </span>
      </>
    );
  }

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 font-mono text-[0.7rem] tabular-nums text-muted-foreground',
        className,
      )}
    >
      <span className="tracking-[0.12em] text-muted-foreground/55 uppercase">
        est
      </span>
      <span className="text-muted-foreground/30">·</span>
      {body}
    </span>
  );
}
