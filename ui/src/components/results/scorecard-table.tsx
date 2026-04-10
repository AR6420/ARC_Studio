/**
 * Layer 2: The Scorecard — variant ranking table.
 *
 * Dense, monospace, heat-colored cells. Uses the backend-provided
 * color_coding strings (green/amber/red) per Pitfall 8 so UI and
 * backend agree on which variant is best.
 *
 * Per-iteration data: scorecard.variants only carries the final
 * iteration's ranking. When the caller provides a perIterationVariants
 * map (reshaped from deep_analysis by campaign-detail) and a
 * selectedIteration, the table swaps in that iteration's ranked
 * variants and recomputes the winner as the top-ranked row for that
 * iteration.
 */

import { useMemo } from 'react';
import { cn } from '@/lib/utils';
import { formatScore, formatMetricLabel } from '@/utils/formatters';
import { SCORE_COLORS, SCORE_BG_COLORS } from '@/utils/colors';
import { MarkdownProse } from '@/components/common/markdown-prose';
import type { ScorecardData, ScorecardVariant } from '@/api/types';

interface ScorecardTableProps {
  scorecard: ScorecardData | null | undefined;
  className?: string;
  /** Currently selected iteration for trajectory interaction. */
  selectedIteration?: number;
  /** Called when user clicks an iteration trajectory button. */
  onSelectIteration?: (iteration: number) => void;
  /** Iteration → ranked variants (reshaped from deep_analysis). */
  perIterationVariants?: Map<number, ScorecardVariant[]>;
  /** Iterations the user can actively pick. */
  availableIterations?: number[];
}

function cellClasses(color: string | undefined) {
  const key = (color ?? 'amber') as keyof typeof SCORE_COLORS;
  return {
    textClass: SCORE_COLORS[key] ?? SCORE_COLORS.amber,
    bgClass: SCORE_BG_COLORS[key] ?? SCORE_BG_COLORS.amber,
  };
}

export function ScorecardTable({
  scorecard,
  className,
  selectedIteration,
  onSelectIteration,
  perIterationVariants,
  availableIterations,
}: ScorecardTableProps) {
  const { displayVariants, winnerId, scopedIteration, fellBack } = useMemo(() => {
    if (!scorecard) {
      return {
        displayVariants: [] as ScorecardVariant[],
        winnerId: undefined as string | undefined,
        scopedIteration: null as number | null,
        fellBack: false,
      };
    }
    // Try the per-iteration view first.
    if (
      selectedIteration != null &&
      perIterationVariants &&
      perIterationVariants.has(selectedIteration)
    ) {
      const variants = perIterationVariants.get(selectedIteration)!;
      if (variants.length > 0) {
        const sorted = [...variants].sort((a, b) => a.rank - b.rank);
        return {
          displayVariants: sorted,
          winnerId: sorted[0]?.variant_id,
          scopedIteration: selectedIteration,
          fellBack: false,
        };
      }
    }
    // Fallback: the final iteration's scorecard.variants.
    return {
      displayVariants: [...scorecard.variants].sort((a, b) => a.rank - b.rank),
      winnerId: scorecard.winning_variant_id,
      scopedIteration: null,
      fellBack:
        selectedIteration != null &&
        perIterationVariants != null &&
        !perIterationVariants.has(selectedIteration),
    };
  }, [scorecard, selectedIteration, perIterationVariants]);

  if (!scorecard) {
    return (
      <div className={cn('space-y-4', className)}>
        <SectionHeader />
        <p className="font-mono text-[0.74rem] text-muted-foreground">
          › scorecard not available
        </p>
      </div>
    );
  }

  const scoreKeys =
    displayVariants.length > 0
      ? Object.keys(displayVariants[0].composite_scores)
      : scorecard.variants.length > 0
        ? Object.keys(scorecard.variants[0].composite_scores)
        : [];

  return (
    <div className={cn('space-y-5', className)}>
      <SectionHeader winningVariantId={winnerId} />

      {/* Iteration selector */}
      {availableIterations && availableIterations.length > 1 && onSelectIteration && (
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-mono text-[0.62rem] tracking-[0.14em] text-muted-foreground uppercase">
            Iteration
          </span>
          <div className="flex flex-wrap gap-1">
            {availableIterations.map((it) => {
              const isActive = selectedIteration === it;
              return (
                <button
                  key={it}
                  type="button"
                  onClick={() => {
                    if (!isActive) onSelectIteration(it);
                  }}
                  aria-pressed={isActive}
                  className={cn(
                    'inline-flex items-center rounded-sm border px-2 py-0.5 font-mono text-[0.7rem] tabular-nums transition-colors',
                    isActive
                      ? 'border-primary/60 bg-primary/15 text-primary cursor-default'
                      : 'border-border bg-transparent text-muted-foreground hover:border-foreground/30 hover:text-foreground',
                  )}
                >
                  i{it}
                </button>
              );
            })}
          </div>
          {scopedIteration != null && (
            <span className="font-mono text-[0.62rem] text-muted-foreground">
              · {displayVariants.length} variants from iteration {scopedIteration}
            </span>
          )}
          {fellBack && (
            <span className="font-mono text-[0.62rem] text-muted-foreground">
              · no data for that iteration; showing final ranking
            </span>
          )}
        </div>
      )}

      {/* Variant ranking table */}
      <div className="overflow-x-auto border border-border">
        <table className="w-full font-mono text-[0.74rem]">
          <thead>
            <tr className="border-b border-border">
              <th className="px-3 py-2 text-left text-[0.6rem] tracking-[0.14em] text-muted-foreground uppercase">
                #
              </th>
              <th className="px-3 py-2 text-left text-[0.6rem] tracking-[0.14em] text-muted-foreground uppercase">
                Variant
              </th>
              <th className="px-3 py-2 text-left text-[0.6rem] tracking-[0.14em] text-muted-foreground uppercase">
                Strategy
              </th>
              {scoreKeys.map((key) => (
                <th
                  key={key}
                  className="px-2 py-2 text-right text-[0.6rem] tracking-[0.14em] text-muted-foreground uppercase whitespace-nowrap"
                >
                  {formatMetricLabel(key).replace(' Score', '').replace(' Potential', '')}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {displayVariants.map((variant) => {
              const isWinner = variant.variant_id === winnerId;
              return (
                <tr
                  key={`${scopedIteration ?? 'final'}-${variant.variant_id}`}
                  className={cn(
                    'border-b border-border/60 transition-colors hover:bg-foreground/[0.025]',
                    isWinner && 'bg-primary/[0.04] shadow-[inset_2px_0_0_var(--primary)]',
                  )}
                >
                  <td className="px-3 py-2 tabular-nums">
                    <span
                      className={cn(
                        isWinner ? 'text-primary' : 'text-foreground/70',
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
                  <td className="max-w-[200px] truncate px-3 py-2 text-foreground/75">
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
              <span className="font-mono text-[0.6rem] tracking-[0.14em] text-muted-foreground uppercase">
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
                          'inline-flex items-center gap-1.5 border px-2 py-0.5 font-mono text-[0.66rem]',
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
            <span className="font-mono text-[0.6rem] tracking-[0.14em] text-muted-foreground uppercase">
              Iteration Trajectory
            </span>
            <div className="flex flex-wrap gap-1.5">
              {scorecard.iteration_trajectory.map((entry, idx) => {
                const e = entry as Record<string, unknown>;
                const iterNum = (e.iteration as number) ?? idx + 1;
                const isActive = selectedIteration === iterNum;
                const interactive = typeof onSelectIteration === 'function';
                const topScore =
                  typeof e.top_score === 'number'
                    ? (e.top_score as number)
                    : undefined;
                const contents = (
                  <>
                    <span
                      className={
                        isActive ? 'text-primary' : 'text-foreground/80'
                      }
                    >
                      i{iterNum}
                    </span>
                    {topScore != null && (
                      <span className="tabular-nums text-foreground/85">
                        {formatScore(topScore)}
                      </span>
                    )}
                  </>
                );
                if (interactive) {
                  return (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => {
                        if (!isActive) onSelectIteration!(iterNum);
                      }}
                      aria-pressed={isActive}
                      className={cn(
                        'inline-flex items-baseline gap-1.5 border px-2 py-0.5 font-mono text-[0.66rem] transition-colors',
                        isActive
                          ? 'border-primary/60 bg-primary/15 cursor-default'
                          : 'border-border bg-surface-1 hover:border-foreground/30',
                      )}
                    >
                      {contents}
                    </button>
                  );
                }
                return (
                  <span
                    key={idx}
                    className="inline-flex items-baseline gap-1.5 border border-border bg-surface-1 px-2 py-0.5 font-mono text-[0.66rem]"
                  >
                    {contents}
                  </span>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* Summary — rendered as markdown */}
      {scorecard.summary && <MarkdownProse>{scorecard.summary}</MarkdownProse>}
    </div>
  );
}

function SectionHeader({ winningVariantId }: { winningVariantId?: string }) {
  return (
    <div className="flex items-baseline justify-between gap-6 border-b border-border pb-2">
      <div className="flex items-baseline gap-3">
        <h2 className="text-[1rem] font-medium tracking-[-0.005em] text-foreground">
          Scorecard
        </h2>
        <span className="font-mono text-[0.62rem] tracking-[0.12em] text-muted-foreground uppercase">
          layer 2
        </span>
      </div>
      {winningVariantId && (
        <span className="font-mono text-[0.66rem] tabular-nums text-foreground/75">
          <span className="tracking-[0.1em] uppercase text-muted-foreground">
            winner
          </span>{' '}
          <span className="text-primary">{winningVariantId}</span>
        </span>
      )}
    </div>
  );
}
