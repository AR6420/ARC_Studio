/**
 * Configuration panel — tight grid layout.
 *
 * Row 1: Agent count + Max iterations sliders side-by-side.
 * Row 2: Collapsible 2-column threshold editor.
 *
 * Everything monospace where it's a number; everything labels in small caps.
 */

import { useState } from 'react';
import { ChevronDown } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Slider } from '@/components/ui/slider';
import { Input } from '@/components/ui/input';

const DEFAULT_THRESHOLDS: Record<string, number> = {
  attention_score: 60,
  virality_potential: 50,
  backlash_risk: 40,
  memory_durability: 55,
  conversion_potential: 50,
  audience_fit: 60,
  polarization_index: 40,
};

const THRESHOLD_LABELS: Record<string, string> = {
  attention_score: 'Attention',
  virality_potential: 'Virality',
  backlash_risk: 'Backlash',
  memory_durability: 'Memory',
  conversion_potential: 'Conversion',
  audience_fit: 'Audience Fit',
  polarization_index: 'Polarization',
};

const INVERTED = new Set(['backlash_risk', 'polarization_index']);

interface ConfigPanelProps {
  agentCount: number;
  onAgentCountChange: (value: number) => void;
  maxIterations: number;
  onMaxIterationsChange: (value: number) => void;
  thresholdEnabled: boolean;
  onThresholdEnabledChange: (enabled: boolean) => void;
  thresholds: Record<string, number>;
  onThresholdsChange: (thresholds: Record<string, number>) => void;
}

function SliderRow({
  label,
  hint,
  value,
  min,
  max,
  step,
  onChange,
}: {
  label: string;
  hint: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (v: number) => void;
}) {
  return (
    <div className="space-y-2">
      <div className="flex items-baseline justify-between">
        <span className="font-mono text-[0.6rem] tracking-[0.16em] text-muted-foreground uppercase">
          {label}
        </span>
        <span className="font-mono text-[0.95rem] font-semibold tabular-nums text-primary">
          {value}
        </span>
      </div>
      <Slider
        value={[value]}
        onValueChange={(val) => {
          const v = Array.isArray(val) ? val[0] : val;
          onChange(v);
        }}
        min={min}
        max={max}
        step={step}
      />
      <div className="flex items-center justify-between font-mono text-[0.58rem] tabular-nums text-muted-foreground/45">
        <span>{min}</span>
        <span>{hint}</span>
        <span>{max}</span>
      </div>
    </div>
  );
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
  const [open, setOpen] = useState(thresholdEnabled);

  function handleToggle() {
    const next = !open;
    setOpen(next);
    onThresholdEnabledChange(next);
    if (next && Object.keys(thresholds).length === 0) {
      onThresholdsChange({ ...DEFAULT_THRESHOLDS });
    }
  }

  function handleChange(key: string, value: string) {
    const num = parseInt(value, 10);
    if (Number.isNaN(num)) return;
    const clamped = Math.max(0, Math.min(100, num));
    onThresholdsChange({ ...thresholds, [key]: clamped });
  }

  return (
    <div className="space-y-5">
      {/* Sliders on a single row */}
      <div className="grid grid-cols-1 gap-7 sm:grid-cols-2">
        <SliderRow
          label="Simulated Agents"
          hint="20 — 200"
          value={agentCount}
          min={20}
          max={200}
          step={10}
          onChange={onAgentCountChange}
        />
        <SliderRow
          label="Max Iterations"
          hint="1 — 10"
          value={maxIterations}
          min={1}
          max={10}
          step={1}
          onChange={onMaxIterationsChange}
        />
      </div>

      {/* Collapsible thresholds */}
      <div className="border-t border-border pt-4">
        <button
          type="button"
          onClick={handleToggle}
          className="flex w-full items-center justify-between text-left"
        >
          <span className="font-mono text-[0.6rem] tracking-[0.16em] text-muted-foreground uppercase">
            Score Thresholds
            <span className="ml-2 normal-case tracking-normal text-muted-foreground/50">
              {open ? 'enabled' : 'optional'}
            </span>
          </span>
          <ChevronDown
            className={cn(
              'size-3.5 text-muted-foreground transition-transform duration-150',
              open && 'rotate-180',
            )}
          />
        </button>

        {open && (
          <div className="mt-3 grid grid-cols-2 gap-x-6 gap-y-2.5">
            {Object.entries(THRESHOLD_LABELS).map(([key, label]) => {
              const isInverted = INVERTED.has(key);
              return (
                <div
                  key={key}
                  className="flex items-center justify-between gap-3"
                >
                  <label
                    htmlFor={`thr-${key}`}
                    className="flex min-w-0 items-center gap-1.5 text-[0.74rem] text-foreground/80"
                  >
                    <span className="truncate">{label}</span>
                    {isInverted && (
                      <span className="font-mono text-[0.55rem] text-muted-foreground/55">
                        ↓
                      </span>
                    )}
                  </label>
                  <Input
                    id={`thr-${key}`}
                    type="number"
                    min={0}
                    max={100}
                    value={thresholds[key] ?? DEFAULT_THRESHOLDS[key]}
                    onChange={(e) => handleChange(key, e.target.value)}
                    className="h-7 w-14 bg-sidebar px-1.5 text-center font-mono text-[0.76rem] tabular-nums"
                  />
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
