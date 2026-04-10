/**
 * Demographic selector — compact pill row with an inline custom option.
 *
 * Pills wrap to 2 rows on narrow screens. Selected pill gets the amber
 * tint; unselected is a flat outline. Selecting "Custom" reveals a
 * monospace textarea directly below the pill row.
 */

import {
  Monitor,
  Building2,
  Users,
  Landmark,
  HeartPulse,
  Smartphone,
  Pen,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Textarea } from '@/components/ui/textarea';

interface DemographicPreset {
  key: string;
  label: string;
  hint: string;
  icon: React.ComponentType<{ className?: string }>;
}

const PRESETS: DemographicPreset[] = [
  {
    key: 'tech_professionals',
    label: 'Tech Pros',
    hint: 'Developers, engineering leads, CTOs',
    icon: Monitor,
  },
  {
    key: 'enterprise_decision_makers',
    label: 'Enterprise',
    hint: 'C-suite, VPs, directors at mid-to-large orgs',
    icon: Building2,
  },
  {
    key: 'general_consumer_us',
    label: 'General Consumer',
    hint: 'Broad US adults, 25–45',
    icon: Users,
  },
  {
    key: 'policy_aware_public',
    label: 'Policy-Aware',
    hint: 'Civically engaged adults, partisan-sensitive',
    icon: Landmark,
  },
  {
    key: 'healthcare_professionals',
    label: 'Healthcare',
    hint: 'Physicians, nurses, public health',
    icon: HeartPulse,
  },
  {
    key: 'gen_z_digital_natives',
    label: 'Gen Z · 18–27',
    hint: 'Authenticity-sensitive, peer-driven',
    icon: Smartphone,
  },
];

interface DemographicSelectorProps {
  selected: string;
  onSelect: (key: string) => void;
  customText: string;
  onCustomTextChange: (text: string) => void;
}

export function DemographicSelector({
  selected,
  onSelect,
  customText,
  onCustomTextChange,
}: DemographicSelectorProps) {
  const isCustom = selected === 'custom';
  const activePreset = PRESETS.find((p) => p.key === selected);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-1.5">
        {PRESETS.map((preset) => {
          const Icon = preset.icon;
          const isSelected = !isCustom && selected === preset.key;
          return (
            <button
              key={preset.key}
              type="button"
              onClick={() => onSelect(preset.key)}
              className={cn(
                'inline-flex items-center gap-1.5 rounded-sm border px-2.5 py-1.5 text-[0.78rem] tracking-[-0.002em] transition-colors duration-150',
                isSelected
                  ? 'border-primary/60 bg-primary/[0.10] text-foreground'
                  : 'border-border bg-transparent text-muted-foreground hover:border-foreground/25 hover:text-foreground',
              )}
            >
              <Icon className="size-3.5 shrink-0" />
              {preset.label}
            </button>
          );
        })}
        <button
          type="button"
          onClick={() => onSelect('custom')}
          className={cn(
            'inline-flex items-center gap-1.5 rounded-sm border border-dashed px-2.5 py-1.5 text-[0.78rem] tracking-[-0.002em] transition-colors duration-150',
            isCustom
              ? 'border-primary/60 bg-primary/[0.10] text-foreground'
              : 'border-border text-muted-foreground hover:border-foreground/25 hover:text-foreground',
          )}
        >
          <Pen className="size-3.5 shrink-0" />
          Custom
        </button>
      </div>

      {/* Inline description of the currently selected preset — replaces tooltips */}
      {activePreset && (
        <p className="font-mono text-[0.66rem] text-muted-foreground/55">
          › {activePreset.hint}
        </p>
      )}

      {isCustom && (
        <Textarea
          value={customText}
          onChange={(e) => onCustomTextChange(e.target.value)}
          placeholder="Describe the target audience: age band, profession, media habits, values, risk profile…"
          className="min-h-[5.5rem] bg-sidebar font-mono text-[0.76rem] leading-relaxed"
        />
      )}
    </div>
  );
}
