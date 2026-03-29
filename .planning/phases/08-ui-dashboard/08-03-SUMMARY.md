---
phase: 08-ui-dashboard
plan: 03
subsystem: ui
tags: [react, typescript, campaign-form, demographic-selector, sliders, time-estimate, dark-theme]

# Dependency graph
requires:
  - phase: 08-ui-dashboard
    plan: 01
    provides: Vite scaffold, TypeScript types, API client, React Query hooks, shadcn/ui components
provides:
  - NewCampaign page with single scrollable form (D-04)
  - DemographicSelector with 6 preset cards and custom option
  - ConfigPanel with agent count and iteration sliders plus optional thresholds
  - TimeEstimate component with live API-driven duration display
  - Campaign creation flow with validation, mutation, and navigation
affects: [08-04, 08-05, 08-06]

# Tech tracking
tech-stack:
  added: []
  patterns: [section-numbered-form-layout, preset-card-grid-selector, slider-with-live-value, collapsible-thresholds, sonner-toast-notifications]

key-files:
  created:
    - ui/src/pages/new-campaign.tsx
    - ui/src/components/campaign/campaign-form.tsx
    - ui/src/components/campaign/demographic-selector.tsx
    - ui/src/components/campaign/config-panel.tsx
    - ui/src/components/campaign/time-estimate.tsx
  modified:
    - ui/src/App.tsx
    - ui/src/main.tsx
    - ui/src/components/ui/sonner.tsx

key-decisions:
  - "Demographic presets inlined as static data (not fetched from API) to ensure form is usable without backend"
  - "Sonner Toaster fixed to use hardcoded dark theme instead of next-themes dependency"
  - "Section numbering in form for visual hierarchy and premium feel (D-07)"
  - "Slider onValueChange handles base-ui union type (number | readonly number[]) explicitly"

patterns-established:
  - "SectionHeading sub-component with numbered badges for form section organization"
  - "CharCount indicator with min/max warning colors using score theme variables"
  - "Demographic preset cards with selection dot indicator and primary ring on active"
  - "Collapsible threshold panel with inline toggle and inverted metric labeling"

requirements-completed: [UI-04]

# Metrics
duration: 19min
completed: 2026-03-29
---

# Phase 08 Plan 03: Campaign Creation Form Summary

**Single-page campaign creation form with 6 demographic preset cards, dual configuration sliders, live time estimate, and validation-gated submission that creates and launches campaigns via the API**

## Performance

- **Duration:** 19 min
- **Started:** 2026-03-29T21:18:24Z
- **Completed:** 2026-03-29T21:37:00Z
- **Tasks:** 1
- **Files modified:** 8

## Accomplishments
- Complete NewCampaign page as a single scrollable form (per D-04) with 5 visually distinct numbered sections
- DemographicSelector component with 6 preset cards in responsive grid (2x3 on large screens), each with distinct lucide icons, labels, truncated descriptions, and a selection indicator dot with primary ring
- Custom demographic option with reveal textarea for freeform audience profiles
- ConfigPanel with two sliders (agent count 20-200 step 10, max iterations 1-10 step 1) showing live values and min/max labels
- Collapsible optional thresholds section with 7 composite score dimension inputs, pre-filled defaults, and inverted metric labeling for backlash_risk and polarization_index
- TimeEstimate component using useTimeEstimate hook with loading skeleton, error state, and "Fast" badge for short estimates
- Form validation: seed content >= 100 chars with character counter and amber warning, prediction question >= 10 chars
- Submit button with loading spinner during mutation, success navigation to /campaigns/:id, error toasts via Sonner
- Sonner Toaster added to main.tsx, fixed to use hardcoded dark theme (removed next-themes dependency)
- Route /campaigns/new added to App.tsx

## Task Commits

Each task was committed atomically:

1. **Task 1: Build campaign creation form with demographic selector, config panel, and time estimate** - `11a80fd` (feat)

## Files Created/Modified
- `ui/src/pages/new-campaign.tsx` - NewCampaign page wrapper with back link, title, and CampaignForm (37 lines)
- `ui/src/components/campaign/campaign-form.tsx` - Full campaign form with 5 sections, validation, and submission (298 lines)
- `ui/src/components/campaign/demographic-selector.tsx` - 6 preset cards with icons + custom option (221 lines)
- `ui/src/components/campaign/config-panel.tsx` - Agent count and iterations sliders + collapsible thresholds (196 lines)
- `ui/src/components/campaign/time-estimate.tsx` - Live time estimate display with loading/error states (73 lines)
- `ui/src/App.tsx` - Added /campaigns/new route
- `ui/src/main.tsx` - Added Toaster component for toast notifications
- `ui/src/components/ui/sonner.tsx` - Fixed to use hardcoded dark theme instead of next-themes

## Decisions Made
- Demographic presets are inlined as static data rather than fetched from the API via getDemographics. This ensures the form is usable even when the backend is offline, and the 6 presets are stable data from orchestrator/prompts/demographic_profiles.py.
- Sonner Toaster component was fixed to remove its dependency on next-themes (which is a Next.js library, not applicable to this Vite project). The theme is hardcoded to "dark" since this is a dark-first application.
- Form sections use numbered badges (1-5) for visual hierarchy, contributing to the premium feel required by D-07.
- The base-ui Slider component's onValueChange callback receives `number | readonly number[]`, so the handler explicitly checks `Array.isArray` before extracting the value.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed Sonner toaster next-themes dependency**
- **Found during:** Task 1 (build verification)
- **Issue:** The shadcn-generated sonner.tsx imported `useTheme` from `next-themes`, which is a Next.js library not available in this Vite + React project. This would cause a runtime crash when trying to show toast notifications.
- **Fix:** Removed the next-themes import and hardcoded the theme to "dark" (matching the dark-first design decision D-02)
- **Files modified:** ui/src/components/ui/sonner.tsx
- **Committed in:** 11a80fd

**2. [Rule 2 - Missing functionality] Added Toaster component to app root**
- **Found during:** Task 1 (toast notifications require Toaster in DOM)
- **Issue:** The Sonner Toaster component was installed as a shadcn/ui component but never rendered in the application tree. Without it, `toast.error()` and `toast.success()` calls in the form would silently fail.
- **Fix:** Added `<Toaster position="bottom-right" />` to main.tsx inside the provider tree
- **Files modified:** ui/src/main.tsx
- **Committed in:** 11a80fd

**3. [Rule 1 - Bug] Fixed Slider onValueChange type mismatch**
- **Found during:** Task 1 (TypeScript compilation)
- **Issue:** base-ui Slider's onValueChange passes `number | readonly number[]` but the initial code assumed `number[]`. TypeScript TS2322 error.
- **Fix:** Changed handler to check `Array.isArray(val)` before extracting value
- **Files modified:** ui/src/components/campaign/config-panel.tsx
- **Committed in:** 11a80fd

---

**Total deviations:** 3 auto-fixed (2 bugs, 1 missing functionality)
**Impact on plan:** All fixes were necessary for the form to compile and function correctly. No scope creep.

## Issues Encountered
None beyond the auto-fixed deviations above.

## User Setup Required
None - all components use existing API layer from Plan 08-01.

## Known Stubs
None - all components contain complete implementations. The form submits to a real API endpoint and navigates on success. Demographic presets contain real data matching the backend. Thresholds default to meaningful values from the plan specification.

## Next Phase Readiness
- Campaign creation form is complete and available at /campaigns/new
- All components export cleanly for use by subsequent plans
- The form navigates to /campaigns/:id on success (campaign detail page built in Plan 08-04)
- Toast notifications working via Sonner for all future UI error/success states

## Self-Check: PASSED
