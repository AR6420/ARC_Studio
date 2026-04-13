#!/usr/bin/env bash
# Restart the TRIBE v2 scorer service after CUDA context corruption.
# Usage: bash scripts/restart_tribe.sh

set -euo pipefail

TRIBE_PORT=${TRIBE_PORT:-8001}

echo "[restart_tribe] Stopping TRIBE scorer on port $TRIBE_PORT..."

# Find and kill the TRIBE scorer process
PIDS=$(lsof -ti:$TRIBE_PORT 2>/dev/null || true)
if [ -n "$PIDS" ]; then
    echo "[restart_tribe] Killing PIDs: $PIDS"
    kill $PIDS 2>/dev/null || true
    sleep 2
    # Force kill if still running
    kill -9 $PIDS 2>/dev/null || true
fi

echo "[restart_tribe] Waiting for port to be free..."
for i in $(seq 1 10); do
    if ! lsof -ti:$TRIBE_PORT &>/dev/null; then
        break
    fi
    sleep 1
done

echo "[restart_tribe] Starting TRIBE scorer..."
cd "$(dirname "$0")/.."
bash tribe_scorer/start.sh &

echo "[restart_tribe] Waiting for TRIBE scorer to become healthy..."
for i in $(seq 1 60); do
    if curl -sf "http://localhost:$TRIBE_PORT/api/health" >/dev/null 2>&1; then
        echo "[restart_tribe] TRIBE scorer is healthy."
        exit 0
    fi
    sleep 2
done

echo "[restart_tribe] ERROR: TRIBE scorer did not become healthy within 120s."
exit 1
