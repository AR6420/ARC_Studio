/**
 * Variant ranking — dense, collapsible list of scored variants.
 *
 *   01  anchored-value     78.4  ████████████████░░░░  ← best (amber bar)
 *   02  benefit-lead       71.2  ██████████████░░░░░░
 *   03  story-framed       62.8  ████████████░░░░░░░░
 *
 * The #1 ranked variant gets a 2px amber left border. Expanding a row
 * reveals all 7 composite score bars and the generated variant content
 * in a monospace preview block.
 */

import { useMemo, useState } from 'react';
import { ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';
import { getHeatStop, HEAT_VARS, HEAT_TEXT } from '@/utils/colors';
import { ScoreBar } from '@/components/results/score-bar';
import type { IterationRecord, CompositeScores } from '@/api/types';

const COMPOSITE_KEYS: (keyof CompositeScores)[] = [
  'attention_score',
  'virality_potential',
  'conversion_potential',
  'audience_fit',
  'memory_durability',
  'backlash_risk',
  'polarization_index',
];

interface RankedVariant {
  record: IterationRecord;
  avgScore: number;
  rank: number;
}

function computeRanking(variants: IterationRecord[]): RankedVariant[] {
  const scored = variants
    .map((record) => {
      if (!record.composite_scores) return { record, avgScore: -1 };
      const vals = COMPOSITE_KEYS.map(
        (k) => record.composite_scores![k],
      ).filter((v): v is number => v !== null);
      const avgScore =
        vals.length > 0 ? vals.reduce((a, b) => a + b, 0) / vals.length : -1;
      return { record, avgScore };
    })
    .filter((v) => v.avgScore >= 0)
    .sort((a, b) => b.avgScore - a.avgScore);
  return scored.map((item, i) => ({ ...item, rank: i + 1 }));
}

interface VariantRankingProps {
  variants: IterationRecord[];
}

export function VariantRanking({ variants }: VariantRankingProps) {
  const ranked = useMemo(() => computeRanking(variants), [variants]);

  if (!ranked.length) {
    return (
      <p className="font-mono text-[0.74rem] text-muted-foreground">
        › no scored variants available
      </p>
    );
  }

  return (
    <div className="divide-y divide-border border-y border-border">
      {ranked.map((item) => (
        <VariantRow
          key={item.record.variant_id}
          item={item}
          isBest={item.rank === 1}
        />
      ))}
    </div>
  );
}

function VariantRow({ item, isBest }: { item: RankedVariant; isBest: boolean }) {
  const [open, setOpen] = useState(false);
  const { record, avgScore, rank } = item;
  const strategy =
    record.variant_strategy ?? `Variant ${record.variant_id.slice(0, 6)}`;
  const isPseudo = record.tribe_scores?.is_pseudo_score === true;
  const heatStop = getHeatStop('attention_score', avgScore);
  const avgPercent = Math.min(Math.max(avgScore, 0), 100);

  return (
    <div
      className={cn(
        'relative',
        // #1 variant: 2px amber left border + slightly lighter background
        isBest && 'bg-foreground/[0.03] shadow-[inset_2px_0_0_var(--primary)]',
      )}
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className={cn(
          'grid w-full grid-cols-[20px_32px_minmax(0,1fr)_70px_minmax(0,140px)_16px] items-center gap-3 px-2 py-2.5 text-left transition-colors',
          'hover:bg-foreground/[0.025]',
          isBest && 'pl-3',
        )}
      >
        <ChevronRight
          className={cn(
            'size-3 text-muted-foreground transition-transform duration-150',
            open && 'rotate-90',
          )}
        />
        <span
          className={cn(
            'font-mono text-[0.74rem] tabular-nums',
            isBest ? 'text-primary' : 'text-foreground/70',
          )}
        >
          {rank.toString().padStart(2, '0')}
        </span>
        <div className="flex items-center gap-2 min-w-0">
          <span className="truncate text-[0.82rem] text-foreground/90">
            {strategy}
          </span>
          {isBest && (
            <span className="font-mono text-[0.58rem] tracking-[0.12em] text-primary uppercase">
              best
            </span>
          )}
          {isPseudo && (
            <span
              className="font-mono text-[0.58rem] tracking-[0.08em] text-muted-foreground uppercase"
              title="Scored using pseudo fallback data (TRIBE unavailable)"
            >
              pseudo
            </span>
          )}
        </div>
        <span
          className={cn(
            'text-right font-mono text-[0.9rem] font-semibold tabular-nums',
            HEAT_TEXT[heatStop],
          )}
        >
          {avgScore.toFixed(1)}
        </span>
        <div className="relative h-[3px] w-full overflow-hidden rounded-[1px] bg-foreground/[0.08]">
          <div
            className="absolute inset-y-0 left-0 rounded-[1px]"
            style={{
              width: `${avgPercent}%`,
              background: HEAT_VARS[heatStop],
            }}
          />
        </div>
        <span className="text-right font-mono text-[0.62rem] tabular-nums text-muted-foreground">
          {record.variant_id.slice(0, 4)}
        </span>
      </button>

      {open && (
        <div className="space-y-4 border-t border-border bg-surface-1/50 px-6 py-4">
          {record.composite_scores && (
            <div className="grid grid-cols-1 gap-1.5 sm:grid-cols-2 sm:gap-x-8">
              {COMPOSITE_KEYS.map((key) => (
                <ScoreBar
                  key={key}
                  name={key}
                  value={record.composite_scores![key]}
                  compact
                />
              ))}
            </div>
          )}
          <div className="space-y-1.5">
            <span className="font-mono text-[0.6rem] tracking-[0.14em] text-muted-foreground uppercase">
              Generated Content
            </span>
            <pre className="max-h-80 overflow-y-auto whitespace-pre-wrap border-l border-border bg-sidebar px-4 py-3 font-mono text-[0.76rem] leading-[1.65] text-foreground/85">
              {record.variant_content}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}
