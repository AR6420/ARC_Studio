/**
 * Layer 4: Mass Psychology — general / technical prose.
 *
 * Segmented control swaps between the two narratives and matches the
 * iteration-pill style (small bordered buttons, filled active state).
 * Prose uses MarkdownProse with the 'editorial' variant for stronger
 * heading/body hierarchy and thin rules between h2 sections.
 */

import { useState } from 'react';
import { cn } from '@/lib/utils';
import { MarkdownProse } from '@/components/common/markdown-prose';

type PsychologyView = 'general' | 'technical';

interface MassPsychologyProps {
  general: string | null | undefined;
  technical: string | null | undefined;
  className?: string;
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
      <div className={cn('space-y-4', className)}>
        <SectionHeader view={view} setView={setView} disabled />
        <p className="font-mono text-[0.74rem] text-muted-foreground">
          › psychology analysis not available
        </p>
      </div>
    );
  }

  const activeText = view === 'general' ? general : technical;
  const isActiveAvailable = view === 'general' ? hasGeneral : hasTechnical;

  return (
    <div className={cn('space-y-5', className)}>
      <SectionHeader
        view={view}
        setView={setView}
        hasGeneral={hasGeneral}
        hasTechnical={hasTechnical}
      />
      {isActiveAvailable && activeText ? (
        <>
          <MarkdownProse variant="editorial">{activeText}</MarkdownProse>
          {view === 'technical' && (
            <p className="mt-6 max-w-[680px] border-t border-border pt-4 font-mono text-[0.68rem] italic text-muted-foreground">
              References threshold models, spiral of silence, emotional contagion.
            </p>
          )}
        </>
      ) : (
        <p className="font-mono text-[0.74rem] text-muted-foreground">
          › {view === 'general' ? 'general' : 'technical'} analysis unavailable
        </p>
      )}
    </div>
  );
}

function SectionHeader({
  view,
  setView,
  hasGeneral = true,
  hasTechnical = true,
  disabled = false,
}: {
  view: PsychologyView;
  setView: (v: PsychologyView) => void;
  hasGeneral?: boolean;
  hasTechnical?: boolean;
  disabled?: boolean;
}) {
  return (
    <div className="flex items-baseline justify-between gap-6 border-b border-border pb-2">
      <div className="flex items-baseline gap-3">
        <h2 className="text-[1rem] font-medium tracking-[-0.005em] text-foreground">
          Mass psychology
        </h2>
        <span className="font-mono text-[0.62rem] tracking-[0.12em] text-muted-foreground uppercase">
          layer 4
        </span>
      </div>
      {!disabled && (
        <div className="flex items-center gap-1">
          <SegmentButton
            active={view === 'general'}
            disabled={!hasGeneral}
            onClick={() => setView('general')}
          >
            general
          </SegmentButton>
          <SegmentButton
            active={view === 'technical'}
            disabled={!hasTechnical}
            onClick={() => setView('technical')}
          >
            technical
          </SegmentButton>
        </div>
      )}
    </div>
  );
}

function SegmentButton({
  active,
  disabled,
  onClick,
  children,
}: {
  active: boolean;
  disabled?: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={() => {
        if (!active && !disabled) onClick();
      }}
      disabled={disabled}
      aria-pressed={active}
      className={cn(
        'inline-flex items-center rounded-sm border px-2 py-0.5 font-mono text-[0.7rem] transition-colors',
        active
          ? 'border-primary/60 bg-primary/15 text-primary cursor-default'
          : 'border-border bg-transparent text-muted-foreground hover:border-foreground/30 hover:text-foreground',
        disabled && 'cursor-not-allowed opacity-40 hover:border-border hover:text-muted-foreground',
      )}
    >
      {children}
    </button>
  );
}
