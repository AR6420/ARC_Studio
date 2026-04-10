/**
 * Horizontal bar for a single composite score.
 *
 *   Attention Score  ████████████░░░░  78.3
 *
 * Label (left), heat-colored bar (center), monospace value (right).
 * Null/undefined values show an em-dash with no bar fill; 0.0 values
 * show the number with an empty (but visually present) bar track.
 */

import { cn } from '@/lib/utils';
import {
  getHeatStop,
  HEAT_VARS,
  HEAT_TEXT,
  INVERTED_SCORES,
} from '@/utils/colors';
import { formatMetricLabel, formatScore } from '@/utils/formatters';

interface ScoreBarProps {
  name: string;
  value: number | null;
  maxValue?: number;
  compact?: boolean;
  className?: string;
}

export function ScoreBar({
  name,
  value,
  maxValue = 100,
  compact = false,
  className,
}: ScoreBarProps) {
  const hasValue = value !== null && value !== undefined;
  const stop = hasValue ? getHeatStop(name, value) : null;
  const widthPercent = hasValue
    ? Math.min(Math.max((value / maxValue) * 100, 0), 100)
    : 0;
  const inverted = INVERTED_SCORES.has(name);

  return (
    <div
      className={cn(
        'grid items-center gap-3',
        compact
          ? 'grid-cols-[96px_minmax(0,1fr)_38px]'
          : 'grid-cols-[120px_minmax(0,1fr)_44px]',
        className,
      )}
    >
      <div className="flex items-center gap-1 overflow-hidden">
        <span className="truncate text-[0.74rem] text-foreground/80">
          {formatMetricLabel(name)}
        </span>
        {inverted && (
          <span
            className="font-mono text-[0.58rem] text-muted-foreground"
            title="Lower is better"
          >
            ↓
          </span>
        )}
      </div>

      {hasValue ? (
        <div className="relative h-[3px] overflow-hidden rounded-[1px] bg-foreground/[0.08]">
          {stop && widthPercent > 0 && (
            <div
              className="absolute inset-y-0 left-0 rounded-[1px]"
              style={{
                width: `${widthPercent}%`,
                background: HEAT_VARS[stop],
              }}
            />
          )}
        </div>
      ) : (
        // Null / missing — show a dashed track so the metric isn't mistaken for 0
        <div className="h-[3px] rounded-[1px] border-t border-dashed border-foreground/15" />
      )}

      <span
        className={cn(
          'text-right font-mono text-[0.8rem] font-medium tabular-nums',
          hasValue && stop ? HEAT_TEXT[stop] : 'text-muted-foreground',
        )}
      >
        {hasValue ? formatScore(value) : '—'}
      </span>
    </div>
  );
}
