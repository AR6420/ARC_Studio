/**
 * Composite score card -- the hero data tile for a single metric dimension.
 *
 * Per D-07: Bloomberg terminal meets modern SaaS. The score value dominates
 * visually. Color coding is instantly recognizable. Subtle gradient glow on
 * the colored accent border.
 *
 * Color logic: green >= 70, amber 40-69, red < 40 (inverted for backlash/polarization).
 */

import { cn } from '@/lib/utils';
import { getScoreColor, INVERTED_SCORES, SCORE_COLORS, SCORE_BG_COLORS, SCORE_BORDER_COLORS } from '@/utils/colors';
import { formatScore, formatMetricLabel } from '@/utils/formatters';
import { TrendingDown } from 'lucide-react';

interface ScoreCardProps {
  name: string;
  value: number | null;
  description?: string;
}

export function ScoreCard({ name, value, description }: ScoreCardProps) {
  const isInverted = INVERTED_SCORES.has(name);
  const hasValue = value !== null && value !== undefined;
  const color = hasValue ? getScoreColor(name, value) : null;

  return (
    <div
      className={cn(
        'group relative flex flex-col gap-2 rounded-xl border-l-[3px] bg-card px-4 py-4 ring-1 ring-foreground/[0.06] transition-all duration-200 hover:ring-foreground/10',
        color ? SCORE_BORDER_COLORS[color] : 'border-muted',
      )}
    >
      {/* Subtle background tint */}
      {color && (
        <div
          className={cn(
            'pointer-events-none absolute inset-0 rounded-xl opacity-30',
            SCORE_BG_COLORS[color],
          )}
        />
      )}

      {/* Metric label */}
      <div className="relative flex items-center justify-between">
        <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
          {formatMetricLabel(name)}
        </span>
        {isInverted && (
          <span
            className="flex items-center gap-0.5 text-[10px] text-muted-foreground/70"
            title="Lower is better"
          >
            <TrendingDown className="size-3" />
          </span>
        )}
      </div>

      {/* Score value -- dominant visual element */}
      <div className="relative">
        {hasValue ? (
          <span
            className={cn(
              'text-[2.75rem] font-bold leading-none tracking-tight tabular-nums',
              color ? SCORE_COLORS[color] : 'text-muted-foreground',
            )}
          >
            {formatScore(value)}
          </span>
        ) : (
          <span className="text-[2.75rem] font-bold leading-none tracking-tight text-muted-foreground/30">
            N/A
          </span>
        )}
      </div>

      {/* Description */}
      {description && (
        <p className="relative text-[11px] leading-relaxed text-muted-foreground/60 line-clamp-2">
          {description}
        </p>
      )}
    </div>
  );
}
