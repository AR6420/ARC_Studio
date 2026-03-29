/**
 * Export buttons for downloading campaign report data.
 *
 * JSON and Markdown export buttons that trigger browser file downloads
 * via window.open() per Pitfall 7 (no auth needed in POC).
 */

import { Download } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { downloadExport } from '@/api/reports';

interface ExportButtonsProps {
  campaignId: string;
  className?: string;
}

export function ExportButtons({ campaignId, className }: ExportButtonsProps) {
  return (
    <div className={className}>
      <div className="flex items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={() => downloadExport(campaignId, 'json')}
          className="gap-1.5 text-xs"
        >
          <Download className="size-3.5" data-icon="inline-start" />
          Export JSON
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => downloadExport(campaignId, 'markdown')}
          className="gap-1.5 text-xs"
        >
          <Download className="size-3.5" data-icon="inline-start" />
          Export Markdown
        </Button>
      </div>
    </div>
  );
}
