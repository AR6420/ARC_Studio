---
phase: 08-ui-dashboard
plan: 06
subsystem: ui, api
tags: [react, recharts, fastapi, mirofish, agent-chat, simulation, area-chart, dialog]

# Dependency graph
requires:
  - phase: 08-01
    provides: UI scaffold, API layer, shadcn components, Recharts setup
  - phase: 08-05
    provides: CampaignDetail page with tab structure (parallel wave 3)
  - phase: 05-02
    provides: MirofishClient with httpx.AsyncClient pattern
provides:
  - Backend proxy endpoint for MiroFish agent chat (POST /api/campaigns/{id}/agents/{id}/chat)
  - MetricsPanel component displaying 8 MiroFish social metrics
  - SentimentTimeline area chart for sentiment trajectory visualization
  - AgentGrid with clickable agent profile cards
  - AgentInterview dialog modal for live agent chat
  - useAgentChat React hook with local message history management
  - chatAgent API function bridging frontend to orchestrator proxy
affects: [08-07, 09-integration]

# Tech tracking
tech-stack:
  added: []
  patterns: [agent-chat-proxy, recharts-area-chart-with-gradient, deterministic-avatar-hue, chat-bubble-ui]

key-files:
  created:
    - orchestrator/api/agents.py
    - ui/src/components/simulation/metrics-panel.tsx
    - ui/src/components/simulation/sentiment-timeline.tsx
    - ui/src/components/simulation/agent-grid.tsx
    - ui/src/components/simulation/agent-interview.tsx
    - ui/src/hooks/use-agent-chat.ts
    - ui/src/pages/campaign-detail.tsx
  modified:
    - orchestrator/api/__init__.py
    - orchestrator/api/schemas.py
    - orchestrator/clients/mirofish_client.py
    - ui/src/api/types.ts
    - ui/src/api/campaigns.ts
    - ui/src/App.tsx

key-decisions:
  - "Agent chat proxied through orchestrator (not direct frontend-to-MiroFish) for consistent error handling"
  - "AgentGrid uses deterministic hue from agent ID for avatar colors -- no external avatar service needed"
  - "SentimentTimeline uses shadcn ChartContainer with OKLCH color for dark-theme consistency"
  - "AgentInterview clears chat history on dialog close to prevent stale state across agents"
  - "CampaignDetail page created with 3-tab structure (Campaign tab placeholder pending 08-05 merge)"

patterns-established:
  - "Agent chat proxy: UI -> orchestrator /api/campaigns/{id}/agents/{id}/chat -> MiroFish /api/agent/{id}/chat"
  - "Chat hook pattern: useMutation + local state array for message history"
  - "Deterministic avatar: hash agent ID to hue value for consistent but varied colors"
  - "Simulation components: null-safe with dashed-border empty states"

requirements-completed: [UI-07, UI-08]

# Metrics
duration: 25min
completed: 2026-03-29
---

# Phase 08 Plan 06: Simulation Tab Summary

**Simulation tab with 8-metric MiroFish panel, sentiment area chart, agent profile grid, and live agent interview modal backed by a new orchestrator proxy endpoint**

## Performance

- **Duration:** 25 min
- **Started:** 2026-03-29T22:09:08Z
- **Completed:** 2026-03-29T22:34:28Z
- **Tasks:** 2
- **Files modified:** 13

## Accomplishments
- Backend agent chat proxy endpoint forwarding to MiroFish POST /api/agent/{id}/chat with 502 fallback
- 8 MiroFish metrics displayed as card grid with contextual icons, formatted values, and descriptions
- Sentiment trajectory rendered as Recharts AreaChart with gradient fill and dark-themed tooltip
- Agent grid with deterministic pastel avatars, sentiment indicators, and interview call-to-action
- Chat interface in shadcn Dialog with user/agent bubbles, suggested prompts, and loading states
- Full CampaignDetail page with 3-tab structure wired for Simulation tab content

## Task Commits

Each task was committed atomically:

1. **Task 1: Add agent chat proxy endpoint to orchestrator backend** - `8699420` (feat)
2. **Task 2: Build Simulation tab components** - `84d8442` (feat)

## Files Created/Modified
- `orchestrator/api/agents.py` - Agent chat proxy router with POST endpoint
- `orchestrator/api/schemas.py` - AgentChatRequest/AgentChatResponse Pydantic models
- `orchestrator/clients/mirofish_client.py` - chat_agent method with graceful degradation
- `orchestrator/api/__init__.py` - Mounted agents_router at /api prefix
- `ui/src/components/simulation/metrics-panel.tsx` - 8 MiroFish metrics as card grid
- `ui/src/components/simulation/sentiment-timeline.tsx` - Recharts AreaChart for sentiment trajectory
- `ui/src/components/simulation/agent-grid.tsx` - Clickable agent profile cards with avatars
- `ui/src/components/simulation/agent-interview.tsx` - Dialog modal chat interface
- `ui/src/hooks/use-agent-chat.ts` - React hook for agent chat with useMutation
- `ui/src/api/types.ts` - Added AgentChatRequest/AgentChatResponse interfaces
- `ui/src/api/campaigns.ts` - Added chatAgent API function
- `ui/src/pages/campaign-detail.tsx` - Campaign detail page with 3-tab structure
- `ui/src/App.tsx` - Replaced placeholder route with real CampaignDetail component

## Decisions Made
- Agent chat proxied through orchestrator rather than direct frontend-to-MiroFish calls, keeping consistent error handling and CORS control
- AgentGrid uses deterministic hue from agent ID hash for avatar background colors, avoiding external avatar dependencies
- SentimentTimeline uses shadcn ChartContainer wrapper with OKLCH color values for seamless dark-theme integration
- AgentInterview modal clears chat history on close to prevent stale conversation state when switching between agents
- CampaignDetail page created fresh since 08-05 (which also creates it) runs in parallel; merge will reconcile

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Removed unused campaignId prop from AgentGrid**
- **Found during:** Task 2 (Build simulation components)
- **Issue:** TypeScript strict mode flagged campaignId as declared but never read in AgentGrid
- **Fix:** Removed campaignId from AgentGridProps since it's only needed by the parent for the interview modal, not inside the grid itself
- **Files modified:** ui/src/components/simulation/agent-grid.tsx, ui/src/pages/campaign-detail.tsx
- **Verification:** npm run build succeeds
- **Committed in:** 84d8442 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Minor interface adjustment. No scope creep.

## Known Stubs
- `campaign-detail.tsx` Campaign tab content is a placeholder pending 08-05 merge
- `campaign-detail.tsx` Report tab content is a placeholder pending 08-07
- `extractAgents()` returns empty array -- real agent data requires MiroFish agent_stats in campaign API response (future integration)

## Issues Encountered
- node_modules not present in worktree; resolved with npm install before build
- 08-05 (which creates campaign-detail.tsx) not yet merged into this worktree; created page with full 3-tab structure here, merge will reconcile

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Simulation tab components ready, will render data when MiroFish runs complete
- Agent interview modal ready, will function when MiroFish agent chat API is accessible
- CampaignDetail page needs merge with 08-05 (Campaign tab) and 08-07 (Report tab)
- Agent grid currently shows empty state; real agent data integration depends on MiroFish agent_stats being included in campaign response

---
*Phase: 08-ui-dashboard*
*Completed: 2026-03-29*
