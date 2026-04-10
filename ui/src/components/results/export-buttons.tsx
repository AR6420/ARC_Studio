/**
 * Minimal export button group — small outline buttons, monospace labels.
 */

import { Download } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { downloadExport } from '@/api/reports';
import { cn } from '@/lib/utils';

interface ExportButtonsProps {
  campaignId: string;
  className?: string;
}

export function ExportButtons({ campaignId, className }: ExportButtonsProps) {
  return (
    <div className={cn('flex items-center gap-1', className)}>
      <Button
        variant="outline"
        size="xs"
        onClick={() => downloadExport(campaignId, 'json')}
        className="gap-1 font-mono"
      >
        <Download className="size-2.5" />
        json
      </Button>
      <Button
        variant="outline"
        size="xs"
        onClick={() => downloadExport(campaignId, 'markdown')}
        className="gap-1 font-mono"
      >
        <Download className="size-2.5" />
        md
      </Button>
    </div>
  );
}
