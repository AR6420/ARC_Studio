/**
 * Layer 3: Deep Analysis - Per-iteration expandable sections.
 *
 * Renders detailed per-iteration data with collapsible sections
 * for power users and data scientists. All sections collapsed by default.
 * Uses shadcn Collapsible primitive for expand/collapse behavior.
 *
 * Backend data structure:
 * { iterations: [{ iteration: N, variants: [...], analysis: {...} }] }
 */

import { useState } from 'react';
import { ChevronRight, Layers, ChevronsUpDown } from 'lucide-react';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { formatScore, formatMetricLabel } from '@/utils/formatters';

interface DeepAnalysisProps {
  deepAnalysis: Record<string, unknown> | null | undefined;
  className?: string;
}

interface IterationData {
  iteration: number;
  variants?: VariantDetail[];
  analysis?: AnalysisDetail;
}

interface VariantDetail {
  variant_id: string;
  strategy?: string;
  tribe_scores?: Record<string, number | null>;
  mirofish_metrics?: Record<string, unknown>;
  composite_scores?: Record<string, number | null>;
}

interface AnalysisDetail {
  ranking?: string[];
  cross_system_insights?: string[];
  [key: string]: unknown;
}

/** Type-narrow the deep_analysis JSON into iteration array. */
function parseIterations(
  data: Record<string, unknown>,
): IterationData[] {
  if (Array.isArray(data.iterations)) {
    return data.iterations as IterationData[];
  }
  // Fallback: if the data itself is an array
  if (Array.isArray(data)) {
    return data as IterationData[];
  }
  return [];
}

/** Render a score table from a Record<string, number|null>. */
function ScoreGrid({
  title,
  scores,
}: {
  title: string;
  scores: Record<string, number | null> | undefined;
}) {
  if (!scores || Object.keys(scores).length === 0) return null;

  return (
    <div className="space-y-1.5">
      <h6 className="text-[0.7rem] font-semibold tracking-wider text-muted-foreground/80 uppercase">
        {title}
      </h6>
      <div className="grid grid-cols-2 gap-x-6 gap-y-1 sm:grid-cols-3 lg:grid-cols-4">
        {Object.entries(scores).map(([key, val]) => (
          <div
            key={key}
            className="flex items-center justify-between gap-2 text-xs"
          >
            <span className="truncate text-foreground/60">
              {formatMetricLabel(key)}
            </span>
            <span className="tabular-nums font-medium text-foreground/90">
              {typeof val === 'number' ? formatScore(val) : 'N/A'}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function VariantSection({ variant }: { variant: VariantDetail }) {
  return (
    <div className="space-y-3 rounded-lg border border-foreground/8 bg-[oklch(0.16_0.01_260)]/40 px-4 py-3">
      <div className="flex items-center gap-2">
        <span className="text-sm font-semibold text-foreground">
          {variant.variant_id}
        </span>
        {variant.strategy && (
          <span className="text-xs text-muted-foreground">
            {variant.strategy}
          </span>
        )}
      </div>

      <ScoreGrid title="TRIBE v2 Scores" scores={variant.tribe_scores} />
      <ScoreGrid
        title="MiroFish Metrics"
        scores={
          variant.mirofish_metrics as
            | Record<string, number | null>
            | undefined
        }
      />
      <ScoreGrid
        title="Composite Scores"
        scores={variant.composite_scores}
      />
    </div>
  );
}

function IterationSection({
  data,
  isOpen,
  onToggle,
}: {
  data: IterationData;
  isOpen: boolean;
  onToggle: () => void;
}) {
  const variants = data.variants ?? [];
  const analysis = data.analysis;

  return (
    <Collapsible open={isOpen} onOpenChange={onToggle}>
      <CollapsibleTrigger
        className={cn(
          'flex w-full items-center gap-3 rounded-lg border border-foreground/10 px-4 py-3 text-left transition-colors',
          'hover:border-foreground/20 hover:bg-muted/20',
          isOpen && 'border-[oklch(0.40_0.08_250)]/40 bg-[oklch(0.20_0.02_260)]/40',
        )}
      >
        <ChevronRight
          className={cn(
            'size-4 text-muted-foreground transition-transform duration-200',
            isOpen && 'rotate-90',
          )}
        />
        <span className="text-sm font-semibold text-foreground">
          Iteration {data.iteration}
        </span>
        <span className="text-xs text-muted-foreground">
          {variants.length} variant{variants.length !== 1 ? 's' : ''}
        </span>
      </CollapsibleTrigger>
      <CollapsibleContent>
        <div className="mt-2 space-y-4 pl-7">
          {/* Variant data */}
          {variants.map((variant) => (
            <VariantSection key={variant.variant_id} variant={variant} />
          ))}

          {/* Analysis insights */}
          {analysis && (
            <div className="space-y-3 rounded-lg border border-foreground/8 bg-muted/10 px-4 py-3">
              <h6 className="text-[0.7rem] font-semibold tracking-wider text-muted-foreground/80 uppercase">
                Analysis
              </h6>

              {analysis.ranking && analysis.ranking.length > 0 && (
                <div className="space-y-1">
                  <span className="text-xs font-medium text-foreground/70">
                    Ranking:
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {analysis.ranking.map((id, idx) => (
                      <span
                        key={id}
                        className="inline-flex items-center gap-1 rounded-md bg-muted/30 px-2 py-0.5 text-xs"
                      >
                        <span className="font-bold text-foreground/60">
                          {idx + 1}.
                        </span>
                        <span className="text-foreground/80">{id}</span>
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {analysis.cross_system_insights &&
                analysis.cross_system_insights.length > 0 && (
                  <div className="space-y-1.5">
                    <span className="text-xs font-medium text-foreground/70">
                      Cross-System Insights:
                    </span>
                    <ul className="space-y-1">
                      {analysis.cross_system_insights.map(
                        (insight, idx) => (
                          <li
                            key={idx}
                            className="flex gap-2 text-xs leading-relaxed text-foreground/70"
                          >
                            <span className="mt-0.5 shrink-0 text-[oklch(0.55_0.12_250)]">
                              &bull;
                            </span>
                            {insight}
                          </li>
                        ),
                      )}
                    </ul>
                  </div>
                )}
            </div>
          )}
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
}

export function DeepAnalysis({ deepAnalysis, className }: DeepAnalysisProps) {
  const [openSections, setOpenSections] = useState<Set<number>>(new Set());

  if (!deepAnalysis) {
    return (
      <div
        className={cn(
          'flex flex-col items-center justify-center gap-3 py-12 text-center',
          className,
        )}
      >
        <div className="flex size-12 items-center justify-center rounded-xl bg-muted/50">
          <Layers className="size-6 text-muted-foreground/60" />
        </div>
        <p className="text-sm text-muted-foreground">
          Deep analysis not available
        </p>
      </div>
    );
  }

  const iterations = parseIterations(deepAnalysis);

  if (iterations.length === 0) {
    return (
      <div
        className={cn(
          'flex flex-col items-center justify-center gap-3 py-12 text-center',
          className,
        )}
      >
        <div className="flex size-12 items-center justify-center rounded-xl bg-muted/50">
          <Layers className="size-6 text-muted-foreground/60" />
        </div>
        <p className="text-sm text-muted-foreground">
          No iteration data found
        </p>
      </div>
    );
  }

  const allOpen = iterations.every((it) =>
    openSections.has(it.iteration),
  );

  function toggleAll() {
    if (allOpen) {
      setOpenSections(new Set());
    } else {
      setOpenSections(new Set(iterations.map((it) => it.iteration)));
    }
  }

  function toggleSection(iteration: number) {
    setOpenSections((prev) => {
      const next = new Set(prev);
      if (next.has(iteration)) {
        next.delete(iteration);
      } else {
        next.add(iteration);
      }
      return next;
    });
  }

  return (
    <div className={cn('space-y-4', className)}>
      {/* Section header with expand/collapse all */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="flex size-8 items-center justify-center rounded-lg bg-[oklch(0.28_0.04_40)]">
            <Layers className="size-4 text-[oklch(0.75_0.12_40)]" />
          </div>
          <h3 className="text-sm font-semibold tracking-wide text-foreground/90 uppercase">
            Deep Analysis
          </h3>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={toggleAll}
          className="gap-1.5 text-xs text-muted-foreground"
        >
          <ChevronsUpDown className="size-3.5" />
          {allOpen ? 'Collapse all' : 'Expand all'}
        </Button>
      </div>

      {/* Iteration sections */}
      <div className="space-y-2">
        {iterations.map((iteration) => (
          <IterationSection
            key={iteration.iteration}
            data={iteration}
            isOpen={openSections.has(iteration.iteration)}
            onToggle={() => toggleSection(iteration.iteration)}
          />
        ))}
      </div>
    </div>
  );
}
