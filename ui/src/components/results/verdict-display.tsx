/**
 * Layer 1: The Verdict - Plain English recommendation.
 *
 * Executive-brief style display for the campaign verdict.
 * Renders as a prominent text block with elegant typography,
 * generous line height, and comfortable reading width.
 * Per RPT-01: 100-400 words, no jargon.
 */

import { FileText } from 'lucide-react';
import { cn } from '@/lib/utils';

interface VerdictDisplayProps {
  verdict: string | null | undefined;
  className?: string;
}

/**
 * Render verdict text with basic markdown-like formatting.
 * Handles paragraphs (double newline) and bold (**text**).
 */
function renderVerdictText(text: string) {
  const paragraphs = text.split(/\n\n+/).filter(Boolean);

  return paragraphs.map((paragraph, idx) => {
    // Process bold markers
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
      <p key={idx} className="leading-[1.85] text-foreground/85">
        {rendered}
      </p>
    );
  });
}

export function VerdictDisplay({ verdict, className }: VerdictDisplayProps) {
  if (!verdict) {
    return (
      <div
        className={cn(
          'flex flex-col items-center justify-center gap-3 py-12 text-center',
          className,
        )}
      >
        <div className="flex size-12 items-center justify-center rounded-xl bg-muted/50">
          <FileText className="size-6 text-muted-foreground/60" />
        </div>
        <p className="text-sm text-muted-foreground">
          Report not yet generated
        </p>
      </div>
    );
  }

  return (
    <div className={cn('space-y-1', className)}>
      <div className="mb-4 flex items-center gap-2.5">
        <div className="flex size-8 items-center justify-center rounded-lg bg-[oklch(0.30_0.06_250)]">
          <FileText className="size-4 text-[oklch(0.78_0.14_250)]" />
        </div>
        <h3 className="text-sm font-semibold tracking-wide text-foreground/90 uppercase">
          The Verdict
        </h3>
      </div>
      <div
        className={cn(
          'relative rounded-xl border border-[oklch(0.35_0.04_250)] bg-[oklch(0.18_0.015_260)]/60 px-7 py-6',
          'before:absolute before:inset-y-4 before:left-0 before:w-[3px] before:rounded-full before:bg-[oklch(0.55_0.12_250)]',
        )}
      >
        <div className="max-w-prose space-y-4 text-[0.92rem]">
          {renderVerdictText(verdict)}
        </div>
      </div>
    </div>
  );
}
