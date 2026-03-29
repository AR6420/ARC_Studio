# Phase 8: UI Dashboard - Research

**Researched:** 2026-03-29
**Domain:** React + Vite + TypeScript dashboard (shadcn/ui, Tailwind CSS, Recharts, SSE)
**Confidence:** HIGH

## Summary

Phase 8 builds a React dashboard from scratch (the `ui/` directory exists but is completely empty -- no package.json, no config files, no components). The backend API is fully built (Phases 5-7 are complete) with well-defined Pydantic schemas in `orchestrator/api/schemas.py` that the TypeScript types must mirror exactly. The UI connects to a FastAPI orchestrator at `localhost:8000` via REST + SSE.

The locked decision is **shadcn/ui + Tailwind CSS** with a **dark theme** and a **fixed left sidebar** layout. shadcn/ui now supports Tailwind v4 natively via `@tailwindcss/vite`, eliminating the old PostCSS/tailwind.config.js approach entirely. All components use copy-paste architecture (no npm dependency lock-in), Radix UI primitives, and CSS variables for theming. Recharts is specified in PROJECT.md for charts, and shadcn/ui has a built-in Chart wrapper that integrates with Recharts using CSS-variable-driven colors.

**One critical gap:** There is no agent interview proxy endpoint in the orchestrator. The MiroFish client (`orchestrator/clients/mirofish_client.py`) has no `chat` method. The MiroFish API does expose `POST /api/agent/{id}/chat` (per the tech spec), but the orchestrator has no route to proxy this to the UI. Phase 8 must either add this endpoint or defer the interview feature. Since UI-08 requires it, a small backend addition is needed.

**Primary recommendation:** Use the `shadcn@latest init -t vite` CLI to scaffold the project with Tailwind v4, then systematically add components. Use `@tanstack/react-query` v5 for data fetching with `refetchInterval` for campaign status polling, native `EventSource` API wrapped in a custom hook for SSE progress streaming, and `react-router-dom` v7 for client-side routing.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Use **shadcn/ui + Tailwind CSS** as the component system. Copy-paste components, fully customizable, dark theme built-in.
- **D-02:** **Dark theme** with accent colors for score indicators (green >=70, amber 40-69, red <40 per Results.md). Professional data-heavy aesthetic.
- **D-03:** **Fixed left sidebar** with campaign history list + main content area with header. Standard dashboard pattern.
- **D-04:** Campaign creation is a **single page with sections** (seed content, prediction question, demographic selector, config panel with sliders/thresholds). Not a multi-step wizard. Scroll down, click Run.
- **D-05:** Agent interview via **modal dialog** over campaign detail (per spec UI-08).
- **D-06:** Progress display is **inline in campaign detail** with step labels + ETA from SSE stream.
- **D-07:** **CRITICAL -- No generic AI slop.** The UI must be distinctive, polished, and production-grade. Use the `/frontend-design` skill during execution to ensure high design quality. Avoid cookie-cutter layouts, bland color schemes, and template-looking interfaces. The dashboard should feel like a premium tool, not a hackathon demo.

### Claude's Discretion
- Chart library choice (Recharts is specified in PROJECT.md)
- Component composition and file organization
- Animation and transition details
- Exact sidebar width and responsive breakpoints
- Tab component implementation (shadcn tabs or custom)

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| UI-01 | React + Vite + TypeScript + Tailwind scaffold with API client | Vite scaffold via `shadcn@latest init -t vite`, Tailwind v4 via `@tailwindcss/vite` plugin, API client using fetch/axios to localhost:8000 |
| UI-02 | TypeScript types matching all Pydantic schemas | Mirror `orchestrator/api/schemas.py` exactly: CampaignCreateRequest, CampaignResponse, CampaignListResponse, IterationRecord, AnalysisRecord, TribeScores, MirofishMetrics, CompositeScores, ReportResponse, ScorecardData, ScorecardVariant, ProgressEvent, EstimateRequest/Response, HealthResponse, DemographicsResponse |
| UI-03 | Layout with sidebar (campaign history) and header | Fixed left sidebar (D-03), shadcn/ui Sheet or custom sidebar component, dark theme via ThemeProvider |
| UI-04 | NewCampaign page: seed content, prediction question, demographic selector, config panel, time estimate, Run button | Single page with sections (D-04), 6 presets from GET /api/demographics, POST /api/estimate for live estimate, POST /api/campaigns to submit |
| UI-05 | CampaignDetail page with 3 tabs (Campaign, Simulation, Report) | shadcn/ui Tabs component, GET /api/campaigns/{id} for data, tab routing |
| UI-06 | Campaign tab: composite score cards (color-coded), variant ranking, iteration chart | Color coding: green >=70, amber 40-69, red <40 (inverted for backlash/polarization). Recharts LineChart for iteration trajectory. ScorecardData.variants for ranking. |
| UI-07 | Simulation tab: MiroFish metrics, sentiment timeline, coalition map, agent grid | Recharts AreaChart for sentiment_trajectory, agent grid from MiroFish agent_stats data, metrics cards |
| UI-08 | Agent interview: click agent card -> chat modal proxied through orchestrator | **GAP: Orchestrator needs a proxy endpoint for MiroFish POST /api/agent/{id}/chat.** Modal via shadcn/ui Dialog. |
| UI-09 | Report tab: verdict, scorecard, expandable deep analysis, mass psychology toggle | GET /api/campaigns/{id}/report for ReportResponse, shadcn/ui Collapsible for expandable sections, toggle for general/technical psychology |
| UI-10 | ProgressStream component connected to SSE during campaign runs | EventSource to GET /api/campaigns/{id}/progress, custom useProgress hook, step labels + ETA display |
| UI-11 | CampaignList page with status badges, click to open detail | GET /api/campaigns for CampaignListResponse, StatusBadge component (pending/running/completed/failed) |
| UI-12 | JSON and Markdown export buttons on Report tab | GET /api/campaigns/{id}/export/json and /export/markdown trigger file downloads |
| UI-13 | Loading states, error states, empty states, responsive layout | React Query loading/error states, skeleton components, empty state illustrations |
</phase_requirements>

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| react | 19.x | UI framework | Current stable, shadcn/ui components updated for React 19 |
| react-dom | 19.x | DOM rendering | Paired with React 19 |
| vite | 6.x | Build tool / dev server | Fast HMR, native ESM, official Vite template |
| typescript | 5.x | Type safety | Required for schema mirroring, shadcn/ui uses TS |
| tailwindcss | 4.x | Utility CSS | D-01 locked decision, v4 uses `@tailwindcss/vite` plugin (no PostCSS config needed) |
| @tailwindcss/vite | 4.x | Vite plugin for Tailwind v4 | Replaces old PostCSS-based setup, zero-config |
| shadcn/ui | CLI 4.x | Component library | D-01 locked decision, copy-paste components on Radix UI primitives |
| react-router-dom | 7.x | Client-side routing | Standard React routing, 3 pages (list, new, detail) |
| @tanstack/react-query | 5.x | Server state management | Data fetching, caching, polling for campaign status |
| recharts | 2.x | Charting | Specified in PROJECT.md, shadcn/ui Chart component wraps Recharts |
| lucide-react | 1.x | Icons | Default icon library for shadcn/ui |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| @radix-ui/react-* | 1.x | Accessible primitives | Installed by shadcn/ui CLI per-component (tabs, dialog, collapsible, dropdown-menu, etc.) |
| class-variance-authority | 0.7.x | Variant styling | Used by shadcn/ui button/badge variants |
| clsx | 2.x | Conditional classes | Used by shadcn/ui cn() utility |
| tailwind-merge | 3.x | Tailwind class deduplication | Used by shadcn/ui cn() utility |
| @types/node | latest | Node type definitions | Needed for Vite config path resolution |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| @tanstack/react-query | SWR | React Query has better polling (refetchInterval), mutation support, devtools |
| react-router-dom | TanStack Router | RRD v7 is simpler for 3-page app, no data loading needed at router level |
| fetch (native) | axios | fetch is built-in, no dependency; axios adds interceptors but not needed for POC |

**Installation (after Vite scaffold):**
```bash
# Create Vite project
npm create vite@latest ui -- --template react-ts
cd ui
npm install

# Add Tailwind v4 (via Vite plugin)
npm install tailwindcss @tailwindcss/vite

# Initialize shadcn/ui (configures components.json, cn utility, CSS variables)
npx shadcn@latest init

# Core dependencies
npm install react-router-dom @tanstack/react-query recharts lucide-react
```

**Version verification (confirmed 2026-03-29):**
- react: 19.2.4
- vite: 8.0.3
- typescript: 6.0.2
- tailwindcss: 4.2.2
- recharts: 3.8.1
- @tanstack/react-query: 5.95.2
- react-router-dom: 7.13.2
- lucide-react: 1.7.0

## Architecture Patterns

### Recommended Project Structure
```
ui/
├── index.html
├── package.json
├── vite.config.ts
├── tsconfig.json
├── tsconfig.app.json
├── components.json              # shadcn/ui config
├── src/
│   ├── main.tsx                 # React root + QueryClientProvider + ThemeProvider + Router
│   ├── App.tsx                  # Router outlet + Layout
│   ├── index.css                # @import "tailwindcss" + @theme CSS variables
│   ├── lib/
│   │   └── utils.ts             # cn() utility (generated by shadcn init)
│   ├── api/
│   │   ├── client.ts            # Base fetch wrapper (API_BASE_URL from env)
│   │   ├── campaigns.ts         # Campaign CRUD API functions
│   │   ├── reports.ts           # Report + export API functions
│   │   └── types.ts             # TypeScript interfaces mirroring Pydantic schemas
│   ├── hooks/
│   │   ├── use-campaigns.ts     # React Query hooks for campaign data
│   │   ├── use-progress.ts      # SSE EventSource hook for progress streaming
│   │   ├── use-time-estimate.ts # Debounced estimate API hook
│   │   └── use-health.ts        # Health check polling hook
│   ├── components/
│   │   ├── ui/                  # shadcn/ui components (button, card, tabs, dialog, etc.)
│   │   ├── layout/
│   │   │   ├── app-layout.tsx   # Sidebar + header + main content
│   │   │   ├── sidebar.tsx      # Campaign history list
│   │   │   └── header.tsx       # App title + health indicator
│   │   ├── campaign/
│   │   │   ├── campaign-form.tsx        # Full creation form (D-04: single page)
│   │   │   ├── demographic-selector.tsx # 6 presets + custom
│   │   │   ├── config-panel.tsx         # Sliders + threshold toggles
│   │   │   └── time-estimate.tsx        # Live estimate display
│   │   ├── results/
│   │   │   ├── score-card.tsx           # Single composite score with color coding
│   │   │   ├── variant-ranking.tsx      # Ranked variant list
│   │   │   ├── iteration-chart.tsx      # Recharts line chart
│   │   │   ├── verdict-display.tsx      # Layer 1 plain English
│   │   │   ├── deep-analysis.tsx        # Expandable per-iteration data
│   │   │   ├── mass-psychology.tsx       # General/technical toggle
│   │   │   └── export-buttons.tsx       # JSON + Markdown download
│   │   ├── simulation/
│   │   │   ├── metrics-panel.tsx        # MiroFish 8 metrics display
│   │   │   ├── sentiment-timeline.tsx   # Recharts area chart
│   │   │   ├── agent-grid.tsx           # Clickable agent cards
│   │   │   └── agent-interview.tsx      # Chat modal (Dialog)
│   │   ├── progress/
│   │   │   └── progress-stream.tsx      # SSE progress display
│   │   └── common/
│   │       ├── status-badge.tsx         # Status pill (pending/running/completed/failed)
│   │       ├── score-bar.tsx            # Horizontal bar with color
│   │       ├── loading-skeleton.tsx     # Skeleton shimmer
│   │       ├── error-state.tsx          # Error boundary display
│   │       └── empty-state.tsx          # Empty campaign list state
│   ├── pages/
│   │   ├── campaign-list.tsx    # All campaigns with status badges
│   │   ├── new-campaign.tsx     # Campaign creation (D-04 single page)
│   │   └── campaign-detail.tsx  # 3-tab results view
│   └── utils/
│       ├── colors.ts            # Score -> color mapping (green/amber/red + inverted logic)
│       └── formatters.ts        # Number, duration, date formatting
```

### Pattern 1: TypeScript Types Mirroring Pydantic Schemas
**What:** Create TypeScript interfaces that exactly match the Pydantic models in `orchestrator/api/schemas.py`
**When to use:** Every API call and response
**Example:**
```typescript
// Source: Derived from orchestrator/api/schemas.py

export interface CampaignCreateRequest {
  seed_content: string;        // min 100, max 25000 chars
  prediction_question: string; // min 10 chars
  demographic: string;         // preset key or "custom"
  demographic_custom?: string | null;
  agent_count?: number;        // 20-200, default 40
  max_iterations?: number;     // 1-10, default 4
  thresholds?: Record<string, number> | null;
  constraints?: string | null;
  auto_start?: boolean;        // default true
}

export interface TribeScores {
  attention_capture: number;
  emotional_resonance: number;
  memory_encoding: number;
  reward_response: number;
  threat_detection: number;
  cognitive_load: number;
  social_relevance: number;
}

export interface CompositeScores {
  attention_score: number | null;
  virality_potential: number | null;
  backlash_risk: number | null;
  memory_durability: number | null;
  conversion_potential: number | null;
  audience_fit: number | null;
  polarization_index: number | null;
}

export interface CampaignResponse {
  id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  seed_content: string;
  prediction_question: string;
  demographic: string;
  demographic_custom?: string | null;
  agent_count: number;
  max_iterations: number;
  thresholds?: Record<string, number> | null;
  constraints?: string | null;
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
  error?: string | null;
  iterations?: IterationRecord[] | null;
  analyses?: AnalysisRecord[] | null;
}
```

### Pattern 2: SSE Progress Hook (EventSource API)
**What:** Custom React hook wrapping the native EventSource API for real-time campaign progress
**When to use:** During active campaign runs on CampaignDetail page
**Example:**
```typescript
// Source: Built from orchestrator/api/progress.py SSE endpoint pattern

import { useEffect, useRef, useState, useCallback } from 'react';
import { ProgressEvent } from '@/api/types';

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const TERMINAL_EVENTS = new Set(['campaign_complete', 'campaign_error']);

export function useProgress(campaignId: string | null) {
  const [events, setEvents] = useState<ProgressEvent[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [isComplete, setIsComplete] = useState(false);
  const esRef = useRef<EventSource | null>(null);

  const connect = useCallback(() => {
    if (!campaignId) return;

    const es = new EventSource(
      `${API_BASE}/api/campaigns/${campaignId}/progress`
    );
    esRef.current = es;

    es.onopen = () => setIsConnected(true);
    es.onerror = () => {
      setIsConnected(false);
      es.close();
    };

    // Listen for specific event types from the backend
    const eventTypes = [
      'iteration_start', 'step_start', 'step_complete',
      'iteration_complete', 'threshold_check', 'convergence_check',
      'campaign_complete', 'campaign_error'
    ];

    for (const type of eventTypes) {
      es.addEventListener(type, (e: MessageEvent) => {
        const data: ProgressEvent = JSON.parse(e.data);
        setEvents(prev => [...prev, data]);
        if (TERMINAL_EVENTS.has(data.event)) {
          setIsComplete(true);
          es.close();
        }
      });
    }
  }, [campaignId]);

  useEffect(() => {
    connect();
    return () => {
      esRef.current?.close();
    };
  }, [connect]);

  const latestEvent = events[events.length - 1] ?? null;

  return { events, latestEvent, isConnected, isComplete };
}
```

### Pattern 3: Color Coding Utility
**What:** Score-to-color mapping matching the backend `color_code_score()` function
**When to use:** Every composite score display
**Example:**
```typescript
// Source: orchestrator/engine/report_generator.py color_code_score()
// Per Results.md Section 4.2:
//   Normal: green >= 70, amber 40-69, red < 40
//   Inverted (backlash_risk, polarization_index): green < 30, amber 30-59, red >= 60

const INVERTED_SCORES = new Set(['backlash_risk', 'polarization_index']);

export function getScoreColor(metricName: string, value: number): 'green' | 'amber' | 'red' {
  if (INVERTED_SCORES.has(metricName)) {
    if (value < 30) return 'green';
    if (value < 60) return 'amber';
    return 'red';
  }
  if (value >= 70) return 'green';
  if (value >= 40) return 'amber';
  return 'red';
}

// CSS variable mapping for Tailwind
export const SCORE_COLORS = {
  green: 'text-emerald-400',
  amber: 'text-amber-400',
  red: 'text-red-400',
} as const;

export const SCORE_BG_COLORS = {
  green: 'bg-emerald-500/20',
  amber: 'bg-amber-500/20',
  red: 'bg-red-500/20',
} as const;
```

### Pattern 4: React Query Campaign Data Hook
**What:** Centralized data fetching with automatic polling for running campaigns
**When to use:** CampaignDetail and CampaignList pages
**Example:**
```typescript
// Source: @tanstack/react-query v5 patterns

import { useQuery } from '@tanstack/react-query';
import { getCampaign, listCampaigns } from '@/api/campaigns';

export function useCampaign(id: string) {
  return useQuery({
    queryKey: ['campaign', id],
    queryFn: () => getCampaign(id),
    // Poll every 3s while campaign is running
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === 'running' ? 3000 : false;
    },
  });
}

export function useCampaigns() {
  return useQuery({
    queryKey: ['campaigns'],
    queryFn: listCampaigns,
  });
}
```

### Pattern 5: Dark Theme CSS Variables (Tailwind v4)
**What:** CSS variable system for dark-first theme with score colors
**When to use:** Global theme configuration in index.css
**Example:**
```css
/* Source: shadcn/ui Tailwind v4 theming docs */
@import "tailwindcss";

@theme inline {
  --color-background: oklch(0.145 0.005 285);
  --color-foreground: oklch(0.985 0.002 285);
  --color-card: oklch(0.17 0.005 285);
  --color-card-foreground: oklch(0.985 0.002 285);
  --color-primary: oklch(0.65 0.2 250);
  --color-primary-foreground: oklch(0.985 0.002 285);
  --color-muted: oklch(0.25 0.005 285);
  --color-muted-foreground: oklch(0.65 0.015 285);
  --color-border: oklch(0.3 0.005 285);
  /* Score indicator colors */
  --color-score-green: oklch(0.72 0.19 163);
  --color-score-amber: oklch(0.75 0.18 75);
  --color-score-red: oklch(0.65 0.22 25);
  /* Chart colors */
  --color-chart-1: oklch(0.65 0.2 250);
  --color-chart-2: oklch(0.72 0.19 163);
  --color-chart-3: oklch(0.75 0.18 75);
  --color-chart-4: oklch(0.65 0.22 25);
  --color-chart-5: oklch(0.7 0.15 300);
}
```

### Anti-Patterns to Avoid
- **Hand-coding component primitives:** Never build custom dropdowns, modals, tabs, or tooltips from scratch. Use shadcn/ui components which wrap accessible Radix UI primitives.
- **Hardcoded colors instead of CSS variables:** All theme colors must use CSS variables so dark mode works automatically. Never use raw hex values for UI colors.
- **Fetching inside useEffect without React Query:** Always use React Query for API calls. It handles caching, deduplication, error/loading states, and refetching. Never use raw `useEffect + fetch` patterns.
- **Polling via setInterval:** Use React Query's `refetchInterval` instead. It integrates with the query lifecycle and stops when the component unmounts.
- **Storing server state in useState:** Campaign data, reports, demographics all live in React Query cache. Only use useState for local UI state (form inputs, modal open/close, tab selection).
- **Monolithic page components:** Break pages into focused components (ScoreCard, VariantRanking, IterationChart). Each component should be <150 lines.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Accessible modals | Custom overlay + focus trap | shadcn/ui Dialog (Radix Dialog) | Focus management, escape key, screen readers, portal rendering |
| Tab panels | Custom tab state management | shadcn/ui Tabs (Radix Tabs) | Keyboard navigation, ARIA attributes, controlled/uncontrolled modes |
| Dropdown menus | Custom positioned dropdown | shadcn/ui DropdownMenu (Radix) | Positioning engine, keyboard nav, submenus, portal |
| Toast notifications | Custom toast system | shadcn/ui Sonner | Stacking, dismissal, animation, accessibility |
| Form validation | Manual if/else checks | HTML5 validation + controlled inputs | Sufficient for POC forms, no need for react-hook-form complexity |
| Data fetching layer | Custom fetch + cache | @tanstack/react-query | Deduplication, stale-while-revalidate, error retry, devtools |
| SSE reconnection | Custom reconnect logic | Native EventSource (auto-reconnects) | EventSource spec includes automatic reconnection on failure |
| File downloads | Custom blob handling | Window location + API content-disposition | Backend already sets Content-Disposition headers on export endpoints |
| Collapsible sections | Custom animation | shadcn/ui Collapsible (Radix) | Animated expand/collapse with accessibility |
| Score color logic | Per-component inline conditions | Shared utility function (colors.ts) | Backend has identical logic -- single source of truth |

**Key insight:** shadcn/ui + Radix UI eliminates all primitive UI complexity. The only custom code should be business logic (score visualization, campaign flow, SSE integration) and data transformation.

## Common Pitfalls

### Pitfall 1: Agent Interview Endpoint Missing
**What goes wrong:** UI-08 requires clicking an agent card to open a chat modal proxied through the orchestrator. The orchestrator currently has NO agent interview endpoint. The MiroFish API exposes `POST /api/agent/{id}/chat` but nothing in the orchestrator proxies to it.
**Why it happens:** Phase 5 built campaign CRUD, scoring, and simulation orchestration, but agent interview was not in the orchestrator requirements (ORCH-01 through ORCH-14).
**How to avoid:** Add a proxy endpoint to the orchestrator before building the frontend chat component: `POST /api/campaigns/{campaign_id}/agents/{agent_id}/chat` that forwards to MiroFish.
**Warning signs:** 404 errors when the chat modal tries to send messages.

### Pitfall 2: SSE EventSource Named Events vs Generic Messages
**What goes wrong:** The backend sends named event types (e.g., `event: iteration_start`), not generic `message` events. If the frontend uses `es.onmessage`, it will receive nothing because named events are not dispatched to `onmessage`.
**Why it happens:** The SSE spec distinguishes between named events (dispatched to `addEventListener(type)`) and unnamed events (dispatched to `onmessage`).
**How to avoid:** Use `es.addEventListener('iteration_start', handler)` for each event type, NOT `es.onmessage`. See the progress.py source -- it yields `{"event": event_type, "data": json}`.
**Warning signs:** EventSource connects (onopen fires) but no events ever arrive.

### Pitfall 3: CORS Preflight for POST Requests
**What goes wrong:** The Vite dev server runs on port 5173 and the API on port 8000. POST requests trigger CORS preflight (OPTIONS). If the browser doesn't get proper CORS headers on the OPTIONS response, the POST is blocked.
**Why it happens:** Cross-origin POST with JSON content-type triggers preflight in all browsers.
**How to avoid:** The orchestrator already configures CORS for `http://localhost:5173` with `allow_methods=["*"]` and `allow_headers=["*"]`. No changes needed. But if the Vite dev server URL changes, update the CORS origin in `orchestrator/api/__init__.py`.
**Warning signs:** "CORS policy" errors in browser console.

### Pitfall 4: Stale Campaign Data After SSE Completion
**What goes wrong:** SSE reports campaign_complete, but the React Query cache still has the old "running" status. The UI shows completion but the data (iterations, analyses, report) is stale.
**Why it happens:** SSE and React Query are separate data flows. SSE completion doesn't automatically trigger a React Query refetch.
**How to avoid:** When the SSE `campaign_complete` event arrives, call `queryClient.invalidateQueries({ queryKey: ['campaign', id] })` to force a fresh fetch of the full campaign data including the report.
**Warning signs:** Campaign shows as "completed" in the progress bar but results tabs are empty or show old data.

### Pitfall 5: Tailwind v4 Breaking Changes from v3
**What goes wrong:** Tailwind v4 eliminates `tailwind.config.js`, uses `@theme` in CSS instead. The old config-based approach with `content` array, `plugins`, and `theme.extend` does not work.
**Why it happens:** Tailwind v4 is a complete rewrite. Many online tutorials still show v3 patterns.
**How to avoid:** Use `@tailwindcss/vite` plugin (not PostCSS). Define theme in CSS with `@theme inline { }`. Colors use OKLCH by default. There is no tailwind.config.js file.
**Warning signs:** Classes not applying, build errors about missing config, "darkMode" config having no effect.

### Pitfall 6: SSE Connection Stays Open After Navigation
**What goes wrong:** User navigates away from CampaignDetail while a campaign is running. The EventSource connection stays open, leaking memory and receiving events that update unmounted component state.
**Why it happens:** EventSource must be explicitly closed; it doesn't close on component unmount automatically.
**How to avoid:** Close EventSource in the useEffect cleanup function. The useProgress hook pattern above handles this correctly with `esRef.current?.close()` in the cleanup return.
**Warning signs:** React "Can't perform a state update on an unmounted component" warning (though React 18+ suppresses this warning, it still wastes resources).

### Pitfall 7: File Export Download Handling
**What goes wrong:** Clicking export buttons makes a fetch request but the file doesn't download -- it just returns data to JavaScript.
**Why it happens:** fetch() doesn't trigger browser downloads. The response has `Content-Disposition: attachment` but the browser only acts on it for navigation-initiated requests.
**How to avoid:** Either use `window.open(url)` to trigger a native download, or use the fetch response to create a Blob URL and trigger download via a programmatic `<a>` click. The simpler approach is `window.open()` since no auth headers are needed (POC, no auth).
**Warning signs:** Export button "works" (no errors) but nothing downloads.

### Pitfall 8: ScorecardVariant.color_coding Already Provided by Backend
**What goes wrong:** Frontend re-computes color coding when the backend already provides it in `ScorecardVariant.color_coding: dict[str, str]`.
**Why it happens:** Developer doesn't notice the backend includes pre-computed colors.
**How to avoid:** Use `variant.color_coding` from the API response for scorecard display. Only compute colors client-side for the Campaign tab score cards (which show CompositeScores directly, not the scorecard layer).
**Warning signs:** Color coding mismatch between Campaign tab and Report tab scorecard.

## Code Examples

### API Client Base
```typescript
// Source: Standard fetch wrapper pattern

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => res.statusText);
    throw new Error(`API ${res.status}: ${detail}`);
  }
  return res.json();
}

// Campaign API functions
export const createCampaign = (body: CampaignCreateRequest) =>
  apiFetch<CampaignResponse>('/api/campaigns', {
    method: 'POST',
    body: JSON.stringify(body),
  });

export const getCampaign = (id: string) =>
  apiFetch<CampaignResponse>(`/api/campaigns/${id}`);

export const listCampaigns = () =>
  apiFetch<CampaignListResponse>('/api/campaigns');

export const getReport = (campaignId: string) =>
  apiFetch<ReportResponse>(`/api/campaigns/${campaignId}/report`);

export const getDemographics = () =>
  apiFetch<DemographicsResponse>('/api/demographics');

export const getEstimate = (body: EstimateRequest) =>
  apiFetch<EstimateResponse>('/api/estimate', {
    method: 'POST',
    body: JSON.stringify(body),
  });
```

### File Export via window.open
```typescript
// Source: Standard browser download pattern (no auth needed for POC)

export function downloadExport(campaignId: string, format: 'json' | 'markdown') {
  const url = `${API_BASE}/api/campaigns/${campaignId}/export/${format}`;
  window.open(url, '_blank');
}
```

### React Query Provider Setup
```typescript
// Source: @tanstack/react-query v5 docs

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,      // 30s before refetch on focus
      retry: 1,                // One retry on failure
      refetchOnWindowFocus: false, // Avoid jarring refetches
    },
  },
});

// In main.tsx:
<QueryClientProvider client={queryClient}>
  <ThemeProvider defaultTheme="dark">
    <RouterProvider router={router} />
  </ThemeProvider>
</QueryClientProvider>
```

### shadcn/ui Components to Install
```bash
# Core layout and interaction components
npx shadcn@latest add button card tabs dialog collapsible
npx shadcn@latest add dropdown-menu input textarea label slider
npx shadcn@latest add badge separator scroll-area skeleton
npx shadcn@latest add select toggle-group tooltip chart sonner
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Tailwind v3 + PostCSS + tailwind.config.js | Tailwind v4 + @tailwindcss/vite + @theme in CSS | Jan 2025 | No config file needed, OKLCH colors, @theme directive |
| React.forwardRef everywhere | Named functions + data-slot attributes | React 19 + shadcn/ui 2025 update | Simpler component code, less boilerplate |
| HSL color system in shadcn/ui | OKLCH color system | shadcn/ui Tailwind v4 update | Better color perception, wider gamut |
| shadcn/ui toast component | Sonner (shadcn/ui wraps sonner) | 2024-2025 | Better toast UX, `toast` component deprecated |
| `default` style in shadcn/ui | `new-york` style (default now) | 2025 | Default style deprecated for new projects |

**Deprecated/outdated:**
- tailwind.config.js: Tailwind v4 does not use it. Use `@theme` in CSS instead.
- PostCSS-based Tailwind: Use `@tailwindcss/vite` plugin for Vite projects.
- `React.forwardRef`: shadcn/ui components updated to use named functions.
- HSL color tokens: Now OKLCH.

## Open Questions

1. **Agent Interview Backend Endpoint**
   - What we know: MiroFish exposes `POST /api/agent/{id}/chat`. The orchestrator has no proxy route for this.
   - What's unclear: What request/response shape does the MiroFish chat endpoint expect? Does it need a simulation_id for context?
   - Recommendation: The plan should include a small backend task to add `POST /api/campaigns/{campaign_id}/agents/{agent_id}/chat` to the orchestrator that proxies to MiroFish. Examine the MiroFish API docs/source during implementation.

2. **Agent Data Availability**
   - What we know: MiroFish simulation results include `agent_stats` (fetched by `_extract_results` in the client). This data is available through the IterationRecord's raw data.
   - What's unclear: What exactly is in `agent_stats`? What fields identify an agent (name, id, role)? Is there enough to render meaningful agent cards?
   - Recommendation: The agent grid should render whatever fields are available in agent_stats. If data is sparse, display basic cards with agent IDs. The interview modal adds depth.

3. **Coalition Map Visualization**
   - What we know: UI-07 lists "coalition map" but MiroFish returns `coalition_formation: int` (a count of coalitions, not spatial data).
   - What's unclear: Is there enough data for a meaningful "map"? The Pydantic schema has `coalition_formation: int`.
   - Recommendation: Display coalition count as a metric card. If agent_stats includes coalition membership, build a simple grouped visualization. Do NOT over-invest in a spatial map for integer data.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Node.js | Vite build + dev server | Yes | 22.22.0 | -- |
| npm | Package management | Yes | 10.9.4 | -- |
| Orchestrator API (port 8000) | All API calls | Yes (built in Phase 5-7) | 0.1.0 | -- |
| Vite dev server (port 5173) | Frontend development | Will be created | -- | -- |

**Missing dependencies with no fallback:** None. All tooling is available.

**Missing dependencies with fallback:** None.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Vitest 4.x + @testing-library/react 16.x |
| Config file | `ui/vitest.config.ts` (needs creation -- Wave 0) |
| Quick run command | `cd ui && npx vitest run --reporter=verbose` |
| Full suite command | `cd ui && npx vitest run` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| UI-01 | Vite scaffold builds, API client connects | smoke | `cd ui && npm run build` | No -- Wave 0 |
| UI-02 | TypeScript types match Pydantic schemas | unit (type compilation) | `cd ui && npx tsc --noEmit` | No -- Wave 0 |
| UI-03 | Layout renders sidebar + header | unit | `cd ui && npx vitest run src/components/layout` | No -- Wave 0 |
| UI-04 | NewCampaign form submits valid data | unit | `cd ui && npx vitest run src/pages/new-campaign` | No -- Wave 0 |
| UI-05 | CampaignDetail renders 3 tabs | unit | `cd ui && npx vitest run src/pages/campaign-detail` | No -- Wave 0 |
| UI-06 | Score cards render with correct colors | unit | `cd ui && npx vitest run src/utils/colors.test.ts` | No -- Wave 0 |
| UI-07 | Simulation tab renders metrics | unit | `cd ui && npx vitest run src/components/simulation` | No -- Wave 0 |
| UI-08 | Agent interview modal opens/closes | unit | `cd ui && npx vitest run src/components/simulation/agent-interview` | No -- Wave 0 |
| UI-09 | Report tab renders all 4 layers | unit | `cd ui && npx vitest run src/components/results` | No -- Wave 0 |
| UI-10 | Progress hook processes SSE events | unit | `cd ui && npx vitest run src/hooks/use-progress` | No -- Wave 0 |
| UI-11 | Campaign list renders with badges | unit | `cd ui && npx vitest run src/pages/campaign-list` | No -- Wave 0 |
| UI-12 | Export triggers download | unit | `cd ui && npx vitest run src/components/results/export-buttons` | No -- Wave 0 |
| UI-13 | Loading/error/empty states render | unit | `cd ui && npx vitest run src/components/common` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `cd ui && npx vitest run --reporter=verbose`
- **Per wave merge:** `cd ui && npx vitest run && npx tsc --noEmit`
- **Phase gate:** Full suite green + TypeScript compilation clean before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `ui/vitest.config.ts` -- Vitest configuration with React testing library setup
- [ ] `ui/src/test/setup.ts` -- Testing library global setup (cleanup, jest-dom matchers)
- [ ] Framework install: `npm install -D vitest @testing-library/react @testing-library/jest-dom @testing-library/user-event jsdom`
- [ ] `ui/src/utils/colors.test.ts` -- Covers UI-06 color coding logic

## Project Constraints (from CLAUDE.md)

- **Scope:** Phase 1 POC only -- no auth, no HTTPS, no multi-user
- **Hardware:** Single RTX 5070 Ti GPU (shared, but irrelevant for frontend)
- **Performance:** Full campaign <= 20 minutes (frontend must show progress during this time)
- **API:** UI connects ONLY to orchestrator at localhost:8000 (never directly to MiroFish or TRIBE)
- **CORS:** Already configured for localhost:5173 in orchestrator
- **Dependency:** MiroFish is a submodule with minimal modifications
- **GSD Workflow:** Use GSD commands for execution; use `/frontend-design` skill per D-07

## Sources

### Primary (HIGH confidence)
- `orchestrator/api/schemas.py` -- All Pydantic response models (read directly from codebase)
- `orchestrator/api/campaigns.py` -- Campaign CRUD endpoints (read directly)
- `orchestrator/api/progress.py` -- SSE endpoint implementation (read directly)
- `orchestrator/api/reports.py` -- Report and export endpoints (read directly)
- `orchestrator/api/__init__.py` -- CORS config, lifespan, router mounting (read directly)
- `orchestrator/clients/mirofish_client.py` -- MiroFish client (confirmed no chat method)
- `orchestrator/engine/report_generator.py` -- color_code_score() logic (read directly)
- `docs/Results.md` -- Full output layer specifications and color coding standards (read directly)
- `docs/Application_Technical_Spec.md` -- System architecture and UI directory structure (read directly)
- [shadcn/ui Vite installation](https://ui.shadcn.com/docs/installation/vite) -- Official setup guide
- [shadcn/ui Tailwind v4](https://ui.shadcn.com/docs/tailwind-v4) -- Tailwind v4 migration/setup
- [shadcn/ui Dark Mode (Vite)](https://ui.shadcn.com/docs/dark-mode/vite) -- ThemeProvider pattern
- [shadcn/ui Chart Component](https://ui.shadcn.com/docs/components/radix/chart) -- Recharts integration

### Secondary (MEDIUM confidence)
- npm registry version checks (2026-03-29) -- All package versions verified current

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- All libraries verified via npm registry, official docs fetched and read
- Architecture: HIGH -- Based on official shadcn/ui + Vite patterns and codebase analysis of all backend APIs
- Pitfalls: HIGH -- Derived from direct codebase reading (SSE named events, missing agent endpoint, CORS config)
- Backend integration: HIGH -- All schemas, endpoints, and patterns read directly from source code

**Research date:** 2026-03-29
**Valid until:** 2026-04-28 (stable ecosystem, libraries are mature)
