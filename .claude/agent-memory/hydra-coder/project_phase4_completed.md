---
name: Phase 4 — Claude Client and Prompt Templates (completed)
description: What was built in Phase 4 and key decisions made
type: project
---

Phase 4 created the Claude API client and all prompt templates for the orchestrator. All files are at orchestrator/ in the repo root.

**Files created:**
- orchestrator/__init__.py (empty)
- orchestrator/clients/__init__.py (empty)
- orchestrator/prompts/__init__.py (empty)
- orchestrator/clients/claude_client.py — AsyncAnthropic wrapper
- orchestrator/config.py — Pydantic BaseSettings loading from repo-root .env
- orchestrator/prompts/variant_generation.py — Haiku prompt for N-variant generation
- orchestrator/prompts/result_analysis.py — Opus prompt for cross-system analysis
- orchestrator/prompts/report_verdict.py — Opus prompt for Layer 1 (plain-English verdict)
- orchestrator/prompts/report_psychology.py — Opus prompts for Layer 4 (general + technical)
- orchestrator/prompts/demographic_profiles.py — 6 preset demographic configs
- orchestrator/requirements.txt

**Key decisions:**
- Credential loading: ANTHROPIC_API_KEY env var > claudeAiOauth.accessToken in C:/Users/adars/.claude/.credentials.json
- Retry: exponential backoff (1s, 2s, 4s), max 3 retries, for 429 and 5xx status codes
- 401 handling: re-reads credentials file once (OAuth token rotation), then retries without counting toward backoff limit
- JSON mode: augments user prompt with JSON-only instruction, retries once on parse failure
- JSON extraction: handles markdown fences, bare JSON, and first-{}-block patterns
- config.py: Settings is a module singleton (`settings = Settings()`); env_file path is resolved relative to __file__ so it works from any cwd
- DEMOGRAPHIC_PROFILES is an annotated assignment (`dict[str, Any]`) — AST simple-assign checks will miss it

**Why:** Phase 1 POC constraints — dynamic credential loading needed because OAuth token rotates per Claude session.
