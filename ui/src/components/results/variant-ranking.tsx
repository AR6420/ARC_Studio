/**
 * Ranked list of content variants from the latest iteration.
 *
 * Sorts variants by computed overall score (average of non-null composites).
 * Each variant card is expandable (Collapsible) to reveal the full content.
 * Best variant gets a highlighted "Best" badge.
 */

import { useMemo, useState } from 'react';
import { ChevronDown, Trophy } from 'lucide-react';
import { cn } from '@/lib/utils';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
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
      const vals = COMPOSITE_KEYS.map((k) => record.composite_scores![k]).filter(
        (v): v is number => v !== null,
      );
      const avgScore = vals.length > 0 ? vals.reduce((a, b) => a + b, 0) / vals.length : -1;
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
      <p className="text-sm text-muted-foreground">
        No scored variants available.
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      {ranked.map((item) => (
        <VariantCard key={item.record.variant_id} item={item} isBest={item.rank === 1} />
      ))}
    </div>
  );
}

interface VariantCardProps {
  item: RankedVariant;
  isBest: boolean;
}

function VariantCard({ item, isBest }: VariantCardProps) {
  const [open, setOpen] = useState(false);
  const { record, avgScore, rank } = item;
  const strategy = record.variant_strategy ?? `Variant ${record.variant_id.slice(0, 6)}`;

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <div
        className={cn(
          'rounded-xl border bg-card ring-1 ring-foreground/[0.06] transition-all duration-200',
          isBest
            ? 'border-primary/30 ring-primary/10 shadow-[0_0_20px_-4px_oklch(0.65_0.18_250/0.12)]'
            : 'border-transparent',
        )}
      >
        <CollapsibleTrigger className="flex w-full items-center gap-4 px-5 py-4 text-left cursor-pointer group/trigger">
          {/* Rank number */}
          <div
            className={cn(
              'flex size-9 shrink-0 items-center justify-center rounded-lg font-bold text-sm tabular-nums',
              isBest
                ? 'bg-primary/15 text-primary'
                : 'bg-muted text-muted-foreground',
            )}
          >
            {rank}
          </div>

          {/* Strategy + average */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-foreground truncate">
                {strategy}
              </span>
              {isBest && (
                <span className="inline-flex items-center gap-1 rounded-full bg-primary/15 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-primary">
                  <Trophy className="size-2.5" />
                  Best
                </span>
              )}
            </div>
            <span className="text-xs text-muted-foreground">
              Avg score: {avgScore.toFixed(1)}
            </span>
          </div>

          {/* Expand chevron */}
          <ChevronDown
            className={cn(
              'size-4 shrink-0 text-muted-foreground transition-transform duration-200',
              open && 'rotate-180',
            )}
          />
        </CollapsibleTrigger>

        {/* Score bars (always visible) */}
        {record.composite_scores && (
          <div className="px-5 pb-4 grid grid-cols-1 gap-1.5 sm:grid-cols-2">
            {COMPOSITE_KEYS.map((key) => (
              <ScoreBar
                key={key}
                name={key}
                value={record.composite_scores![key]}
              />
            ))}
          </div>
        )}

        {/* Expandable content */}
        <CollapsibleContent>
          <div className="border-t border-border/50 px-5 py-4">
            <h4 className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
              Generated Content
            </h4>
            <div className="rounded-lg bg-muted/30 p-4 text-sm leading-relaxed text-foreground/90 whitespace-pre-wrap">
              {record.variant_content}
            </div>
          </div>
        </CollapsibleContent>
      </div>
    </Collapsible>
  );
}
