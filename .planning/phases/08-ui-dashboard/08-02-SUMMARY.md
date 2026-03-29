---
phase: 08-ui-dashboard
plan: 02
subsystem: ui
tags: [react, layout, sidebar, header, routing, status-badge, campaign-list, dark-theme]

# Dependency graph
requires:
  - phase: 08-ui-dashboard
    plan: 01
    provides: Vite scaffold, TypeScript types, API client, React Query hooks, shadcn/ui components
provides:
  - Fixed sidebar layout shell with campaign history and health indicator
  - StatusBadge component for all 4 campaign states
  - Loading/error/empty state common components
  - CampaignList page with responsive card grid
  - Full routing structure (/, /campaigns, /campaigns/new, /campaigns/:id)
affects: [08-03, 08-04, 08-05, 08-06, 08-07]

# Tech tracking
tech-stack:
  added: []
  patterns: [layout-shell-outlet, sidebar-active-route-highlight, health-indicator-tooltip, status-badge-config-map]

key-files:
  created:
    - ui/src/components/layout/app-layout.tsx
    - ui/src/components/layout/sidebar.tsx
    - ui/src/components/layout/header.tsx
    - ui/src/components/common/status-badge.tsx
    - ui/src/components/common/loading-skeleton.tsx
    - ui/src/components/common/error-state.tsx
    - ui/src/components/common/empty-state.tsx
    - ui/src/pages/campaign-list.tsx
  modified:
    - ui/src/App.tsx

key-decisions:
  - "Layout uses React Router Outlet pattern: AppLayout wraps all /campaigns/* routes as a layout route"
  - "Sidebar highlights active campaign by matching route param to campaign.id"
  - "Health indicator uses pulsing dot with tooltip showing per-service breakdown"
  - "StatusBadge uses config map pattern: each status maps to icon, label, and OKLCH color classes"

patterns-established:
  - "AppLayout as layout route with Outlet for nested content rendering"
  - "Common state components (ErrorState, EmptyState, LoadingSkeleton) with consistent API across the app"
  - "StatusBadge accepts CampaignStatus and renders icon + color-coded badge"

requirements-completed: [UI-03, UI-11, UI-13]

# Metrics
duration: 13min
completed: 2026-03-29
---

# Phase 08 Plan 02: App Shell, Layout, and Campaign List Summary

**Fixed sidebar layout with campaign history, health-indicator header, status badges for 4 states, and responsive CampaignList page with loading/error/empty state handling**

## Performance

- **Duration:** 13 min
- **Started:** 2026-03-29T21:11:02Z
- **Completed:** 2026-03-29T21:24:00Z
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments

- Two-column layout shell: fixed w-72 sidebar with branding, New Campaign CTA, and ScrollArea campaign history list; main area with header and scrollable Outlet content
- Sidebar uses useCampaigns() hook, highlights active campaign from route params, shows status badges and relative dates for each entry
- Header with page title and system health indicator: pulsing dot (green/amber/red) with tooltip breakdown of TRIBE, MiroFish, and Database statuses via useHealth()
- StatusBadge component with config-map pattern: 4 states (pending/running/completed/failed) each with icon (Clock/Play/CheckCircle2/XCircle) and OKLCH color classes
- Common state components: CampaignListSkeleton (6-card grid), CampaignDetailSkeleton, SidebarSkeleton, ErrorState with retry, EmptyState with icon and optional CTA
- CampaignList page: responsive 1/2/3 column card grid with prediction question, demographic label, status badge, relative date, iteration count, and status-aware hover ring colors
- Full routing: / redirects to /campaigns, /campaigns shows list, /campaigns/new and /campaigns/:id render placeholders inside layout

## Task Commits

Each task was committed atomically:

1. **Task 1: Build layout shell (sidebar, header, routing) and common state components** - `8e57813` (feat)
2. **Task 2: Build CampaignList page with status badges, filtering, and polished data display** - `522dfb5` (feat)

## Files Created/Modified

- `ui/src/components/layout/app-layout.tsx` - Two-column layout shell with Sidebar + Header + Outlet
- `ui/src/components/layout/sidebar.tsx` - Fixed sidebar with branding, new campaign button, campaign history list
- `ui/src/components/layout/header.tsx` - Header bar with page title and pulsing health indicator
- `ui/src/components/common/status-badge.tsx` - Color-coded status badge with lucide icons for 4 campaign states
- `ui/src/components/common/loading-skeleton.tsx` - CampaignListSkeleton, CampaignDetailSkeleton, SidebarSkeleton
- `ui/src/components/common/error-state.tsx` - Error display with AlertTriangle icon and retry button
- `ui/src/components/common/empty-state.tsx` - Empty state with configurable icon, title, description, and action
- `ui/src/pages/campaign-list.tsx` - Campaign list page with responsive card grid and all state handling
- `ui/src/App.tsx` - Updated with full routing: redirect, layout route, campaigns, new, detail

## Decisions Made

- Layout uses React Router Outlet pattern: AppLayout is a layout route that wraps all /campaigns/* routes, rendering children via `<Outlet />`.
- Sidebar highlights active campaign by matching `useParams().id` to campaign.id, using sidebar-accent background color.
- Health indicator uses pulsing ping animation on the dot, with a Tooltip showing per-service status breakdown.
- StatusBadge uses a config-map pattern where each CampaignStatus maps to an icon component, label string, and OKLCH-based Tailwind classes.

## Deviations from Plan

None -- plan executed exactly as written.

## Known Stubs

- `ui/src/App.tsx`: CampaignNewPlaceholder and CampaignDetailPlaceholder are inline placeholder components. These are intentional stubs that will be replaced by Plan 08-03 (campaign creation form) and Plan 08-05 (campaign detail view) respectively.

## Self-Check: PASSED
