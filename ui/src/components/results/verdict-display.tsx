/**
 * Layer 1: The Verdict — executive-brief prose.
 *
 * Rendered as clean reading-width prose (max 680px), no card wrapper,
 * generous line-height. The section header is a small-caps eyebrow,
 * not a styled box.
 */

import { cn } from '@/lib/utils';

interface VerdictDisplayProps {
  verdict: string | null | undefined;
  className?: string;
}

function renderText(text: string) {
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
      <p key={idx} className="leading-[1.75] text-foreground/85">
        {rendered}
      </p>
    );
  });
}

export function VerdictDisplay({ verdict, className }: VerdictDisplayProps) {
  if (!verdict) {
    return (
      <div className={cn('space-y-4', className)}>
        <SectionEyebrow label="Verdict" />
        <p className="font-mono text-[0.72rem] text-muted-foreground/55">
          › report not yet generated
        </p>
      </div>
    );
  }

  return (
    <div className={cn('space-y-5', className)}>
      <SectionEyebrow label="Verdict" />
      <div className="max-w-[680px] space-y-4 text-[0.92rem]">
        {renderText(verdict)}
      </div>
    </div>
  );
}

function SectionEyebrow({ label }: { label: string }) {
  return (
    <div className="flex items-baseline gap-3 border-b border-border pb-2">
      <span className="font-mono text-[0.6rem] font-semibold tracking-[0.18em] text-foreground/90 uppercase">
        {label}
      </span>
      <span className="font-mono text-[0.58rem] tracking-[0.12em] text-muted-foreground/50 uppercase">
        layer 1
      </span>
    </div>
  );
}
