/**
 * MarkdownProse — renders markdown strings from Claude's analysis
 * into properly styled dark-theme prose.
 *
 * Used by Verdict (Layer 1), Deep Analysis (Layer 3), and Mass
 * Psychology (Layer 4). Two variants:
 *
 *   default   — balanced weight, used for verdict, summary, insights
 *   editorial — stronger hierarchy for long-form reading: brighter
 *               h2 with rule above, dimmer body, brighter strong
 */

import ReactMarkdown, { type Components } from 'react-markdown';
import { cn } from '@/lib/utils';

type Variant = 'default' | 'editorial';

function buildComponents(variant: Variant): Components {
  const editorial = variant === 'editorial';

  return {
    h1: ({ children }) => (
      <h1
        className={cn(
          'mt-6 mb-3 leading-tight tracking-[-0.01em] text-foreground first:mt-0',
          editorial
            ? 'text-[1.3rem] font-medium'
            : 'text-[1.25rem] font-medium',
        )}
      >
        {children}
      </h1>
    ),
    h2: ({ children }) =>
      editorial ? (
        <h2 className="mt-8 mb-3 border-t border-foreground/[0.1] pt-6 text-[1.125rem] font-medium leading-tight tracking-[-0.005em] text-foreground/95 first:mt-0 first:border-t-0 first:pt-0">
          {children}
        </h2>
      ) : (
        <h2 className="mt-5 mb-2 text-[1.06rem] font-medium leading-tight tracking-[-0.005em] text-foreground first:mt-0">
          {children}
        </h2>
      ),
    h3: ({ children }) => (
      <h3
        className={cn(
          'mt-4 mb-2 font-medium first:mt-0',
          editorial
            ? 'text-[1rem] text-foreground/95'
            : 'text-[0.95rem] text-foreground',
        )}
      >
        {children}
      </h3>
    ),
    h4: ({ children }) => (
      <h4 className="mt-3 mb-1.5 text-[0.9rem] font-medium text-foreground/90 first:mt-0">
        {children}
      </h4>
    ),
    p: ({ children }) =>
      editorial ? (
        <p className="my-3 text-[0.94rem] leading-[1.8] text-foreground/70 first:mt-0 last:mb-0">
          {children}
        </p>
      ) : (
        <p className="my-3 text-[0.94rem] leading-[1.7] text-foreground/85 first:mt-0 last:mb-0">
          {children}
        </p>
      ),
    strong: ({ children }) => (
      <strong
        className={cn(
          'font-semibold',
          editorial ? 'text-foreground/95' : 'text-foreground',
        )}
      >
        {children}
      </strong>
    ),
    em: ({ children }) => (
      <em className="italic text-foreground/90">{children}</em>
    ),
    ul: ({ children }) =>
      editorial ? (
        <ul className="my-3 flex flex-col gap-1.5 pl-5 text-[0.94rem] leading-[1.7] text-foreground/75 marker:text-muted-foreground first:mt-0 last:mb-0">
          {children}
        </ul>
      ) : (
        <ul className="my-3 flex flex-col gap-1.5 pl-5 text-[0.94rem] leading-[1.65] text-foreground/85 marker:text-muted-foreground first:mt-0 last:mb-0">
          {children}
        </ul>
      ),
    ol: ({ children }) =>
      editorial ? (
        <ol className="my-3 flex list-decimal flex-col gap-1.5 pl-5 text-[0.94rem] leading-[1.7] text-foreground/75 marker:text-muted-foreground first:mt-0 last:mb-0">
          {children}
        </ol>
      ) : (
        <ol className="my-3 flex list-decimal flex-col gap-1.5 pl-5 text-[0.94rem] leading-[1.65] text-foreground/85 marker:text-muted-foreground first:mt-0 last:mb-0">
          {children}
        </ol>
      ),
    li: ({ children }) => <li className="list-disc pl-1">{children}</li>,
    blockquote: ({ children }) => (
      <blockquote className="my-3 border-l-2 border-border pl-4 text-foreground/75 italic">
        {children}
      </blockquote>
    ),
    code: ({ children }) => (
      <code className="rounded-sm bg-foreground/[0.06] px-1 py-0.5 font-mono text-[0.85em] text-foreground/90">
        {children}
      </code>
    ),
    a: ({ children, href }) => (
      <a
        href={href}
        className="text-primary underline-offset-4 hover:underline"
        target="_blank"
        rel="noreferrer"
      >
        {children}
      </a>
    ),
    hr: () => <hr className="my-6 border-border" />,
  };
}

const componentsByVariant: Record<Variant, Components> = {
  default: buildComponents('default'),
  editorial: buildComponents('editorial'),
};

interface MarkdownProseProps {
  children: string | null | undefined;
  className?: string;
  width?: 'reading' | 'full';
  variant?: Variant;
}

export function MarkdownProse({
  children,
  className,
  width = 'reading',
  variant = 'default',
}: MarkdownProseProps) {
  if (!children || !children.trim()) return null;
  return (
    <div
      className={cn(
        width === 'reading' ? 'max-w-[680px]' : 'max-w-none',
        className,
      )}
    >
      <ReactMarkdown components={componentsByVariant[variant]}>
        {children}
      </ReactMarkdown>
    </div>
  );
}
