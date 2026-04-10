/**
 * Layer 3: Deep Analysis — developer tools aesthetic.
 *
 * Collapsible per-iteration sections rendered as a monospace tree.
 * Looks like a console panel, feels like drilling into a stack trace.
 * Sub-sections: TRIBE scores, MiroFish metrics, Composite scores.
 */

import { useState } from 'react';
import { ChevronRight } from 'lucide-react';
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

function parseIterations(data: Record<string, unknown>): IterationData[] {
  if (Array.isArray(data.iterations)) return data.iterations as IterationData[];
  if (Array.isArray(data)) return data as IterationData[];
  return [];
}

function ScoreGrid({
  title,
  system,
  scores,
}: {
  title: string;
  system: 'tribe' | 'mirofish' | 'composite';
  scores: Record<string, number | null> | undefined;
}) {
  if (!scores || Object.keys(scores).length === 0) return null;

  const tagClass =
    system === 'tribe'
      ? 'text-tribe/80'
      : system === 'mirofish'
        ? 'text-mirofish/80'
        : 'text-primary/80';

  return (
    <div className="space-y-1.5">
      <div className="flex items-baseline gap-2">
        <span className="font-mono text-[0.56rem] tracking-[0.14em] text-muted-foreground/70 uppercase">
          {title}
        </span>
        <span className={cn('font-mono text-[0.54rem] tracking-[0.1em] uppercase', tagClass)}>
          {system}
        </span>
      </div>
      <div className="grid grid-cols-2 gap-x-6 gap-y-0.5 sm:grid-cols-3 lg:grid-cols-4">
        {Object.entries(scores).map(([key, val]) => (
          <div
            key={key}
            className="flex items-baseline justify-between gap-2 font-mono text-[0.7rem]"
          >
            <span className="truncate text-foreground/55">
              {formatMetricLabel(key)}
            </span>
            <span className="tabular-nums text-foreground/90">
              {typeof val === 'number' ? formatScore(val) : '—'}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function VariantSection({ variant }: { variant: VariantDetail }) {
  return (
    <div className="space-y-3 border-l border-border bg-surface-1/40 px-4 py-3">
      <div className="flex items-baseline gap-2">
        <span className="font-mono text-[0.74rem] font-semibold text-foreground">
          {variant.variant_id}
        </span>
        {variant.strategy && (
          <span className="font-mono text-[0.66rem] text-muted-foreground/60">
            {variant.strategy}
          </span>
        )}
      </div>
      <ScoreGrid title="Tribe Scores" system="tribe" scores={variant.tribe_scores} />
      <ScoreGrid
        title="MiroFish Metrics"
        system="mirofish"
        scores={variant.mirofish_metrics as Record<string, number | null> | undefined}
      />
      <ScoreGrid
        title="Composite Scores"
        system="composite"
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
    <div>
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center gap-2 px-2 py-2 text-left transition-colors hover:bg-foreground/[0.025]"
      >
        <ChevronRight
          className={cn(
            'size-3 text-muted-foreground/60 transition-transform duration-150',
            isOpen && 'rotate-90',
          )}
        />
        <span className="font-mono text-[0.72rem] font-semibold text-foreground">
          iteration_{data.iteration}
        </span>
        <span className="font-mono text-[0.62rem] text-muted-foreground/55">
          · {variants.length} variant{variants.length !== 1 ? 's' : ''}
        </span>
      </button>
      {isOpen && (
        <div className="space-y-3 border-l border-border/60 pl-6 pt-1 pb-3 ml-[14px]">
          {variants.map((variant) => (
            <VariantSection key={variant.variant_id} variant={variant} />
          ))}
          {analysis && (
            <div className="space-y-2 border-l border-border bg-surface-1/40 px-4 py-3">
              <span className="font-mono text-[0.56rem] tracking-[0.14em] text-muted-foreground/70 uppercase">
                Analysis
              </span>
              {analysis.ranking && analysis.ranking.length > 0 && (
                <div className="flex flex-wrap items-center gap-1.5 font-mono text-[0.7rem]">
                  <span className="text-muted-foreground/55">ranking →</span>
                  {analysis.ranking.map((id, idx) => (
                    <span key={id} className="text-foreground/80">
                      {id}
                      {idx < analysis.ranking!.length - 1 && (
                        <span className="ml-1.5 text-muted-foreground/30">›</span>
                      )}
                    </span>
                  ))}
                </div>
              )}
              {analysis.cross_system_insights &&
                analysis.cross_system_insights.length > 0 && (
                  <ul className="space-y-1 font-mono text-[0.7rem] leading-[1.55]">
                    {analysis.cross_system_insights.map((insight, idx) => (
                      <li
                        key={idx}
                        className="flex gap-2 text-foreground/70"
                      >
                        <span className="shrink-0 text-primary/60">›</span>
                        <span>{insight}</span>
                      </li>
                    ))}
                  </ul>
                )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function DeepAnalysis({ deepAnalysis, className }: DeepAnalysisProps) {
  const [openSections, setOpenSections] = useState<Set<number>>(new Set());

  if (!deepAnalysis) {
    return (
      <div className={cn('space-y-4', className)}>
        <SectionHeader disabled />
        <p className="font-mono text-[0.72rem] text-muted-foreground/55">
          › deep analysis not available
        </p>
      </div>
    );
  }

  const iterations = parseIterations(deepAnalysis);
  if (iterations.length === 0) {
    return (
      <div className={cn('space-y-4', className)}>
        <SectionHeader disabled />
        <p className="font-mono text-[0.72rem] text-muted-foreground/55">
          › no iteration data
        </p>
      </div>
    );
  }

  const allOpen = iterations.every((it) => openSections.has(it.iteration));

  function toggleAll() {
    if (allOpen) setOpenSections(new Set());
    else setOpenSections(new Set(iterations.map((it) => it.iteration)));
  }

  function toggleSection(iteration: number) {
    setOpenSections((prev) => {
      const next = new Set(prev);
      if (next.has(iteration)) next.delete(iteration);
      else next.add(iteration);
      return next;
    });
  }

  return (
    <div className={cn('space-y-4', className)}>
      <SectionHeader
        onToggleAll={toggleAll}
        allOpen={allOpen}
      />
      <div className="divide-y divide-border border-y border-border">
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

function SectionHeader({
  onToggleAll,
  allOpen,
  disabled,
}: {
  onToggleAll?: () => void;
  allOpen?: boolean;
  disabled?: boolean;
}) {
  return (
    <div className="flex items-baseline justify-between gap-6 border-b border-border pb-2">
      <div className="flex items-baseline gap-3">
        <span className="font-mono text-[0.6rem] font-semibold tracking-[0.18em] text-foreground/90 uppercase">
          Deep Analysis
        </span>
        <span className="font-mono text-[0.58rem] tracking-[0.12em] text-muted-foreground/50 uppercase">
          layer 3
        </span>
      </div>
      {!disabled && onToggleAll && (
        <Button
          variant="ghost"
          size="xs"
          onClick={onToggleAll}
          className="font-mono"
        >
          {allOpen ? 'collapse all' : 'expand all'}
        </Button>
      )}
    </div>
  );
}
