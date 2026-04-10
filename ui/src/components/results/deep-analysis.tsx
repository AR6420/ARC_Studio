/**
 * Layer 3: Deep Analysis — developer tools aesthetic.
 *
 * Collapsible per-iteration sections rendered as a monospace tree.
 * Looks like a console panel, feels like drilling into a stack trace.
 * Cross-system insights and any string analysis fields are rendered
 * through MarkdownProse so bold/lists/headings come through from
 * Claude's analysis output.
 */

import { useState } from 'react';
import { ChevronRight } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { formatScore, formatMetricLabel } from '@/utils/formatters';
import { MarkdownProse } from '@/components/common/markdown-prose';

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

type ScoreSystem = 'tribe' | 'mirofish' | 'composite';

const SYSTEM_LABEL: Record<
  ScoreSystem,
  { category: string; unit: string; color: string; mono: boolean }
> = {
  tribe: { category: 'TRIBE', unit: 'scores', color: 'text-tribe', mono: true },
  mirofish: {
    category: 'MiroFish',
    unit: 'metrics',
    color: 'text-mirofish',
    mono: false,
  },
  composite: {
    category: 'Composite',
    unit: 'scores',
    color: 'text-primary',
    mono: false,
  },
};

function ScoreGrid({
  system,
  scores,
}: {
  system: ScoreSystem;
  scores: Record<string, number | null> | undefined;
}) {
  if (!scores || Object.keys(scores).length === 0) return null;

  const info = SYSTEM_LABEL[system];

  return (
    <div className="space-y-1.5">
      <h6 className="flex items-baseline gap-1.5 text-[0.82rem] font-medium">
        <span
          className={cn(
            info.color,
            info.mono && 'font-mono tracking-[0.04em]',
          )}
        >
          {info.category}
        </span>
        <span className="text-muted-foreground font-normal">{info.unit}</span>
      </h6>
      <div className="grid grid-cols-2 gap-x-6 gap-y-0.5 sm:grid-cols-3 lg:grid-cols-4">
        {Object.entries(scores).map(([key, val]) => (
          <div
            key={key}
            className="flex items-baseline justify-between gap-2 font-mono text-[0.72rem]"
          >
            <span className="truncate text-foreground/65">
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
    <div className="space-y-3 border-l border-border bg-surface-1/50 px-4 py-3">
      <div className="flex items-baseline gap-2">
        <span className="font-mono text-[0.76rem] font-semibold text-foreground">
          {variant.variant_id}
        </span>
        {variant.strategy && (
          <span className="font-mono text-[0.68rem] text-muted-foreground">
            {variant.strategy}
          </span>
        )}
      </div>
      <ScoreGrid system="tribe" scores={variant.tribe_scores} />
      <ScoreGrid
        system="mirofish"
        scores={variant.mirofish_metrics as Record<string, number | null> | undefined}
      />
      <ScoreGrid system="composite" scores={variant.composite_scores} />
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
            'size-3 text-muted-foreground transition-transform duration-150',
            isOpen && 'rotate-90',
          )}
        />
        <span className="font-mono text-[0.74rem] font-semibold text-foreground">
          iteration_{data.iteration}
        </span>
        <span className="font-mono text-[0.64rem] text-muted-foreground">
          · {variants.length} variant{variants.length !== 1 ? 's' : ''}
        </span>
      </button>
      {isOpen && (
        <div className="space-y-3 border-l border-border/60 pl-6 pt-1 pb-3 ml-[14px]">
          {variants.map((variant) => (
            <VariantSection key={variant.variant_id} variant={variant} />
          ))}
          {analysis && (
            <div className="space-y-3 border-l border-border bg-surface-1/50 px-4 py-3">
              <span className="font-mono text-[0.6rem] tracking-[0.14em] text-muted-foreground uppercase">
                Analysis
              </span>
              {analysis.ranking && analysis.ranking.length > 0 && (
                <div className="flex flex-wrap items-center gap-1.5 font-mono text-[0.72rem]">
                  <span className="text-muted-foreground">ranking →</span>
                  {analysis.ranking.map((id, idx) => (
                    <span key={id} className="text-foreground/85">
                      {id}
                      {idx < analysis.ranking!.length - 1 && (
                        <span className="ml-1.5 text-muted-foreground/60">›</span>
                      )}
                    </span>
                  ))}
                </div>
              )}
              {analysis.cross_system_insights &&
                analysis.cross_system_insights.length > 0 && (
                  <div className="space-y-2">
                    <span className="font-mono text-[0.6rem] tracking-[0.14em] text-muted-foreground uppercase">
                      Cross-system insights
                    </span>
                    <div className="flex flex-col gap-2">
                      {analysis.cross_system_insights.map((insight, idx) => (
                        <div
                          key={idx}
                          className="flex gap-2"
                        >
                          <span className="mt-[10px] shrink-0 text-muted-foreground">›</span>
                          <MarkdownProse width="full" className="flex-1">
                            {insight}
                          </MarkdownProse>
                        </div>
                      ))}
                    </div>
                  </div>
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
        <p className="font-mono text-[0.74rem] text-muted-foreground">
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
        <p className="font-mono text-[0.74rem] text-muted-foreground">
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
        <h2 className="text-[1rem] font-medium tracking-[-0.005em] text-foreground">
          Deep analysis
        </h2>
        <span className="font-mono text-[0.62rem] tracking-[0.12em] text-muted-foreground uppercase">
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
