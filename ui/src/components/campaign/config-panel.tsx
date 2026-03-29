/**
 * Campaign configuration panel with sliders and optional thresholds.
 *
 * - Agent Count slider: 20-200, step 10, default 40
 * - Max Iterations slider: 1-10, step 1, default 4
 * - Optional thresholds section (collapsed by default):
 *   7 composite score dimensions with number inputs, 0-100 range
 */

import { useState } from 'react'
import { ChevronDown, SlidersHorizontal } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Slider } from '@/components/ui/slider'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'

/** Default threshold values per composite score dimension. */
const DEFAULT_THRESHOLDS: Record<string, number> = {
  attention_score: 60,
  virality_potential: 50,
  backlash_risk: 40,
  memory_durability: 55,
  conversion_potential: 50,
  audience_fit: 60,
  polarization_index: 40,
}

/** Human-readable labels for each threshold metric. */
const THRESHOLD_LABELS: Record<string, string> = {
  attention_score: 'Attention Score',
  virality_potential: 'Virality Potential',
  backlash_risk: 'Backlash Risk',
  memory_durability: 'Memory Durability',
  conversion_potential: 'Conversion Potential',
  audience_fit: 'Audience Fit',
  polarization_index: 'Polarization Index',
}

/** Metrics where LOWER is better (inverted scoring). */
const INVERTED_METRICS = new Set(['backlash_risk', 'polarization_index'])

interface ConfigPanelProps {
  agentCount: number
  onAgentCountChange: (value: number) => void
  maxIterations: number
  onMaxIterationsChange: (value: number) => void
  thresholdEnabled: boolean
  onThresholdEnabledChange: (enabled: boolean) => void
  thresholds: Record<string, number>
  onThresholdsChange: (thresholds: Record<string, number>) => void
}

export function ConfigPanel({
  agentCount,
  onAgentCountChange,
  maxIterations,
  onMaxIterationsChange,
  thresholdEnabled,
  onThresholdEnabledChange,
  thresholds,
  onThresholdsChange,
}: ConfigPanelProps) {
  const [thresholdsOpen, setThresholdsOpen] = useState(thresholdEnabled)

  function handleToggleThresholds() {
    const next = !thresholdsOpen
    setThresholdsOpen(next)
    onThresholdEnabledChange(next)
    if (next && Object.keys(thresholds).length === 0) {
      onThresholdsChange({ ...DEFAULT_THRESHOLDS })
    }
  }

  function handleThresholdChange(key: string, value: string) {
    const num = parseInt(value, 10)
    if (Number.isNaN(num)) return
    const clamped = Math.max(0, Math.min(100, num))
    onThresholdsChange({ ...thresholds, [key]: clamped })
  }

  return (
    <div className="space-y-6">
      {/* Agent Count Slider */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <Label className="text-sm text-foreground/90">Simulated Agents</Label>
          <span className="tabular-nums text-sm font-semibold text-primary">
            {agentCount}
          </span>
        </div>
        <Slider
          value={[agentCount]}
          onValueChange={(val) => {
            const v = Array.isArray(val) ? val[0] : val
            onAgentCountChange(v)
          }}
          min={20}
          max={200}
          step={10}
        />
        <div className="flex justify-between text-[11px] text-muted-foreground">
          <span>20 agents</span>
          <span>200 agents</span>
        </div>
      </div>

      {/* Max Iterations Slider */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <Label className="text-sm text-foreground/90">Max Iterations</Label>
          <span className="tabular-nums text-sm font-semibold text-primary">
            {maxIterations}
          </span>
        </div>
        <Slider
          value={[maxIterations]}
          onValueChange={(val) => {
            const v = Array.isArray(val) ? val[0] : val
            onMaxIterationsChange(v)
          }}
          min={1}
          max={10}
          step={1}
        />
        <div className="flex justify-between text-[11px] text-muted-foreground">
          <span>1 iteration</span>
          <span>10 iterations</span>
        </div>
      </div>

      {/* Optional Thresholds */}
      <div className="rounded-xl border border-border/60 bg-card/30">
        <button
          type="button"
          onClick={handleToggleThresholds}
          className={cn(
            'flex w-full items-center justify-between px-4 py-3 text-sm transition-colors',
            'hover:bg-muted/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
            'rounded-xl',
            thresholdsOpen && 'rounded-b-none border-b border-border/40'
          )}
        >
          <div className="flex items-center gap-2">
            <SlidersHorizontal className="size-4 text-muted-foreground" />
            <span className="font-medium text-foreground/90">Score Thresholds</span>
            <span className="text-xs text-muted-foreground">(optional)</span>
          </div>
          <ChevronDown
            className={cn(
              'size-4 text-muted-foreground transition-transform duration-200',
              thresholdsOpen && 'rotate-180'
            )}
          />
        </button>

        {thresholdsOpen && (
          <div className="space-y-3 px-4 py-4">
            <p className="text-xs leading-relaxed text-muted-foreground">
              Set minimum acceptable scores for each dimension. The optimizer will continue
              iterating until these thresholds are met or max iterations are reached.
            </p>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {Object.entries(THRESHOLD_LABELS).map(([key, label]) => {
                const isInverted = INVERTED_METRICS.has(key)
                return (
                  <div key={key} className="flex items-center gap-3">
                    <div className="min-w-0 flex-1">
                      <Label
                        htmlFor={`threshold-${key}`}
                        className="text-xs text-muted-foreground"
                      >
                        {label}
                        {isInverted && (
                          <span className="ml-1 text-[10px] text-score-amber">(lower is better)</span>
                        )}
                      </Label>
                    </div>
                    <Input
                      id={`threshold-${key}`}
                      type="number"
                      min={0}
                      max={100}
                      value={thresholds[key] ?? DEFAULT_THRESHOLDS[key]}
                      onChange={(e) => handleThresholdChange(key, e.target.value)}
                      className="h-8 w-16 bg-card/60 text-center text-sm tabular-nums"
                    />
                  </div>
                )
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
