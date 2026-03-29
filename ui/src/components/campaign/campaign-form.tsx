/**
 * Campaign creation form -- single scrollable page with visually distinct sections.
 *
 * Per D-04: Not a wizard. Scroll down, click Run.
 * Per D-07: Premium feel. This is the first thing users interact with.
 *
 * Sections:
 *   1. Content -- seed content textarea + prediction question
 *   2. Audience -- demographic preset selector
 *   3. Configuration -- agent count, iterations, optional thresholds
 *   4. Time Estimate -- live duration estimate from API
 *   5. Optional Constraints -- additional constraints textarea
 *   Submit -- Run Campaign button
 */

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { Play, Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useCreateCampaign } from '@/hooks/use-campaigns'
import { Textarea } from '@/components/ui/textarea'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Separator } from '@/components/ui/separator'
import { DemographicSelector } from './demographic-selector'
import { ConfigPanel } from './config-panel'
import { TimeEstimate } from './time-estimate'

const SEED_MIN = 100
const SEED_MAX = 25000
const QUESTION_MIN = 10

export function CampaignForm() {
  const navigate = useNavigate()
  const createMutation = useCreateCampaign()

  // -- Form state --
  const [seedContent, setSeedContent] = useState('')
  const [predictionQuestion, setPredictionQuestion] = useState('')
  const [demographic, setDemographic] = useState('general_consumer_us')
  const [demographicCustom, setDemographicCustom] = useState('')
  const [agentCount, setAgentCount] = useState(40)
  const [maxIterations, setMaxIterations] = useState(4)
  const [thresholdEnabled, setThresholdEnabled] = useState(false)
  const [thresholds, setThresholds] = useState<Record<string, number>>({})
  const [constraints, setConstraints] = useState('')

  // -- Validation --
  const seedLen = seedContent.length
  const questionLen = predictionQuestion.length
  const seedValid = seedLen >= SEED_MIN
  const questionValid = questionLen >= QUESTION_MIN
  const canSubmit = seedValid && questionValid && !createMutation.isPending

  // -- Submission --
  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()

    if (!seedValid) {
      toast.error('Seed content must be at least 100 characters.')
      return
    }
    if (!questionValid) {
      toast.error('Prediction question must be at least 10 characters.')
      return
    }

    createMutation.mutate(
      {
        seed_content: seedContent,
        prediction_question: predictionQuestion,
        demographic,
        demographic_custom: demographic === 'custom' ? demographicCustom : null,
        agent_count: agentCount,
        max_iterations: maxIterations,
        thresholds: thresholdEnabled ? thresholds : null,
        constraints: constraints.trim() || null,
        auto_start: true,
      },
      {
        onSuccess: (data) => {
          toast.success('Campaign launched')
          navigate(`/campaigns/${data.id}`)
        },
        onError: (err) => {
          toast.error(err.message || 'Failed to create campaign')
        },
      }
    )
  }

  return (
    <form onSubmit={handleSubmit} className="mx-auto max-w-3xl space-y-10 pb-16">
      {/* ── Section 1: Content ─────────────────────────────────────── */}
      <section className="space-y-5">
        <SectionHeading number={1} title="Content" />

        <div className="space-y-2">
          <Label htmlFor="seed-content" className="text-sm text-foreground/90">
            Seed Content
          </Label>
          <Textarea
            id="seed-content"
            value={seedContent}
            onChange={(e) => setSeedContent(e.target.value)}
            placeholder="Paste the content you want to optimize -- a product launch announcement, press release, policy draft, PSA, marketing copy, or any text you want to run through neural scoring and social simulation..."
            className={cn(
              'min-h-40 resize-y bg-card/60 text-sm leading-relaxed',
              seedLen > 0 && !seedValid && 'border-score-amber'
            )}
          />
          <div className="flex items-center justify-between">
            <p className="text-xs text-muted-foreground">
              The raw text that will be analyzed and iteratively improved
            </p>
            <CharCount current={seedLen} max={SEED_MAX} min={SEED_MIN} />
          </div>
        </div>

        <div className="space-y-2">
          <Label htmlFor="prediction-question" className="text-sm text-foreground/90">
            Prediction Question
          </Label>
          <Input
            id="prediction-question"
            value={predictionQuestion}
            onChange={(e) => setPredictionQuestion(e.target.value)}
            placeholder="e.g., How will tech professionals react to this product launch?"
            className={cn(
              'bg-card/60',
              questionLen > 0 && !questionValid && 'border-score-amber'
            )}
          />
          <p className="text-xs text-muted-foreground">
            The specific question the simulation will answer about audience response
          </p>
        </div>
      </section>

      <Separator className="opacity-40" />

      {/* ── Section 2: Audience ────────────────────────────────────── */}
      <section className="space-y-5">
        <SectionHeading number={2} title="Audience" />
        <p className="text-xs leading-relaxed text-muted-foreground">
          Select a demographic preset to configure the simulated agent population,
          or define a custom audience profile.
        </p>
        <DemographicSelector
          selected={demographic}
          onSelect={setDemographic}
          customText={demographicCustom}
          onCustomTextChange={setDemographicCustom}
        />
      </section>

      <Separator className="opacity-40" />

      {/* ── Section 3: Configuration ───────────────────────────────── */}
      <section className="space-y-5">
        <SectionHeading number={3} title="Configuration" />
        <p className="text-xs leading-relaxed text-muted-foreground">
          Adjust the simulation parameters. More agents and iterations produce
          richer results but take longer.
        </p>
        <ConfigPanel
          agentCount={agentCount}
          onAgentCountChange={setAgentCount}
          maxIterations={maxIterations}
          onMaxIterationsChange={setMaxIterations}
          thresholdEnabled={thresholdEnabled}
          onThresholdEnabledChange={setThresholdEnabled}
          thresholds={thresholds}
          onThresholdsChange={setThresholds}
        />
      </section>

      <Separator className="opacity-40" />

      {/* ── Section 4: Time Estimate ───────────────────────────────── */}
      <section className="space-y-5">
        <SectionHeading number={4} title="Estimated Duration" />
        <TimeEstimate agentCount={agentCount} maxIterations={maxIterations} />
      </section>

      <Separator className="opacity-40" />

      {/* ── Section 5: Optional Constraints ────────────────────────── */}
      <section className="space-y-5">
        <SectionHeading number={5} title="Constraints" subtitle="optional" />
        <div className="space-y-2">
          <Textarea
            id="constraints"
            value={constraints}
            onChange={(e) => setConstraints(e.target.value)}
            placeholder="e.g., Must maintain professional tone. Do not reference competitors by name. Keep the call-to-action within 2 sentences."
            className="min-h-20 resize-y bg-card/60 text-sm"
          />
          <p className="text-xs text-muted-foreground">
            Additional rules or boundaries the optimizer should respect during variant generation
          </p>
        </div>
      </section>

      {/* ── Submit ─────────────────────────────────────────────────── */}
      <div className="pt-2">
        <Button
          type="submit"
          size="lg"
          disabled={!canSubmit}
          className={cn(
            'h-12 w-full gap-2 text-base font-semibold tracking-wide',
            'bg-primary text-primary-foreground',
            'hover:bg-primary/90 hover:shadow-[0_0_20px_-4px_var(--primary)]',
            'disabled:opacity-40 disabled:shadow-none',
            'transition-all duration-200'
          )}
        >
          {createMutation.isPending ? (
            <>
              <Loader2 className="size-5 animate-spin" />
              Launching...
            </>
          ) : (
            <>
              <Play className="size-5" />
              Run Campaign
            </>
          )}
        </Button>
        {!canSubmit && seedLen === 0 && questionLen === 0 && (
          <p className="mt-2 text-center text-xs text-muted-foreground">
            Fill in your content and prediction question to begin
          </p>
        )}
      </div>
    </form>
  )
}

// ── Sub-components ────────────────────────────────────────────────────────────

function SectionHeading({
  number,
  title,
  subtitle,
}: {
  number: number
  title: string
  subtitle?: string
}) {
  return (
    <div className="flex items-center gap-3">
      <span className="flex size-7 shrink-0 items-center justify-center rounded-md bg-primary/10 text-xs font-bold text-primary tabular-nums">
        {number}
      </span>
      <h2 className="text-base font-semibold text-foreground">{title}</h2>
      {subtitle && (
        <span className="text-xs text-muted-foreground">({subtitle})</span>
      )}
    </div>
  )
}

function CharCount({
  current,
  max,
  min,
}: {
  current: number
  max: number
  min: number
}) {
  const belowMin = current > 0 && current < min
  const nearMax = current > max * 0.9

  return (
    <span
      className={cn(
        'text-xs tabular-nums',
        belowMin
          ? 'text-score-amber'
          : nearMax
            ? 'text-score-red'
            : 'text-muted-foreground'
      )}
    >
      {current.toLocaleString()} / {max.toLocaleString()}
      {belowMin && (
        <span className="ml-1 text-[11px]">
          (min {min})
        </span>
      )}
    </span>
  )
}
