/**
 * Phase 5 session 4 — embed MiroFish's live force-directed graph view
 * inside ARC_Studio's campaign-detail page.
 *
 * MiroFish ships its own Vue UI on port 3000 with a route at
 * /simulation/:simulationId/start that polls the running OASIS sim and
 * renders agents + ontology edges as they materialise. Iframe-embedding
 * it gives us a demo-ready live visualisation without rebuilding it in
 * React. The orchestrator emits a `mirofish_simulation_started` SSE
 * event with the simulation_id as soon as MiroFish creates the sim
 * (post step-3, well before step-4 prepare loops); the UI captures
 * that ID and renders this panel.
 *
 * Source URL is configurable via `VITE_MIROFISH_BASE_URL` so a dev
 * with no local MiroFish stack can point it at the public demo
 * (https://mirofish-demo.pages.dev) and iterate on this chrome
 * without bringing up docker.
 */

import { useEffect, useState } from 'react';
import { ExternalLink, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';

// MiroFish dev/cloud port. Override at build time with
// VITE_MIROFISH_BASE_URL (e.g. http://localhost:3000 or
// https://mirofish-demo.pages.dev for screenshot-only dev).
const DEFAULT_MIROFISH_BASE = 'http://localhost:3000';

function resolveMirofishBase(): string {
  const fromEnv = (import.meta.env as Record<string, string | undefined>)
    .VITE_MIROFISH_BASE_URL;
  return (fromEnv?.trim() || DEFAULT_MIROFISH_BASE).replace(/\/+$/, '');
}

export interface SimulationGraphPanelProps {
  simulationId: string | null;
  /** When true, renders a "Simulation complete" badge instead of the live label. */
  complete?: boolean;
  /** Pixel height of the iframe. Defaults to 600. */
  height?: number;
  /** Override the base URL for testing / demo dev. */
  mirofishBaseUrl?: string;
  className?: string;
}

export function SimulationGraphPanel({
  simulationId,
  complete = false,
  height = 600,
  mirofishBaseUrl,
  className,
}: SimulationGraphPanelProps) {
  const baseUrl = (mirofishBaseUrl ?? resolveMirofishBase()).replace(/\/+$/, '');
  const iframeUrl = simulationId
    ? `${baseUrl}/simulation/${encodeURIComponent(simulationId)}/start`
    : null;

  // Track iframe load + error states so we can render a skeleton or a
  // friendly fallback rather than a blank rectangle.
  const [loadState, setLoadState] = useState<'loading' | 'ready' | 'error'>(
    'loading',
  );

  // Reset state whenever the iframe URL changes — a new simulation_id
  // means a new sim, so we want the loader back until that one paints.
  useEffect(() => {
    setLoadState(simulationId ? 'loading' : 'ready');
  }, [simulationId]);

  if (!simulationId || !iframeUrl) {
    return (
      <div
        className={cn(
          'flex flex-col gap-2 border border-border bg-card/40 p-3',
          className,
        )}
      >
        <PanelHeader complete={false} sourceUrl={null} />
        <div
          className="flex items-center justify-center border border-border/40 bg-background/60"
          style={{ height: `${height}px` }}
        >
          <p className="font-mono text-[0.72rem] text-muted-foreground/55">
            › waiting for MiroFish to register the simulation…
          </p>
        </div>
      </div>
    );
  }

  return (
    <div
      className={cn(
        'flex flex-col gap-2 border border-border bg-card/40 p-3',
        className,
      )}
    >
      <PanelHeader complete={complete} sourceUrl={iframeUrl} />
      <div
        className="relative overflow-hidden border border-border/40 bg-background/60"
        style={{ height: `${height}px` }}
      >
        {loadState === 'loading' && (
          <div className="absolute inset-0 z-10 flex items-center justify-center bg-card/80">
            <span className="flex items-center gap-2 font-mono text-[0.72rem] text-muted-foreground">
              <Loader2 className="size-3.5 animate-spin" />
              loading MiroFish view…
            </span>
          </div>
        )}
        {loadState === 'error' && (
          <div className="absolute inset-0 z-10 flex flex-col items-center justify-center gap-2 bg-card/80 px-6 text-center">
            <p className="text-[0.82rem] text-foreground/85">
              MiroFish UI unreachable.
            </p>
            <p className="max-w-md font-mono text-[0.68rem] leading-relaxed text-muted-foreground">
              Bring it up with{' '}
              <code className="bg-sidebar px-1 py-0.5">
                docker compose up -d mirofish
              </code>{' '}
              or set <code className="bg-sidebar px-1 py-0.5">
                VITE_MIROFISH_BASE_URL
              </code>{' '}
              for a remote target.
            </p>
          </div>
        )}
        <iframe
          src={iframeUrl}
          title="MiroFish live audience simulation"
          className="h-full w-full border-0"
          onLoad={() => setLoadState('ready')}
          onError={() => setLoadState('error')}
        />
      </div>
    </div>
  );
}

function PanelHeader({
  complete,
  sourceUrl,
}: {
  complete: boolean;
  sourceUrl: string | null;
}) {
  return (
    <div className="flex items-baseline justify-between gap-3 border-b border-border/50 pb-2">
      <div className="flex items-baseline gap-3">
        <h3 className="text-[0.95rem] font-medium tracking-tight text-foreground">
          Live audience simulation
        </h3>
        <span
          className={cn(
            'flex items-center gap-1.5 font-mono text-[0.6rem] uppercase tracking-[0.1em]',
            complete ? 'text-muted-foreground' : 'text-primary',
          )}
        >
          {!complete && (
            <span className="inline-block size-1.5 rounded-full bg-primary shimmer" />
          )}
          {complete ? 'simulation complete' : 'live'}
        </span>
      </div>
      <div className="flex items-baseline gap-3">
        <span className="font-mono text-[0.6rem] tracking-[0.1em] text-muted-foreground/55 uppercase">
          powered by MiroFish
        </span>
        {sourceUrl && (
          <a
            href={sourceUrl}
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-1 font-mono text-[0.6rem] tracking-[0.1em] text-muted-foreground uppercase hover:text-foreground"
          >
            open
            <ExternalLink className="size-2.5" />
          </a>
        )}
      </div>
    </div>
  );
}
