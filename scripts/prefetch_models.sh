#!/usr/bin/env bash
# Pre-pull Qwen weights into the HF cache before starting vLLM.
#
# Designed to run on the AMD Cloud MI300X node during Phase 3 of the
# hackathon migration. Pulls all four model variants (primary +
# fallback, both tiers) so flipping between them is a one-env-var
# change with no extra download time.
#
# Usage:
#   HF_TOKEN=hf_xxxxx bash scripts/prefetch_models.sh
#   HF_TOKEN=hf_xxxxx PREFETCH_FALLBACK=0 bash scripts/prefetch_models.sh   # skip Qwen3
#
# Idempotent: huggingface-cli skips files already present in the cache.
# Total cost on first run: ~120-160 GB across the 4 models.

set -euo pipefail

# ── Config ───────────────────────────────────────────────────────────────
PRIMARY_ORCHESTRATOR="${VLLM_ORCHESTRATOR_MODEL:-Qwen/Qwen3.5-27B}"
PRIMARY_AGENT="${VLLM_AGENT_MODEL:-Qwen/Qwen3.5-9B}"
FALLBACK_ORCHESTRATOR="Qwen/Qwen3-32B"
FALLBACK_AGENT="Qwen/Qwen3-8B"
PREFETCH_FALLBACK="${PREFETCH_FALLBACK:-1}"
HF_CACHE_DIR="${HF_HOME:-$HOME/.cache/huggingface}"

# ── Pre-flight ───────────────────────────────────────────────────────────
if ! command -v huggingface-cli >/dev/null 2>&1; then
    echo "ERROR: huggingface-cli not on PATH. Install with: pip install -U 'huggingface_hub[cli]'" >&2
    exit 1
fi

if [[ -z "${HF_TOKEN:-}" ]]; then
    echo "ERROR: HF_TOKEN env var is required (Qwen weights are gated for some accounts)." >&2
    echo "       Set it in .env.hackathon and source it before running this script." >&2
    exit 1
fi

# huggingface-cli reads HF_TOKEN from env directly (since hub 0.20+).
export HF_TOKEN

mkdir -p "$HF_CACHE_DIR"

# ── Helpers ──────────────────────────────────────────────────────────────
fetch() {
    local repo="$1"
    local label="$2"
    echo
    echo "── ${label}: ${repo} ────────────────────────────────────────────"
    local t0
    t0=$(date +%s)
    # --resume-download is on by default in modern hub CLI; --local-dir-use-symlinks=False
    # keeps the cache structure tidy. Suppress progress noise but keep errors.
    if huggingface-cli download "${repo}" \
        --repo-type model \
        --quiet 2>&1 | tail -n 5; then
        local elapsed=$(( $(date +%s) - t0 ))
        echo "${label}: done in ${elapsed}s"
    else
        echo "ERROR: download failed for ${repo}" >&2
        return 1
    fi
}

# ── Pull ────────────────────────────────────────────────────────────────
echo "Prefetching Qwen weights to ${HF_CACHE_DIR}"
echo "Primary pair  : agent=${PRIMARY_AGENT}, orch=${PRIMARY_ORCHESTRATOR}"
if [[ "$PREFETCH_FALLBACK" == "1" ]]; then
    echo "Fallback pair : agent=${FALLBACK_AGENT}, orch=${FALLBACK_ORCHESTRATOR}"
else
    echo "Fallback pair : SKIPPED (PREFETCH_FALLBACK=0)"
fi

GRAND_T0=$(date +%s)

fetch "$PRIMARY_AGENT"        "primary  agent"
fetch "$PRIMARY_ORCHESTRATOR" "primary  orchestrator"

if [[ "$PREFETCH_FALLBACK" == "1" ]]; then
    fetch "$FALLBACK_AGENT"        "fallback agent"
    fetch "$FALLBACK_ORCHESTRATOR" "fallback orchestrator"
fi

GRAND_ELAPSED=$(( $(date +%s) - GRAND_T0 ))

# ── Report ──────────────────────────────────────────────────────────────
echo
echo "── Summary ──────────────────────────────────────────────────────────"
echo "Total elapsed: ${GRAND_ELAPSED}s ($((GRAND_ELAPSED / 60))m)"
if command -v du >/dev/null 2>&1; then
    SIZE_HUMAN=$(du -sh "$HF_CACHE_DIR" 2>/dev/null | awk '{print $1}')
    echo "HF cache size: ${SIZE_HUMAN}  (at ${HF_CACHE_DIR})"
fi
if command -v df >/dev/null 2>&1; then
    AVAIL_HUMAN=$(df -h "$HF_CACHE_DIR" | awk 'NR==2 {print $4}')
    echo "Disk free   : ${AVAIL_HUMAN} on the cache filesystem"
fi
echo
echo "Done. vLLM can now start without on-demand model downloads."
