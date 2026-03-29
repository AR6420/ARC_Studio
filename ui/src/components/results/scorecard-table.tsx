/**
 * Layer 2: The Scorecard - Structured ranking data.
 *
 * Displays variant ranking table with composite scores color-coded
 * using the backend-provided color_coding (per Pitfall 8 -- do NOT recompute).
 * Also shows the winner callout, threshold status, iteration trajectory summary,
 * and scorecard summary text.
 */

import { Trophy, Check, X, TrendingUp } from 'lucide-react';
import { cn } from '@/lib/utils';
import { formatScore, formatMetricLabel } from '@/utils/formatters';
import { SCORE_COLORS, SCORE_BG_COLORS } from '@/utils/colors';
import type { ScorecardData } from '@/api/types';

interface ScorecardTableProps {
  scorecard: ScorecardData | null | undefined;
  className?: string;
}

/** Map backend color string to Tailwind classes for cell styling. */
function cellClasses(color: string | undefined) {
  const key = (color ?? 'amber') as keyof typeof SCORE_COLORS;
  const textClass = SCORE_COLORS[key] ?? SCORE_COLORS.amber;
  const bgClass = SCORE_BG_COLORS[key] ?? SCORE_BG_COLORS.amber;
  return { textClass, bgClass };
}

export function ScorecardTable({ scorecard, className }: ScorecardTableProps) {
  if (!scorecard) {
    return (
      <div
        className={cn(
          'flex flex-col items-center justify-center gap-3 py-12 text-center',
          className,
        )}
      >
        <div className="flex size-12 items-center justify-center rounded-xl bg-muted/50">
          <Trophy className="size-6 text-muted-foreground/60" />
        </div>
        <p className="text-sm text-muted-foreground">
          Scorecard not available
        </p>
      </div>
    );
  }

  // Extract composite score keys from first variant for table headers
  const scoreKeys =
    scorecard.variants.length > 0
      ? Object.keys(scorecard.variants[0].composite_scores)
      : [];

  const sortedVariants = [...scorecard.variants].sort(
    (a, b) => a.rank - b.rank,
  );

  return (
    <div className={cn('space-y-5', className)}>
      {/* Section header */}
      <div className="flex items-center gap-2.5">
        <div className="flex size-8 items-center justify-center rounded-lg bg-[oklch(0.25_0.05_163)]">
          <Trophy className="size-4 text-[oklch(0.78_0.16_163)]" />
        </div>
        <h3 className="text-sm font-semibold tracking-wide text-foreground/90 uppercase">
          Scorecard
        </h3>
      </div>

      {/* Winner callout */}
      <div className="flex items-center gap-3 rounded-lg border border-[oklch(0.40_0.08_163)]/40 bg-[oklch(0.22_0.04_163)]/50 px-4 py-3">
        <Trophy className="size-5 text-[oklch(0.78_0.16_163)]" />
        <div className="flex flex-col gap-0.5">
          <span className="text-xs font-medium tracking-wide text-[oklch(0.78_0.16_163)] uppercase">
            Winner
          </span>
          <span className="text-sm font-semibold text-foreground">
            {scorecard.winning_variant_id}
          </span>
        </div>
      </div>

      {/* Variant ranking table */}
      <div className="overflow-x-auto rounded-lg border border-foreground/10">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-foreground/10 bg-muted/30">
              <th className="px-3 py-2.5 text-left text-xs font-semibold tracking-wide text-muted-foreground uppercase">
                Rank
              </th>
              <th className="px-3 py-2.5 text-left text-xs font-semibold tracking-wide text-muted-foreground uppercase">
                Variant
              </th>
              <th className="px-3 py-2.5 text-left text-xs font-semibold tracking-wide text-muted-foreground uppercase">
                Strategy
              </th>
              {scoreKeys.map((key) => (
                <th
                  key={key}
                  className="px-3 py-2.5 text-right text-xs font-semibold tracking-wide text-muted-foreground uppercase"
                >
                  {formatMetricLabel(key)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sortedVariants.map((variant, idx) => {
              const isWinner =
                variant.variant_id === scorecard.winning_variant_id;

              return (
                <tr
                  key={variant.variant_id}
                  className={cn(
                    'border-b border-foreground/5 transition-colors',
                    isWinner && 'bg-[oklch(0.22_0.04_163)]/30',
                    !isWinner && idx % 2 === 0 && 'bg-transparent',
                    !isWinner && idx % 2 === 1 && 'bg-muted/10',
                  )}
                >
                  <td className="px-3 py-2.5 tabular-nums">
                    <span
                      className={cn(
                        'inline-flex size-6 items-center justify-center rounded-md text-xs font-bold',
                        variant.rank === 1
                          ? 'bg-[oklch(0.25_0.05_163)] text-[oklch(0.78_0.16_163)]'
                          : 'bg-muted/40 text-muted-foreground',
                      )}
                    >
                      {variant.rank}
                    </span>
                  </td>
                  <td className="px-3 py-2.5 font-medium text-foreground">
                    {variant.variant_id}
                    {isWinner && (
                      <Trophy className="ml-1.5 inline size-3.5 text-[oklch(0.78_0.16_163)]" />
                    )}
                  </td>
                  <td className="max-w-[200px] truncate px-3 py-2.5 text-foreground/70">
                    {variant.strategy}
                  </td>
                  {scoreKeys.map((key) => {
                    const value = variant.composite_scores[key];
                    // Use color_coding from backend per Pitfall 8
                    const backendColor = variant.color_coding[key];
                    const { textClass, bgClass } = cellClasses(backendColor);

                    return (
                      <td key={key} className="px-3 py-2.5 text-right">
                        <span
                          className={cn(
                            'inline-block min-w-[3.5rem] rounded-md px-2 py-0.5 text-center text-xs font-semibold tabular-nums',
                            textClass,
                            bgClass,
                          )}
                        >
                          {formatScore(value)}
                        </span>
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Threshold status */}
      {scorecard.thresholds_status &&
        Object.keys(scorecard.thresholds_status).length > 0 && (
          <div className="space-y-2">
            <h4 className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
              Threshold Status
            </h4>
            <div className="flex flex-wrap gap-2">
              {Object.entries(scorecard.thresholds_status).map(
                ([key, val]) => {
                  const met = Boolean(val);
                  return (
                    <div
                      key={key}
                      className={cn(
                        'flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-xs font-medium',
                        met
                          ? 'border-emerald-500/20 bg-emerald-500/10 text-emerald-400'
                          : 'border-red-500/20 bg-red-500/10 text-red-400',
                      )}
                    >
                      {met ? (
                        <Check className="size-3.5" />
                      ) : (
                        <X className="size-3.5" />
                      )}
                      {formatMetricLabel(key)}
                    </div>
                  );
                },
              )}
            </div>
          </div>
        )}

      {/* Iteration trajectory summary */}
      {scorecard.iteration_trajectory.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <TrendingUp className="size-4 text-muted-foreground" />
            <h4 className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
              Iteration Trajectory
            </h4>
          </div>
          <div className="flex flex-wrap gap-2">
            {scorecard.iteration_trajectory.map((entry, idx) => (
              <div
                key={idx}
                className="rounded-md border border-foreground/10 bg-muted/20 px-3 py-2 text-xs"
              >
                <span className="font-medium text-foreground/80">
                  Iter {(entry as Record<string, unknown>).iteration as number ?? idx + 1}
                </span>
                {(entry as Record<string, unknown>).top_score != null && (
                  <span className="ml-2 tabular-nums text-muted-foreground">
                    Top: {formatScore((entry as Record<string, unknown>).top_score as number)}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Summary text */}
      {scorecard.summary && (
        <div className="rounded-lg border border-foreground/8 bg-muted/15 px-5 py-4">
          <p className="max-w-prose text-sm leading-relaxed text-foreground/75">
            {scorecard.summary}
          </p>
        </div>
      )}
    </div>
  );
}
