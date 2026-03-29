/**
 * Agent grid displaying simulated agent profiles as clickable cards.
 *
 * Each card represents a MiroFish social agent with whatever metadata is
 * available from the simulation results (agent_stats data can be sparse).
 * Clicking a card triggers the agent interview modal.
 *
 * Design: social-network-style profile grid per D-07.
 */

import { MessageCircle, User } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';

/**
 * Agent data shape is loosely typed because MiroFish agent_stats
 * structure varies and can be sparse (per research Open Question 2).
 */
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

/** Deterministic pastel hue from agent ID for avatar background. */
function agentHue(id: string): number {
  let hash = 0;
  for (let i = 0; i < id.length; i++) {
    hash = ((hash << 5) - hash + id.charCodeAt(i)) | 0;
  }
  return Math.abs(hash) % 360;
}

/** Truncate text gracefully. */
function truncate(text: string, max: number): string {
  return text.length > max ? text.slice(0, max - 1) + '\u2026' : text;
}

/** Sentiment value to color class. */
function sentimentColor(value: number | undefined): string {
  if (value == null) return 'text-muted-foreground';
  if (value > 0.3) return 'text-emerald-400';
  if (value < -0.3) return 'text-red-400';
  return 'text-amber-400';
}

/** Sentiment value to label. */
function sentimentLabel(value: number | undefined): string {
  if (value == null) return 'Unknown';
  if (value > 0.3) return 'Positive';
  if (value < -0.3) return 'Negative';
  return 'Neutral';
}

export function AgentGrid({
  agents,
  onInterviewAgent,
}: AgentGridProps) {
  if (!agents || agents.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-muted-foreground/25 py-16">
        <Users className="size-8 text-muted-foreground/40" />
        <p className="text-sm text-muted-foreground">
          Agent data not available for this simulation.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between px-1">
        <h3 className="text-sm font-medium text-foreground">
          Simulated Agents
        </h3>
        <span className="text-xs tabular-nums text-muted-foreground">
          {agents.length} agents
        </span>
      </div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
        {agents.map((agent, idx) => {
          const id = agent.agent_id ?? agent.id ?? `agent-${idx}`;
          const name = agent.name ?? agent.persona ?? `Agent ${idx + 1}`;
          const role = agent.role ?? agent.archetype ?? agent.platform ?? null;
          const hue = agentHue(id);

          return (
            <Card
              key={id}
              size="sm"
              className="group relative cursor-pointer transition-all hover:ring-primary/30 hover:shadow-lg hover:shadow-primary/5"
              onClick={() => onInterviewAgent(id, name)}
            >
              <CardContent className="flex flex-col items-center gap-2.5 pt-2 text-center">
                {/* Avatar circle with deterministic color */}
                <div
                  className="flex size-10 items-center justify-center rounded-full ring-2 ring-foreground/10"
                  style={{
                    background: `oklch(0.35 0.06 ${hue})`,
                  }}
                >
                  <User
                    className="size-5"
                    style={{ color: `oklch(0.75 0.1 ${hue})` }}
                  />
                </div>

                {/* Name and role */}
                <div className="w-full min-w-0">
                  <p className="truncate text-sm font-semibold text-foreground">
                    {truncate(name, 24)}
                  </p>
                  {role && (
                    <p className="truncate text-xs text-muted-foreground">
                      {truncate(role, 30)}
                    </p>
                  )}
                </div>

                {/* Sentiment indicator */}
                {agent.sentiment != null && (
                  <div className="flex items-center gap-1.5">
                    <span
                      className={`inline-block size-1.5 rounded-full ${
                        agent.sentiment > 0.3
                          ? 'bg-emerald-400'
                          : agent.sentiment < -0.3
                            ? 'bg-red-400'
                            : 'bg-amber-400'
                      }`}
                    />
                    <span
                      className={`text-[11px] font-medium ${sentimentColor(agent.sentiment)}`}
                    >
                      {sentimentLabel(agent.sentiment)}
                    </span>
                  </div>
                )}

                {/* Interview CTA */}
                <Button
                  variant="ghost"
                  size="sm"
                  className="mt-auto h-7 w-full gap-1.5 text-xs text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100"
                  onClick={(e) => {
                    e.stopPropagation();
                    onInterviewAgent(id, name);
                  }}
                >
                  <MessageCircle className="size-3" />
                  Interview
                </Button>
              </CardContent>

              {/* Hover glow effect */}
              <div
                className="pointer-events-none absolute inset-0 rounded-xl opacity-0 transition-opacity group-hover:opacity-100"
                style={{
                  background: `radial-gradient(circle at 50% 0%, oklch(0.5 0.08 ${hue} / 0.12), transparent 70%)`,
                }}
              />
            </Card>
          );
        })}
      </div>
    </div>
  );
}

/** Used by the empty state fallback */
function Users({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <path d="M22 21v-2a4 4 0 0 0-3-3.87" />
      <path d="M16 3.13a4 4 0 0 1 0 7.75" />
    </svg>
  );
}
