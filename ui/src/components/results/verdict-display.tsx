/**
 * Layer 1: The Verdict — executive-brief prose.
 *
 * Markdown is rendered via ReactMarkdown through MarkdownProse so
 * headings, bold text, and lists come through from Claude's output
 * rather than showing raw ## and ** symbols.
 */

import { cn } from '@/lib/utils';
import { MarkdownProse } from '@/components/common/markdown-prose';

interface VerdictDisplayProps {
  verdict: string | null | undefined;
  className?: string;
}

export function VerdictDisplay({ verdict, className }: VerdictDisplayProps) {
  if (!verdict) {
    return (
      <div className={cn('space-y-4', className)}>
        <SectionEyebrow label="Verdict" />
        <p className="font-mono text-[0.74rem] text-muted-foreground">
          › report not yet generated
        </p>
      </div>
    );
  }

  return (
    <div className={cn('space-y-5', className)}>
      <SectionEyebrow label="Verdict" />
      <MarkdownProse>{verdict}</MarkdownProse>
    </div>
  );
}

function SectionEyebrow({ label }: { label: string }) {
  return (
    <div className="flex items-baseline gap-3 border-b border-border pb-2">
      <h2 className="text-[1rem] font-medium tracking-[-0.005em] text-foreground">
        {label}
      </h2>
      <span className="font-mono text-[0.62rem] tracking-[0.12em] text-muted-foreground uppercase">
        layer 1
      </span>
    </div>
  );
}
