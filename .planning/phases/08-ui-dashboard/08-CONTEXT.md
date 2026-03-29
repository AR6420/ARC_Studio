# Phase 8: UI Dashboard - Context

**Gathered:** 2026-03-29
**Status:** Ready for planning

<domain>
## Phase Boundary

Build a React + Vite + TypeScript dashboard for the Nexus Sim orchestrator. Users create campaigns, watch real-time progress via SSE, view results across three tabs (Campaign, Simulation, Report), and interview simulated agents via a chat modal. Includes campaign list with status badges, loading/error/empty states, and responsive layout.

Requirements: UI-01 through UI-13.

</domain>

<decisions>
## Implementation Decisions

### Visual Design
- **D-01:** Use **shadcn/ui + Tailwind CSS** as the component system. Copy-paste components, fully customizable, dark theme built-in.
- **D-02:** **Dark theme** with accent colors for score indicators (green >=70, amber 40-69, red <40 per Results.md). Professional data-heavy aesthetic.
- **D-03:** **Fixed left sidebar** with campaign history list + main content area with header. Standard dashboard pattern.

### Interaction Patterns
- **D-04:** Campaign creation is a **single page with sections** (seed content, prediction question, demographic selector, config panel with sliders/thresholds). Not a multi-step wizard. Scroll down, click Run.
- **D-05:** Agent interview via **modal dialog** over campaign detail (per spec UI-08).
- **D-06:** Progress display is **inline in campaign detail** with step labels + ETA from SSE stream.

### Design Quality
- **D-07:** **CRITICAL — No generic AI slop.** The UI must be distinctive, polished, and production-grade. Use the `/frontend-design` skill during execution to ensure high design quality. Avoid cookie-cutter layouts, bland color schemes, and template-looking interfaces. The dashboard should feel like a premium tool, not a hackathon demo.

### Claude's Discretion
- Chart library choice (Recharts is specified in PROJECT.md)
- Component composition and file organization
- Animation and transition details
- Exact sidebar width and responsive breakpoints
- Tab component implementation (shadcn tabs or custom)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### UI Specifications
- `docs/Results.md` §3.1 — All 4 output layers with display requirements
- `docs/Results.md` §4.2 — Color coding standards (green >=70, amber 40-69, red <40, inverted for backlash/polarization)
- `docs/Application_Technical_Spec.md` — Full technical specification

### API Endpoints (Backend Already Built)
- `orchestrator/api/campaigns.py` — Campaign CRUD (POST/GET/DELETE)
- `orchestrator/api/health.py` — Health check + demographics
- `orchestrator/api/progress.py` — SSE endpoint + estimate
- `orchestrator/api/reports.py` — Report retrieval + JSON/Markdown export
- `orchestrator/api/schemas.py` — All Pydantic response models (TypeScript types must match)

### Existing UI Directory
- `ui/` — React + Vite scaffold (if exists from Phase 1, or needs creation)

### Project Requirements
- `.planning/REQUIREMENTS.md` — UI-01 through UI-13 requirement definitions

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **Pydantic schemas** (`orchestrator/api/schemas.py`): TypeScript types should mirror these exactly
- **Demographic profiles** (`orchestrator/prompts/demographic_profiles.py`): 6 presets for selector
- **Color coding logic** (`orchestrator/engine/report_generator.py`): color_code_score() for reference

### Established Patterns
- All API calls are REST over localhost:8000
- SSE for real-time progress (EventSource API)
- Campaign CRUD follows standard REST patterns

### Integration Points
- **API client**: fetch or axios to localhost:8000/api/*
- **SSE stream**: EventSource to /api/campaigns/{id}/progress
- **Agent interview**: POST proxy through orchestrator to MiroFish

</code_context>

<specifics>
## Specific Ideas

- **Design quality is non-negotiable** — use /frontend-design skill during execution
- Dark theme with data-visualization focus — think Bloomberg terminal meets modern SaaS
- Score cards should be visually prominent with clear color coding
- Iteration trajectory chart (Recharts) should show improvement over time
- Agent grid should feel like a real social network simulation view

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 08-ui-dashboard*
*Context gathered: 2026-03-29*
