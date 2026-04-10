/**
 * Horizontal bar for a single composite score.
 *
 *   Attention Score  ████████████░░░░  78.3
 *
 * Label (left), heat-colored bar (center), monospace value (right).
 * Used for the composite profile grid on the Campaign tab and inside
 * variant ranking cards.
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
        <span className="truncate text-[0.72rem] text-foreground/75">
          {formatMetricLabel(name)}
        </span>
        {inverted && (
          <span
            className="font-mono text-[0.55rem] text-muted-foreground/50"
            title="Lower is better"
          >
            ↓
          </span>
        )}
      </div>

      <div className="relative h-[3px] overflow-hidden rounded-[1px] bg-foreground/[0.06]">
        {hasValue && stop && (
          <div
            className="absolute inset-y-0 left-0 rounded-[1px]"
            style={{
              width: `${widthPercent}%`,
              background: HEAT_VARS[stop],
            }}
          />
        )}
      </div>

      <span
        className={cn(
          'text-right font-mono text-[0.78rem] font-medium tabular-nums',
          stop ? HEAT_TEXT[stop] : 'text-muted-foreground/40',
        )}
      >
        {formatScore(value)}
      </span>
    </div>
  );
}
