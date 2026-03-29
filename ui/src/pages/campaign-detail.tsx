/**
 * Campaign detail page with 3 tabs: Campaign, Simulation, Report.
 *
 * Uses React Router useParams for campaign ID, fetches data via
 * useCampaign hook, and renders tab-specific content. The Report tab
 * is fully wired with all 4 report layers and export functionality.
 *
 * Campaign and Simulation tab content are placeholders until
 * plans 08-05 and 08-06 wire their respective components.
 */

import { useParams } from 'react-router-dom';
import { FileBarChart, Activity, FileText, Clock } from 'lucide-react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Separator } from '@/components/ui/separator';
import { Skeleton } from '@/components/ui/skeleton';
import { StatusBadge } from '@/components/common/status-badge';
import { ErrorState } from '@/components/common/error-state';
import { CampaignDetailSkeleton } from '@/components/common/loading-skeleton';
import { useCampaign } from '@/hooks/use-campaigns';
import { useReport } from '@/hooks/use-report';
import { VerdictDisplay } from '@/components/results/verdict-display';
import { ScorecardTable } from '@/components/results/scorecard-table';
import { DeepAnalysis } from '@/components/results/deep-analysis';
import { MassPsychology } from '@/components/results/mass-psychology';
import { ExportButtons } from '@/components/results/export-buttons';
import { formatDate } from '@/utils/formatters';
import type { CampaignResponse } from '@/api/types';

/** Report tab skeleton for loading state. */
function ReportSkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-6 w-48" />
      <div className="space-y-3">
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-5/6" />
        <Skeleton className="h-4 w-4/6" />
      </div>
      <Skeleton className="h-32 w-full" />
      <Skeleton className="h-48 w-full" />
    </div>
  );
}

/** Report tab content with all 4 layers + export buttons. */
function ReportTabContent({ campaign }: { campaign: CampaignResponse }) {
  const {
    data: report,
    isLoading,
    isError,
    error,
    refetch,
  } = useReport(campaign.id);

  if (campaign.status !== 'completed') {
    return (
      <div className="flex flex-col items-center justify-center gap-3 py-16 text-center">
        <div className="flex size-12 items-center justify-center rounded-xl bg-muted/50">
          <Clock className="size-6 text-muted-foreground/60" />
        </div>
        <p className="text-sm font-medium text-foreground/80">
          Campaign must complete before report is available
        </p>
        <p className="text-xs text-muted-foreground">
          The report will be generated once all iterations finish.
        </p>
      </div>
    );
  }

  if (isLoading) {
    return <ReportSkeleton />;
  }

  if (isError) {
    const message =
      error instanceof Error ? error.message : 'Failed to load report';
    // 404 means report not yet generated
    if (message.includes('404') || message.includes('not found')) {
      return (
        <div className="flex flex-col items-center justify-center gap-3 py-16 text-center">
          <div className="flex size-12 items-center justify-center rounded-xl bg-muted/50">
            <FileText className="size-6 text-muted-foreground/60" />
          </div>
          <p className="text-sm font-medium text-foreground/80">
            Report not yet generated
          </p>
          <p className="text-xs text-muted-foreground">
            The report generation may still be in progress.
          </p>
        </div>
      );
    }
    return (
      <ErrorState
        message={message}
        onRetry={() => void refetch()}
      />
    );
  }

  if (!report) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 py-16 text-center">
        <div className="flex size-12 items-center justify-center rounded-xl bg-muted/50">
          <FileText className="size-6 text-muted-foreground/60" />
        </div>
        <p className="text-sm text-muted-foreground">
          No report data available
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Export buttons - top right */}
      <div className="flex justify-end">
        <ExportButtons campaignId={campaign.id} />
      </div>

      {/* Layer 1: Verdict */}
      <VerdictDisplay verdict={report.verdict ?? null} />

      <Separator className="opacity-40" />

      {/* Layer 2: Scorecard */}
      <ScorecardTable scorecard={report.scorecard ?? null} />

      <Separator className="opacity-40" />

      {/* Layer 3: Deep Analysis (collapsed by default) */}
      <DeepAnalysis
        deepAnalysis={
          (report.deep_analysis as Record<string, unknown>) ?? null
        }
      />

      <Separator className="opacity-40" />

      {/* Layer 4: Mass Psychology */}
      <MassPsychology
        general={report.mass_psychology_general ?? null}
        technical={report.mass_psychology_technical ?? null}
      />
    </div>
  );
}

export default function CampaignDetail() {
  const { id } = useParams<{ id: string }>();
  const { data: campaign, isLoading, isError, error, refetch } = useCampaign(id!);

  if (isLoading) {
    return <CampaignDetailSkeleton />;
  }

  if (isError || !campaign) {
    return (
      <ErrorState
        message={
          error instanceof Error
            ? error.message
            : 'Failed to load campaign'
        }
        onRetry={() => void refetch()}
      />
    );
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Campaign header */}
      <div className="flex flex-col gap-2">
        <div className="flex items-center justify-between">
          <h1 className="text-lg font-semibold text-foreground">
            {campaign.prediction_question}
          </h1>
          <StatusBadge status={campaign.status} />
        </div>
        <div className="flex items-center gap-3 text-xs text-muted-foreground">
          <span>{campaign.demographic}</span>
          <span className="text-foreground/20">&middot;</span>
          <span>
            {campaign.agent_count} agents, {campaign.max_iterations} iterations
          </span>
          <span className="text-foreground/20">&middot;</span>
          <span>{formatDate(campaign.created_at)}</span>
        </div>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="report">
        <TabsList variant="line" className="gap-0">
          <TabsTrigger value="campaign" className="gap-1.5">
            <FileBarChart className="size-3.5" />
            Campaign
          </TabsTrigger>
          <TabsTrigger value="simulation" className="gap-1.5">
            <Activity className="size-3.5" />
            Simulation
          </TabsTrigger>
          <TabsTrigger value="report" className="gap-1.5">
            <FileText className="size-3.5" />
            Report
          </TabsTrigger>
        </TabsList>

        <TabsContent value="campaign" className="pt-6">
          {/* Campaign tab content - wired by plan 08-05 */}
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <p className="text-sm text-muted-foreground">
              Campaign overview content renders here.
            </p>
          </div>
        </TabsContent>

        <TabsContent value="simulation" className="pt-6">
          {/* Simulation tab content - wired by plan 08-06 */}
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <p className="text-sm text-muted-foreground">
              Simulation results render here.
            </p>
          </div>
        </TabsContent>

        <TabsContent value="report" className="pt-6">
          <ReportTabContent campaign={campaign} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
