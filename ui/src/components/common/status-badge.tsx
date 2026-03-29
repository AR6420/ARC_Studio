/**
 * Campaign status badge with icon and color-coded styling.
 *
 * Uses lucide-react icons and tailored color schemes for each campaign state.
 * Running status gets a pulse animation for live feedback.
 */

import { Clock, Play, CheckCircle2, XCircle } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import type { CampaignStatus } from '@/api/types';

const statusConfig: Record<
  CampaignStatus,
  {
    label: string;
    icon: typeof Clock;
    className: string;
  }
> = {
  pending: {
    label: 'Pending',
    icon: Clock,
    className:
      'bg-muted/60 text-muted-foreground border-muted-foreground/20',
  },
  running: {
    label: 'Running',
    icon: Play,
    className:
      'bg-[oklch(0.30_0.06_250)] text-[oklch(0.78_0.14_250)] border-[oklch(0.45_0.10_250)]',
  },
  completed: {
    label: 'Completed',
    icon: CheckCircle2,
    className:
      'bg-[oklch(0.25_0.05_163)] text-[oklch(0.78_0.16_163)] border-[oklch(0.40_0.08_163)]',
  },
  failed: {
    label: 'Failed',
    icon: XCircle,
    className:
      'bg-destructive/15 text-destructive border-destructive/30',
  },
};

interface StatusBadgeProps {
  status: CampaignStatus;
  className?: string;
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const config = statusConfig[status];
  const Icon = config.icon;

  return (
    <Badge
      variant="outline"
      className={cn(
        'gap-1.5 px-2.5 py-0.5 text-[0.7rem] font-semibold tracking-wide uppercase',
        config.className,
        status === 'running' && 'animate-pulse',
        className,
      )}
    >
      <Icon className="size-3" />
      {config.label}
    </Badge>
  );
}
