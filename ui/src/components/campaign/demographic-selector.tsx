/**
 * Demographic preset selector with 6 cards + custom option.
 *
 * Renders a grid of selectable demographic profile cards with icons,
 * plus a "Custom" option that reveals a textarea for freeform input.
 *
 * Preset data is hardcoded to match orchestrator/prompts/demographic_profiles.py
 * (6 presets). The API call is available via getDemographics but we inline the
 * data here to avoid a network dependency on the form being usable.
 */

import { useState } from 'react'
import {
  Monitor,
  Building2,
  Users,
  Landmark,
  HeartPulse,
  Smartphone,
  Pen,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'

interface DemographicPreset {
  key: string
  label: string
  description: string
  icon: React.ComponentType<{ className?: string }>
}

const PRESETS: DemographicPreset[] = [
  {
    key: 'tech_professionals',
    label: 'Tech Professionals',
    description:
      'Software developers, engineering leads, CTOs, and IT decision-makers. Skeptical of marketing language, values technical substance.',
    icon: Monitor,
  },
  {
    key: 'enterprise_decision_makers',
    label: 'Enterprise Decision-Makers',
    description:
      'C-suite executives, VPs, and directors at mid-to-large enterprises. Time-constrained, risk-averse, need ROI justification.',
    icon: Building2,
  },
  {
    key: 'general_consumer_us',
    label: 'General Consumer (US, 25-45)',
    description:
      'Broad US adult audience. Mixed media literacy. Share content that feels personally relevant or emotionally resonant.',
    icon: Users,
  },
  {
    key: 'policy_aware_public',
    label: 'Policy-Aware Public',
    description:
      'Civically engaged adults who follow policy and political developments. Sensitive to partisan signals and fairness framing.',
    icon: Landmark,
  },
  {
    key: 'healthcare_professionals',
    label: 'Healthcare Professionals',
    description:
      'Practicing physicians, nurses, pharmacists, and public health officials. Evidence-driven, high bar for factual accuracy.',
    icon: HeartPulse,
  },
  {
    key: 'gen_z_digital_natives',
    label: 'Gen Z Digital Natives (18-27)',
    description:
      'College students and early-career adults. Authenticity-sensitive, humor-driven. Peer social proof is dominant influence.',
    icon: Smartphone,
  },
]

interface DemographicSelectorProps {
  selected: string
  onSelect: (key: string) => void
  customText: string
  onCustomTextChange: (text: string) => void
}

export function DemographicSelector({
  selected,
  onSelect,
  customText,
  onCustomTextChange,
}: DemographicSelectorProps) {
  const [isCustom, setIsCustom] = useState(selected === 'custom')

  function handlePresetClick(key: string) {
    setIsCustom(false)
    onSelect(key)
  }

  function handleCustomClick() {
    setIsCustom(true)
    onSelect('custom')
  }

  return (
    <div className="space-y-4">
      {/* Preset grid */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {PRESETS.map((preset) => {
          const Icon = preset.icon
          const isSelected = !isCustom && selected === preset.key

          return (
            <button
              key={preset.key}
              type="button"
              onClick={() => handlePresetClick(preset.key)}
              className={cn(
                'group relative flex flex-col items-start gap-3 rounded-xl border p-4 text-left transition-all duration-150',
                'hover:border-primary/40 hover:bg-card/80',
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                isSelected
                  ? 'border-primary bg-primary/[0.06] ring-1 ring-primary/30'
                  : 'border-border/60 bg-card/40'
              )}
            >
              {/* Selection indicator dot */}
              <div
                className={cn(
                  'absolute top-3 right-3 size-2.5 rounded-full transition-all',
                  isSelected
                    ? 'bg-primary shadow-[0_0_6px_var(--primary)]'
                    : 'bg-muted-foreground/20'
                )}
              />

              <div
                className={cn(
                  'flex size-9 items-center justify-center rounded-lg transition-colors',
                  isSelected
                    ? 'bg-primary/15 text-primary'
                    : 'bg-muted text-muted-foreground group-hover:text-foreground'
                )}
              >
                <Icon className="size-[18px]" />
              </div>

              <div className="space-y-1">
                <div
                  className={cn(
                    'text-sm font-medium leading-tight',
                    isSelected ? 'text-foreground' : 'text-foreground/80'
                  )}
                >
                  {preset.label}
                </div>
                <div className="line-clamp-2 text-xs leading-relaxed text-muted-foreground">
                  {preset.description}
                </div>
              </div>
            </button>
          )
        })}
      </div>

      {/* Custom option */}
      <div className="space-y-3">
        <button
          type="button"
          onClick={handleCustomClick}
          className={cn(
            'flex w-full items-center gap-3 rounded-xl border p-4 text-left transition-all duration-150',
            'hover:border-primary/40 hover:bg-card/80',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
            isCustom
              ? 'border-primary bg-primary/[0.06] ring-1 ring-primary/30'
              : 'border-border/60 bg-card/40'
          )}
        >
          <div
            className={cn(
              'flex size-9 shrink-0 items-center justify-center rounded-lg transition-colors',
              isCustom
                ? 'bg-primary/15 text-primary'
                : 'bg-muted text-muted-foreground'
            )}
          >
            <Pen className="size-[18px]" />
          </div>
          <div>
            <div className="text-sm font-medium">Custom Demographic</div>
            <div className="text-xs text-muted-foreground">
              Define your own audience profile for the simulation
            </div>
          </div>
          <div
            className={cn(
              'ml-auto size-2.5 shrink-0 rounded-full transition-all',
              isCustom
                ? 'bg-primary shadow-[0_0_6px_var(--primary)]'
                : 'bg-muted-foreground/20'
            )}
          />
        </button>

        {isCustom && (
          <div className="space-y-2 pl-1">
            <Label htmlFor="custom-demographic" className="text-xs text-muted-foreground">
              Describe your target audience in detail
            </Label>
            <Textarea
              id="custom-demographic"
              value={customText}
              onChange={(e) => onCustomTextChange(e.target.value)}
              placeholder="e.g., Small business owners in the Midwest, ages 35-55, who are evaluating SaaS tools for the first time..."
              className="min-h-24 resize-y bg-card/60 text-sm"
            />
          </div>
        )}
      </div>
    </div>
  )
}
