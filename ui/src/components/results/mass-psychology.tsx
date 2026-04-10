/**
 * Layer 4: Mass Psychology — general / technical prose.
 *
 * Minimal segmented control swaps between the two narratives.
 * Both render as reading-width prose (max 680px) with generous
 * line-height. No boxes.
 */

import { useState } from 'react';
import { cn } from '@/lib/utils';

type PsychologyView = 'general' | 'technical';

interface MassPsychologyProps {
  general: string | null | undefined;
  technical: string | null | undefined;
  className?: string;
}

function renderNarrative(text: string) {
  const paragraphs = text.split(/\n\n+/).filter(Boolean);
  return paragraphs.map((paragraph, idx) => {
    const parts = paragraph.split(/(\*\*[^*]+\*\*)/g);
    const rendered = parts.map((part, pIdx) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        return (
          <strong key={pIdx} className="font-semibold text-foreground">
            {part.slice(2, -2)}
          </strong>
        );
      }
      return <span key={pIdx}>{part}</span>;
    });
    return (
      <p key={idx} className="leading-[1.8] text-foreground/85">
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
      <div className={cn('space-y-4', className)}>
        <SectionHeader view={view} setView={setView} disabled />
        <p className="font-mono text-[0.72rem] text-muted-foreground/55">
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
        <div className="max-w-[680px] space-y-4 text-[0.92rem]">
          {renderNarrative(activeText)}
          {view === 'technical' && (
            <p className="mt-6 border-t border-border pt-4 font-mono text-[0.64rem] italic text-muted-foreground/50">
              References threshold models, spiral of silence, emotional contagion.
            </p>
          )}
        </div>
      ) : (
        <p className="font-mono text-[0.72rem] text-muted-foreground/55">
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
        <span className="font-mono text-[0.6rem] font-semibold tracking-[0.18em] text-foreground/90 uppercase">
          Mass Psychology
        </span>
        <span className="font-mono text-[0.58rem] tracking-[0.12em] text-muted-foreground/50 uppercase">
          layer 4
        </span>
      </div>
      {!disabled && (
        <div className="flex items-center gap-3 font-mono text-[0.62rem] tracking-[0.1em] uppercase">
          <SegmentButton
            active={view === 'general'}
            disabled={!hasGeneral}
            onClick={() => setView('general')}
          >
            general
          </SegmentButton>
          <span className="text-muted-foreground/30">/</span>
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
      onClick={onClick}
      disabled={disabled}
      className={cn(
        'transition-colors duration-150',
        active
          ? 'text-primary'
          : 'text-muted-foreground/60 hover:text-foreground',
        disabled && 'cursor-not-allowed opacity-40 hover:text-muted-foreground/60',
      )}
    >
      {children}
    </button>
  );
}
