/**
 * Agent grid — compact roster of simulated agents.
 *
 * Each card is a minimal box: monospace ID at top, mono name,
 * a stance dot (teal = pro, coral = anti, gray = neutral), and
 * a small interview action on hover. No gradients, no avatar glow.
 * Empty state is a centered, intentional-looking panel rather than
 * a throwaway one-liner.
 */

import { MessageCircle, Users } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface AgentData {
  id?: string;
  agent_id?: string;
  name?: string;
  role?: string;
  archetype?: string;
  persona?: string;
  sentiment?: number;
  influence_score?: number;
  posts_count?: number;
  platform?: string;
  [key: string]: unknown;
}

interface AgentGridProps {
  agents: AgentData[];
  onInterviewAgent: (agentId: string, agentName: string) => void;
}

function truncate(text: string, max: number): string {
  return text.length > max ? text.slice(0, max - 1) + '…' : text;
}

function stanceColor(value: number | undefined): {
  dot: string;
  label: string;
} {
  if (value == null) return { dot: 'bg-muted-foreground', label: 'unknown' };
  if (value > 0.3)
    return { dot: 'bg-[oklch(0.76_0.12_180)]', label: 'pro' };
  if (value < -0.3)
    return { dot: 'bg-[oklch(0.68_0.20_22)]', label: 'anti' };
  return { dot: 'bg-muted-foreground', label: 'neutral' };
}

export function AgentGrid({ agents, onInterviewAgent }: AgentGridProps) {
  if (!agents || agents.length === 0) {
    return (
      <div className="space-y-3">
        <AgentHeader count={0} />
        <div className="flex flex-col items-center justify-center gap-3 border border-dashed border-border px-6 py-14 text-center">
          <div className="flex size-10 items-center justify-center rounded-sm border border-border bg-surface-1">
            <Users className="size-4 text-muted-foreground" />
          </div>
          <p className="max-w-sm text-[0.88rem] text-foreground/80">
            Agent roster not available
          </p>
          <p className="max-w-sm font-mono text-[0.7rem] leading-relaxed text-muted-foreground">
            MiroFish did not return per-agent data for this simulation —
            only the aggregate metrics above.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <AgentHeader count={agents.length} />
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
        {agents.map((agent, idx) => {
          const id = agent.agent_id ?? agent.id ?? `agent-${idx}`;
          const name = agent.name ?? agent.persona ?? `Agent ${idx + 1}`;
          const role = agent.role ?? agent.archetype ?? agent.platform ?? null;
          const stance = stanceColor(agent.sentiment);

          return (
            <button
              key={id}
              type="button"
              onClick={() => onInterviewAgent(id, name)}
              className={cn(
                'group flex flex-col gap-1.5 border border-border bg-surface-1 px-3 py-2.5 text-left transition-colors',
                'hover:border-primary/40 hover:bg-surface-2',
              )}
            >
              <div className="flex items-center justify-between">
                <span className="font-mono text-[0.6rem] tracking-[0.1em] text-muted-foreground uppercase">
                  {truncate(id, 12)}
                </span>
                <span className={cn('size-1.5 rounded-full', stance.dot)} />
              </div>
              <div className="min-w-0">
                <p className="truncate font-mono text-[0.78rem] font-medium text-foreground/90">
                  {truncate(name, 22)}
                </p>
                {role && (
                  <p className="truncate text-[0.66rem] text-muted-foreground">
                    {truncate(role, 26)}
                  </p>
                )}
              </div>
              <div className="mt-1 flex items-center justify-between">
                <span className="font-mono text-[0.6rem] tracking-[0.08em] text-muted-foreground uppercase">
                  {stance.label}
                </span>
                <span className="flex items-center gap-0.5 font-mono text-[0.6rem] text-muted-foreground/0 transition-colors group-hover:text-primary/90">
                  <MessageCircle className="size-2.5" />
                  interview
                </span>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function AgentHeader({ count }: { count: number }) {
  return (
    <div className="flex items-baseline justify-between border-b border-border pb-2">
      <div className="flex items-baseline gap-3">
        <h3 className="text-[0.95rem] font-medium tracking-[-0.005em] text-foreground">
          Agent roster
        </h3>
        <span className="font-mono text-[0.6rem] tracking-[0.1em] text-mirofish uppercase">
          mirofish
        </span>
      </div>
      <span className="font-mono text-[0.64rem] tabular-nums text-muted-foreground">
        {count.toString().padStart(3, '0')}
      </span>
    </div>
  );
}
