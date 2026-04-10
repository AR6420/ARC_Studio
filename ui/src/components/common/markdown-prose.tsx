/**
 * MarkdownProse — renders markdown strings from Claude's analysis
 * into properly styled dark-theme prose.
 *
 * Used by Verdict (Layer 1), Deep Analysis (Layer 3), and Mass
 * Psychology (Layer 4). Headings, paragraphs, lists, bold text,
 * and inline code all receive weight, color, and spacing tuned for
 * reading-width columns (max 680px).
 */

import ReactMarkdown, { type Components } from 'react-markdown';
import { cn } from '@/lib/utils';

const markdownComponents: Components = {
  h1: ({ children }) => (
    <h1 className="mt-6 mb-3 text-[1.25rem] font-medium leading-tight tracking-[-0.01em] text-foreground first:mt-0">
      {children}
    </h1>
  ),
  h2: ({ children }) => (
    <h2 className="mt-5 mb-2 text-[1.06rem] font-medium leading-tight tracking-[-0.005em] text-foreground first:mt-0">
      {children}
    </h2>
  ),
  h3: ({ children }) => (
    <h3 className="mt-4 mb-2 text-[0.95rem] font-medium text-foreground first:mt-0">
      {children}
    </h3>
  ),
  h4: ({ children }) => (
    <h4 className="mt-3 mb-1.5 text-[0.88rem] font-medium text-foreground first:mt-0">
      {children}
    </h4>
  ),
  p: ({ children }) => (
    <p className="my-3 text-[0.94rem] leading-[1.7] text-foreground/85 first:mt-0 last:mb-0">
      {children}
    </p>
  ),
  strong: ({ children }) => (
    <strong className="font-semibold text-foreground">{children}</strong>
  ),
  em: ({ children }) => (
    <em className="italic text-foreground/90">{children}</em>
  ),
  ul: ({ children }) => (
    <ul className="my-3 flex flex-col gap-1.5 pl-5 text-[0.94rem] leading-[1.65] text-foreground/85 marker:text-muted-foreground first:mt-0 last:mb-0">
      {children}
    </ul>
  ),
  ol: ({ children }) => (
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

interface MarkdownProseProps {
  children: string | null | undefined;
  className?: string;
  width?: 'reading' | 'full';
}

export function MarkdownProse({
  children,
  className,
  width = 'reading',
}: MarkdownProseProps) {
  if (!children || !children.trim()) return null;
  return (
    <div
      className={cn(
        width === 'reading' ? 'max-w-[680px]' : 'max-w-none',
        className,
      )}
    >
      <ReactMarkdown components={markdownComponents}>{children}</ReactMarkdown>
    </div>
  );
}
