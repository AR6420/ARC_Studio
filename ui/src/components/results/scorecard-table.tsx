/**
 * Layer 2: The Scorecard — variant ranking table.
 *
 * Dense, monospace, heat-colored cells. Uses the backend-provided
 * color_coding strings (green/amber/red) per Pitfall 8 so UI and
 * backend agree on which variant is best.
 */

import { cn } from '@/lib/utils';
import { formatScore, formatMetricLabel } from '@/utils/formatters';
import { SCORE_COLORS, SCORE_BG_COLORS } from '@/utils/colors';
import type { ScorecardData } from '@/api/types';

interface ScorecardTableProps {
  scorecard: ScorecardData | null | undefined;
  className?: string;
}

function cellClasses(color: string | undefined) {
  const key = (color ?? 'amber') as keyof typeof SCORE_COLORS;
  return {
    textClass: SCORE_COLORS[key] ?? SCORE_COLORS.amber,
    bgClass: SCORE_BG_COLORS[key] ?? SCORE_BG_COLORS.amber,
  };
}

export function ScorecardTable({ scorecard, className }: ScorecardTableProps) {
  if (!scorecard) {
    return (
      <div className={cn('space-y-4', className)}>
        <SectionHeader />
        <p className="font-mono text-[0.72rem] text-muted-foreground/55">
          › scorecard not available
        </p>
      </div>
    );
  }

  const scoreKeys =
    scorecard.variants.length > 0
      ? Object.keys(scorecard.variants[0].composite_scores)
      : [];
  const sortedVariants = [...scorecard.variants].sort(
    (a, b) => a.rank - b.rank,
  );

  return (
    <div className={cn('space-y-5', className)}>
      <SectionHeader winningVariantId={scorecard.winning_variant_id} />

      {/* Variant ranking table */}
      <div className="overflow-x-auto border border-border">
        <table className="w-full font-mono text-[0.72rem]">
          <thead>
            <tr className="border-b border-border">
              <th className="px-3 py-2 text-left text-[0.56rem] tracking-[0.14em] text-muted-foreground/70 uppercase">
                #
              </th>
              <th className="px-3 py-2 text-left text-[0.56rem] tracking-[0.14em] text-muted-foreground/70 uppercase">
                Variant
              </th>
              <th className="px-3 py-2 text-left text-[0.56rem] tracking-[0.14em] text-muted-foreground/70 uppercase">
                Strategy
              </th>
              {scoreKeys.map((key) => (
                <th
                  key={key}
                  className="px-2 py-2 text-right text-[0.56rem] tracking-[0.14em] text-muted-foreground/70 uppercase whitespace-nowrap"
                >
                  {formatMetricLabel(key).replace(' Score', '').replace(' Potential', '')}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sortedVariants.map((variant) => {
              const isWinner =
                variant.variant_id === scorecard.winning_variant_id;
              return (
                <tr
                  key={variant.variant_id}
                  className={cn(
                    'border-b border-border/60 transition-colors hover:bg-foreground/[0.02]',
                    isWinner && 'bg-primary/[0.03]',
                  )}
                >
                  <td className="px-3 py-2 text-[0.72rem] tabular-nums">
                    <span
                      className={cn(
                        isWinner ? 'text-primary' : 'text-muted-foreground/60',
                      )}
                    >
                      {variant.rank.toString().padStart(2, '0')}
                    </span>
                  </td>
                  <td
                    className={cn(
                      'px-3 py-2',
                      isWinner ? 'text-foreground' : 'text-foreground/85',
                    )}
                  >
                    {variant.variant_id}
                  </td>
                  <td className="max-w-[200px] truncate px-3 py-2 text-foreground/65">
                    {variant.strategy}
                  </td>
                  {scoreKeys.map((key) => {
                    const value = variant.composite_scores[key];
                    const { textClass, bgClass } = cellClasses(
                      variant.color_coding[key],
                    );
                    return (
                      <td key={key} className="px-2 py-2 text-right">
                        <span
                          className={cn(
                            'inline-block min-w-[3rem] rounded-sm px-1.5 py-0.5 text-center font-semibold tabular-nums',
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

      {/* Threshold status + iteration summary side-by-side */}
      <div className="grid gap-6 lg:grid-cols-2">
        {scorecard.thresholds_status &&
          Object.keys(scorecard.thresholds_status).length > 0 && (
            <div className="space-y-2">
              <span className="font-mono text-[0.56rem] tracking-[0.14em] text-muted-foreground/70 uppercase">
                Threshold Status
              </span>
              <div className="flex flex-wrap gap-1.5">
                {Object.entries(scorecard.thresholds_status).map(
                  ([key, val]) => {
                    const met = Boolean(val);
                    return (
                      <span
                        key={key}
                        className={cn(
                          'inline-flex items-center gap-1.5 border px-2 py-0.5 font-mono text-[0.64rem]',
                          met
                            ? 'border-heat-hot/40 bg-heat-hot/[0.06] text-heat-hot'
                            : 'border-heat-cold/40 bg-heat-cold/[0.06] text-heat-cold',
                        )}
                      >
                        <span className="size-1 rounded-full bg-current" />
                        {formatMetricLabel(key)}
                      </span>
                    );
                  },
                )}
              </div>
            </div>
          )}

        {scorecard.iteration_trajectory.length > 0 && (
          <div className="space-y-2">
            <span className="font-mono text-[0.56rem] tracking-[0.14em] text-muted-foreground/70 uppercase">
              Iteration Trajectory
            </span>
            <div className="flex flex-wrap gap-1.5">
              {scorecard.iteration_trajectory.map((entry, idx) => {
                const e = entry as Record<string, unknown>;
                return (
                  <span
                    key={idx}
                    className="inline-flex items-baseline gap-1.5 border border-border bg-surface-1 px-2 py-0.5 font-mono text-[0.64rem]"
                  >
                    <span className="text-muted-foreground/60">
                      i{(e.iteration as number) ?? idx + 1}
                    </span>
                    {e.top_score != null && (
                      <span className="tabular-nums text-foreground">
                        {formatScore(e.top_score as number)}
                      </span>
                    )}
                  </span>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* Summary */}
      {scorecard.summary && (
        <p className="max-w-[680px] text-[0.86rem] leading-[1.7] text-foreground/75">
          {scorecard.summary}
        </p>
      )}
    </div>
  );
}

function SectionHeader({ winningVariantId }: { winningVariantId?: string }) {
  return (
    <div className="flex items-baseline justify-between gap-6 border-b border-border pb-2">
      <div className="flex items-baseline gap-3">
        <span className="font-mono text-[0.6rem] font-semibold tracking-[0.18em] text-foreground/90 uppercase">
          Scorecard
        </span>
        <span className="font-mono text-[0.58rem] tracking-[0.12em] text-muted-foreground/50 uppercase">
          layer 2
        </span>
      </div>
      {winningVariantId && (
        <span className="font-mono text-[0.64rem] tabular-nums text-muted-foreground/60">
          <span className="tracking-[0.1em] uppercase text-muted-foreground/50">
            winner
          </span>{' '}
          <span className="text-primary">{winningVariantId}</span>
        </span>
      )}
    </div>
  );
}
