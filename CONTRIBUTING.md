# Contributing to A.R.C Studio

Thanks for your interest in contributing. This guide covers how to set up a development environment, run tests, and submit changes.

## Development Setup

### Prerequisites

- Python 3.11+ (for TRIBE v2 scorer)
- Python 3.13+ (for orchestrator)
- Node.js 18+
- Docker Desktop
- Git (with submodule support)

### Clone and install

```bash
git clone --recursive https://github.com/AR6420/ARC_Studio.git
cd ARC_Studio
cp .env.example .env
```

**Orchestrator** (system Python):
```bash
pip install -r orchestrator/requirements.txt
```

**TRIBE v2 scorer** (Python 3.11 venv):
```bash
py -3.11 -m venv tribe_scorer/.venv
tribe_scorer/.venv/Scripts/pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
tribe_scorer/.venv/Scripts/pip install -r tribe_scorer/requirements.txt
tribe_scorer/.venv/Scripts/pip install -e tribe_scorer/vendor/tribev2
```

**UI**:
```bash
cd ui && npm install
```

**Docker services** (Neo4j, LiteLLM, MiroFish):
```bash
docker compose up -d
```

## Running Tests

All backend tests are in `orchestrator/tests/` and use pytest with `asyncio_mode=auto`.

```bash
# Run the full suite (194 tests)
pytest

# Run a single test file
pytest orchestrator/tests/test_campaign_runner.py

# Run a specific test
pytest orchestrator/tests/test_campaign_runner.py::test_function_name -v

# Run with stdout output
pytest -s orchestrator/tests/test_composite_scorer.py
```

External services (TRIBE v2, MiroFish, Claude API) are mocked in tests. You don't need any running services to run the test suite.

**UI linting**:
```bash
cd ui && npm run lint
```

## Code Style

- **Python**: Follow existing patterns in the codebase. Use type hints. Pydantic models for data validation. Async throughout the orchestrator.
- **TypeScript**: ESLint is configured in the UI project. Run `npm run lint` before submitting.
- **Commits**: Use conventional commit messages (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`).

## Pull Request Process

1. Fork the repository and create a branch from `main`.
2. Make your changes. Add or update tests if applicable.
3. Run `pytest` and ensure all tests pass.
4. Run `cd ui && npm run lint` if you touched frontend code.
5. Open a PR against `main` with a clear description of what changed and why.

For larger changes, open an issue first to discuss the approach.

## Areas Where Help Is Appreciated

- New demographic profiles (`orchestrator/prompts/demographic_profiles.py`)
- Composite scoring formula improvements (`orchestrator/engine/composite_scorer.py`)
- UI polish and accessibility
- Documentation and examples
- Test coverage expansion
