<!-- GSD:project-start source:PROJECT.md -->
## Project

**Nexus Sim**

Nexus Sim is a content optimization platform that combines neural response prediction (TRIBE v2), multi-agent social simulation (MiroFish-Offline), and LLM-driven iterative optimization (Claude Opus) into a single feedback loop. A user submits content (product launch, PSA, policy draft, etc.), and the system generates variants, scores them neurally, simulates social propagation, analyzes cross-system results, and iterates until thresholds are met. Phase 1 POC — single-user, local machine, non-commercial.

**Core Value:** The iterative feedback loop between neural scoring (TRIBE v2) and social simulation (MiroFish) produces measurably better content than single-pass generation, with cross-system reasoning that explains WHY certain neural patterns lead to specific social outcomes.

### Constraints

- **Hardware**: Single RTX 5070 Ti GPU shared between TRIBE v2 and Ollama embeddings
- **API**: Claude API rate limits — Haiku batched, Opus sequential (4-8 calls/campaign)
- **Dependency**: TRIBE v2 requires HuggingFace LLaMA 3.2-3B gated model approval
- **Dependency**: MiroFish-Offline is a fork/submodule — minimal modifications to enable upstream merges
- **Performance**: Full campaign (40 agents, 4 iterations) must complete in <= 20 minutes
- **Scope**: Phase 1 POC only — no auth, no HTTPS, no multi-user
<!-- GSD:project-end -->

<!-- GSD:stack-start source:STACK.md -->
## Technology Stack

Technology stack not yet documented. Will populate after codebase mapping or first phase.
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd:quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd:debug` for investigation and bug fixing
- `/gsd:execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd:profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
