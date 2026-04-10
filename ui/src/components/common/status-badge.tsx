/**
 * Status indicators for campaign state.
 *
 * The primary API is StatusDot — a 6px circle, amber for running,
 * muted-green for complete, coral for failed. The old StatusBadge is
 * kept as a compat wrapper that pairs the dot with a monospace label.
 *
 *   running  → amber (heat-mid)
 *   complete → muted green
 *   failed   → coral
 *   pending  → gray
 */

import { cn } from '@/lib/utils';
import type { CampaignStatus } from '@/api/types';

const STATUS_DOT: Record<CampaignStatus, string> = {
  pending: 'bg-[oklch(0.55_0.008_70)]',
  running: 'bg-[oklch(0.80_0.14_75)]',
  completed: 'bg-[oklch(0.72_0.15_150)]',
  failed: 'bg-[oklch(0.68_0.20_22)]',
};

const STATUS_TEXT: Record<CampaignStatus, string> = {
  pending: 'text-muted-foreground/70',
  running: 'text-[oklch(0.80_0.14_75)]',
  completed: 'text-[oklch(0.72_0.15_150)]',
  failed: 'text-[oklch(0.68_0.20_22)]',
};

const STATUS_LABEL: Record<CampaignStatus, string> = {
  pending: 'Pending',
  running: 'Running',
  completed: 'Complete',
  failed: 'Failed',
};

interface StatusDotProps {
  status: CampaignStatus;
  className?: string;
  pulse?: boolean;
}

export function StatusDot({ status, className, pulse = true }: StatusDotProps) {
  return (
    <span
      className={cn(
        'inline-block size-1.5 shrink-0 rounded-full',
        STATUS_DOT[status],
        pulse && status === 'running' && 'animate-pulse',
        className,
      )}
      aria-label={STATUS_LABEL[status]}
    />
  );
}

interface StatusBadgeProps {
  status: CampaignStatus;
  className?: string;
  showLabel?: boolean;
}

/**
 * Dot + monospace label. Used in the campaign detail header.
 * In tables and sidebar use StatusDot alone.
 */
export function StatusBadge({
  status,
  className,
  showLabel = true,
}: StatusBadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 font-mono text-[0.65rem] tracking-[0.1em] uppercase',
        STATUS_TEXT[status],
        className,
      )}
    >
      <StatusDot status={status} />
      {showLabel && <span>{STATUS_LABEL[status]}</span>}
    </span>
  );
}
