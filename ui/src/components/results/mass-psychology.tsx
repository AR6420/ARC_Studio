/**
 * Layer 4: Mass Psychology - Crowd dynamics narrative.
 *
 * Toggle between General (accessible prose) and Technical
 * (psychology theory references) views. Per RPT-04 / RPT-05.
 *
 * Design per D-07: scholarly feel with distinct typographic treatment.
 * Technical mode uses a slightly different aesthetic to convey academic weight.
 */

import { useState } from 'react';
import { Brain } from 'lucide-react';
import { cn } from '@/lib/utils';

type PsychologyView = 'general' | 'technical';

interface MassPsychologyProps {
  general: string | null | undefined;
  technical: string | null | undefined;
  className?: string;
}

/** Render text with paragraph breaks and basic bold formatting. */
function renderNarrative(text: string, isTechnical: boolean) {
  const paragraphs = text.split(/\n\n+/).filter(Boolean);

  return paragraphs.map((paragraph, idx) => {
    // Process bold markers
    const parts = paragraph.split(/(\*\*[^*]+\*\*)/g);
    const rendered = parts.map((part, pIdx) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        return (
          <strong
            key={pIdx}
            className={cn(
              'font-semibold',
              isTechnical
                ? 'text-[oklch(0.72_0.10_300)]'
                : 'text-foreground',
            )}
          >
            {part.slice(2, -2)}
          </strong>
        );
      }
      return <span key={pIdx}>{part}</span>;
    });

    return (
      <p
        key={idx}
        className={cn(
          'leading-[1.9]',
          isTechnical
            ? 'text-foreground/80'
            : 'text-foreground/85',
        )}
      >
        {rendered}
      </p>
    );
  });
}

export function MassPsychology({
  general,
  technical,
  className,
}: MassPsychologyProps) {
  const [view, setView] = useState<PsychologyView>('general');

  const hasGeneral = !!general;
  const hasTechnical = !!technical;

  if (!hasGeneral && !hasTechnical) {
    return (
      <div
        className={cn(
          'flex flex-col items-center justify-center gap-3 py-12 text-center',
          className,
        )}
      >
        <div className="flex size-12 items-center justify-center rounded-xl bg-muted/50">
          <Brain className="size-6 text-muted-foreground/60" />
        </div>
        <p className="text-sm text-muted-foreground">
          Psychology analysis not available
        </p>
      </div>
    );
  }

  const activeText = view === 'general' ? general : technical;
  const isActiveAvailable = view === 'general' ? hasGeneral : hasTechnical;

  return (
    <div className={cn('space-y-4', className)}>
      {/* Section header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="flex size-8 items-center justify-center rounded-lg bg-[oklch(0.28_0.04_300)]">
            <Brain className="size-4 text-[oklch(0.72_0.12_300)]" />
          </div>
          <h3 className="text-sm font-semibold tracking-wide text-foreground/90 uppercase">
            Mass Psychology
          </h3>
        </div>

        {/* General / Technical toggle */}
        <div className="flex overflow-hidden rounded-lg border border-foreground/10 bg-muted/20">
          <button
            type="button"
            onClick={() => setView('general')}
            disabled={!hasGeneral}
            className={cn(
              'px-3.5 py-1.5 text-xs font-medium transition-colors',
              view === 'general'
                ? 'bg-[oklch(0.28_0.05_250)] text-[oklch(0.80_0.12_250)]'
                : 'text-muted-foreground hover:text-foreground',
              !hasGeneral && 'cursor-not-allowed opacity-40',
            )}
          >
            General
          </button>
          <button
            type="button"
            onClick={() => setView('technical')}
            disabled={!hasTechnical}
            className={cn(
              'border-l border-foreground/10 px-3.5 py-1.5 text-xs font-medium transition-colors',
              view === 'technical'
                ? 'bg-[oklch(0.28_0.04_300)] text-[oklch(0.72_0.12_300)]'
                : 'text-muted-foreground hover:text-foreground',
              !hasTechnical && 'cursor-not-allowed opacity-40',
            )}
          >
            Technical
          </button>
        </div>
      </div>

      {/* Content area */}
      {isActiveAvailable && activeText ? (
        <div
          className={cn(
            'rounded-xl border px-7 py-6',
            view === 'technical'
              ? 'border-[oklch(0.35_0.03_300)]/40 bg-[oklch(0.17_0.01_290)]/50'
              : 'border-foreground/8 bg-muted/10',
          )}
        >
          <div
            className={cn(
              'max-w-prose space-y-4',
              view === 'technical' ? 'text-[0.9rem]' : 'text-[0.92rem]',
            )}
          >
            {renderNarrative(activeText, view === 'technical')}
          </div>

          {/* Technical mode watermark */}
          {view === 'technical' && (
            <div className="mt-6 border-t border-foreground/5 pt-4">
              <p className="text-[0.7rem] italic text-muted-foreground/50">
                References established social psychology frameworks including
                threshold models, spiral of silence, and emotional contagion
                theory.
              </p>
            </div>
          )}
        </div>
      ) : (
        <div className="flex items-center justify-center py-8">
          <p className="text-sm text-muted-foreground">
            {view === 'general'
              ? 'General analysis not available'
              : 'Technical analysis not available'}
          </p>
        </div>
      )}
    </div>
  );
}
