/**
 * Campaign creation form — single scrollable page, densely laid out.
 *
 * Section headers are small-caps monospace labels, not numbered badges.
 * Seed content is a monospace editor panel with an inset background.
 * Time estimate sits inline next to the Run button; no separate section.
 *
 * Phase 2 A.1/A.2 — Optional audio OR video upload sits between seed content
 * and the prediction question. When media is selected, the seed textarea
 * becomes optional (the media IS the content); the prediction question stays
 * required. Media type is detected from extension by the upload component.
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { Play, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useCreateCampaign } from '@/hooks/use-campaigns';
import { uploadMedia } from '@/api/client';
import { Textarea } from '@/components/ui/textarea';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { DemographicSelector } from './demographic-selector';
import { ConfigPanel } from './config-panel';
import { TimeEstimate } from './time-estimate';
import { MediaUpload, type MediaFileInfo } from './media-upload';

const SEED_MIN = 100;
const SEED_MAX = 25000;
const QUESTION_MIN = 10;

export function CampaignForm() {
  const navigate = useNavigate();
  const createMutation = useCreateCampaign();

  const [seedContent, setSeedContent] = useState('');
  const [predictionQuestion, setPredictionQuestion] = useState('');
  const [demographic, setDemographic] = useState('general_consumer_us');
  const [demographicCustom, setDemographicCustom] = useState('');
  const [agentCount, setAgentCount] = useState(40);
  const [maxIterations, setMaxIterations] = useState(4);
  const [variantCount, setVariantCount] = useState(2);
  const [thresholdEnabled, setThresholdEnabled] = useState(false);
  const [thresholds, setThresholds] = useState<Record<string, number>>({});
  const [constraints, setConstraints] = useState('');

  // Phase 2 A.1/A.2 — media state (audio or video)
  const [mediaFile, setMediaFile] = useState<MediaFileInfo | null>(null);
  const [uploadingMedia, setUploadingMedia] = useState(false);

  const hasMedia = mediaFile !== null;
  const seedLen = seedContent.length;
  const questionLen = predictionQuestion.length;
  // When media is provided, the textarea is optional — the media IS the content.
  // Text-only mode keeps the original 100-char minimum unchanged.
  const seedValid = hasMedia ? true : seedLen >= SEED_MIN;
  const questionValid = questionLen >= QUESTION_MIN;
  const canSubmit =
    seedValid &&
    questionValid &&
    !createMutation.isPending &&
    !uploadingMedia;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!seedValid) {
      toast.error(
        hasMedia
          ? 'Unexpected seed content state.'
          : 'Seed content must be at least 100 characters.',
      );
      return;
    }
    if (!questionValid) {
      toast.error('Prediction question must be at least 10 characters.');
      return;
    }

    // Phase 2 A.1/A.2 — if media is attached, upload it first to obtain media_path.
    let mediaPath: string | null = null;
    let mediaType: 'text' | 'audio' | 'video' = 'text';
    if (hasMedia && mediaFile) {
      try {
        setUploadingMedia(true);
        const res = await uploadMedia(mediaFile.file);
        mediaPath = res.media_path;
        // Trust the server's classification (matches client-side detection
        // but the server is the source of truth, esp. after downscale).
        mediaType = res.media_type;
      } catch (err) {
        setUploadingMedia(false);
        const msg = err instanceof Error ? err.message : 'Media upload failed';
        toast.error(`${mediaFile.mediaType === 'video' ? 'Video' : 'Audio'} upload failed: ${msg}`);
        return;
      }
      setUploadingMedia(false);
    }

    createMutation.mutate(
      {
        // When media-only, still send the seed (possibly empty) so the
        // backend schema has the field; the media is the real content.
        seed_content: hasMedia && seedContent.length === 0 ? '' : seedContent,
        prediction_question: predictionQuestion,
        demographic,
        demographic_custom: demographic === 'custom' ? demographicCustom : null,
        agent_count: agentCount,
        max_iterations: maxIterations,
        variant_count: variantCount,
        thresholds: thresholdEnabled ? thresholds : null,
        constraints: constraints.trim() || null,
        auto_start: true,
        media_type: mediaType,
        media_path: mediaPath,
      },
      {
        onSuccess: (data) => {
          toast.success('Campaign launched');
          navigate(`/campaigns/${data.id}`);
        },
        onError: (err) => {
          toast.error(err.message || 'Failed to create campaign');
        },
      },
    );
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="mx-auto flex max-w-[780px] flex-col gap-10 pb-20"
    >
      {/* ── Content ─────────────────────────────────────────────── */}
      <FieldGroup label="Content" hint="The raw text the pipeline will analyse and iterate on">
        <div className="space-y-2.5">
          <div className="relative">
            <Textarea
              id="seed-content"
              value={seedContent}
              onChange={(e) => setSeedContent(e.target.value)}
              placeholder={
                hasMedia
                  ? `Optional — ${mediaFile?.mediaType ?? 'media'} is the primary content. Add text context if useful.`
                  : 'Paste the content you want to optimise — a product announcement, press release, policy draft, marketing copy…'
              }
              className={cn(
                'min-h-[13rem] resize-y bg-sidebar font-mono text-[0.78rem] leading-[1.55] tracking-[-0.003em]',
                seedLen > 0 && !seedValid && 'border-heat-mid/60',
              )}
            />
            {/* Char count overlay, bottom right */}
            <CharCount
              current={seedLen}
              max={SEED_MAX}
              min={SEED_MIN}
              optional={hasMedia}
            />
          </div>
          <p className="font-mono text-[0.6rem] text-muted-foreground">
            Variants are limited to 150 words each to match TRIBE v2 inference speed on laptop hardware.
          </p>
        </div>

        {/* Phase 2 A.1/A.2 — audio or video upload */}
        <div className="space-y-2.5">
          <FieldLabel>Audio or Video (optional)</FieldLabel>
          <MediaUpload
            value={mediaFile}
            onChange={setMediaFile}
            disabled={createMutation.isPending || uploadingMedia}
          />
        </div>

        <div className="space-y-2.5">
          <FieldLabel htmlFor="prediction-question">Prediction Question</FieldLabel>
          <Input
            id="prediction-question"
            value={predictionQuestion}
            onChange={(e) => setPredictionQuestion(e.target.value)}
            placeholder="e.g. How will tech professionals react to this launch?"
            className={cn(
              'h-9 bg-sidebar text-[0.82rem]',
              questionLen > 0 && !questionValid && 'border-heat-mid/60',
            )}
          />
        </div>
      </FieldGroup>

      {/* ── Audience ────────────────────────────────────────────── */}
      <FieldGroup label="Audience" hint="Select a preset demographic or define your own profile">
        <DemographicSelector
          selected={demographic}
          onSelect={setDemographic}
          customText={demographicCustom}
          onCustomTextChange={setDemographicCustom}
        />
      </FieldGroup>

      {/* ── Configuration ───────────────────────────────────────── */}
      <FieldGroup label="Configuration" hint="Simulation parameters — more agents and iterations cost more time">
        <ConfigPanel
          agentCount={agentCount}
          onAgentCountChange={setAgentCount}
          maxIterations={maxIterations}
          onMaxIterationsChange={setMaxIterations}
          variantCount={variantCount}
          onVariantCountChange={setVariantCount}
          thresholdEnabled={thresholdEnabled}
          onThresholdEnabledChange={setThresholdEnabled}
          thresholds={thresholds}
          onThresholdsChange={setThresholds}
        />
      </FieldGroup>

      {/* ── Constraints (optional) ──────────────────────────────── */}
      <FieldGroup
        label="Constraints"
        hint="Optional rules the optimiser must respect during variant generation"
      >
        <Textarea
          id="constraints"
          value={constraints}
          onChange={(e) => setConstraints(e.target.value)}
          placeholder="e.g. Maintain professional tone. No competitor names. CTA ≤ 2 sentences."
          className="min-h-[4.5rem] resize-y bg-sidebar font-mono text-[0.76rem] leading-[1.55]"
        />
      </FieldGroup>

      {/* ── Footer — inline estimate + Run ─────────────────────── */}
      <div className="flex items-center justify-between gap-6 border-t border-border pt-5">
        <TimeEstimate agentCount={agentCount} maxIterations={maxIterations} />
        <Button
          type="submit"
          disabled={!canSubmit}
          className="gap-1.5 px-5"
        >
          {uploadingMedia ? (
            <>
              <Loader2 className="size-3.5 animate-spin" />
              Uploading {mediaFile?.mediaType ?? 'media'}…
            </>
          ) : createMutation.isPending ? (
            <>
              <Loader2 className="size-3.5 animate-spin" />
              Launching…
            </>
          ) : (
            <>
              <Play className="size-3.5" />
              Run Campaign
            </>
          )}
        </Button>
      </div>
    </form>
  );
}

// ── Sub-components ────────────────────────────────────────────────────────

function FieldGroup({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="flex flex-col gap-4">
      <div className="flex items-baseline gap-3 border-b border-border pb-2">
        <h2 className="text-[1rem] font-medium tracking-[-0.005em] text-foreground">
          {label}
        </h2>
        {hint && (
          <span className="text-[0.72rem] text-muted-foreground">
            {hint}
          </span>
        )}
      </div>
      {children}
    </section>
  );
}

function FieldLabel({
  children,
  htmlFor,
}: {
  children: React.ReactNode;
  htmlFor?: string;
}) {
  return (
    <label
      htmlFor={htmlFor}
      className="block font-mono text-[0.62rem] tracking-[0.14em] text-muted-foreground uppercase"
    >
      {children}
    </label>
  );
}

function CharCount({
  current,
  max,
  min,
  optional = false,
}: {
  current: number;
  max: number;
  min: number;
  optional?: boolean;
}) {
  // When audio provides the primary content, don't flag the textarea as
  // below-min — it's explicitly optional in that mode.
  const belowMin = !optional && current > 0 && current < min;
  const nearMax = current > max * 0.9;

  return (
    <div className="pointer-events-none absolute right-2.5 bottom-2 flex items-center gap-1.5 font-mono text-[0.62rem] tabular-nums">
      <span
        className={cn(
          belowMin
            ? 'text-heat-mid'
            : nearMax
              ? 'text-heat-hot'
              : 'text-muted-foreground',
        )}
      >
        {current.toLocaleString()} / {max.toLocaleString()}
      </span>
      {belowMin && (
        <span className="text-muted-foreground">min {min}</span>
      )}
      {optional && current === 0 && (
        <span className="text-mirofish/70">optional</span>
      )}
    </div>
  );
}
