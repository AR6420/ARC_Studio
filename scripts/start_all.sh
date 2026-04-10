#!/usr/bin/env bash
# A.R.C Studio — Start all services
# Usage: bash scripts/start_all.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

echo "=== A.R.C Studio Startup ==="

# Step 1: Docker Compose (Neo4j, LiteLLM, MiroFish)
echo "[1/4] Starting Docker services..."
docker compose up -d 2>&1
echo "  Waiting for Docker health checks..."
# Wait up to 60s for Neo4j and LiteLLM to be healthy
for i in $(seq 1 30); do
    healthy=$(docker compose ps --format json 2>/dev/null | grep -c '"healthy"' || echo 0)
    if [ "$healthy" -ge 2 ]; then
        echo "  Docker services healthy."
        break
    fi
    sleep 2
done

# Step 2: TRIBE v2 scorer
echo "[2/4] Starting TRIBE v2 scorer..."
bash tribe_scorer/start.sh &
TRIBE_PID=$!
echo "  Waiting for TRIBE v2 (model load takes 60-90s)..."
for i in $(seq 1 60); do
    if curl -s --max-time 2 http://127.0.0.1:8001/api/health > /dev/null 2>&1; then
        echo "  TRIBE v2 scorer ready."
        break
    fi
    if [ "$i" -eq 60 ]; then
        echo "  WARNING: TRIBE v2 did not become healthy in 120s. Check logs."
    fi
    sleep 2
done

# Step 3: Orchestrator API
echo "[3/4] Starting Orchestrator API..."
python -m uvicorn orchestrator.api:create_app --factory --port 8000 &
ORCH_PID=$!
sleep 3
if curl -s --max-time 5 http://127.0.0.1:8000/api/health > /dev/null 2>&1; then
    echo "  Orchestrator ready."
else
    echo "  WARNING: Orchestrator did not start. Check port 8000."
fi

# Step 4: UI dev server
echo "[4/4] Starting UI dev server..."
cd ui && npm run dev &
UI_PID=$!
cd "$PROJECT_ROOT"
sleep 3
echo "  UI starting on http://localhost:5173"

# Final health check
echo ""
echo "=== Health Check ==="
curl -s http://127.0.0.1:8000/api/health 2>/dev/null | python -c "
import sys, json
try:
    d = json.load(sys.stdin)
    for k, v in d.items():
        status = v.get('status', v) if isinstance(v, dict) else v
        print(f'  {k}: {status}')
except:
    print('  Could not reach orchestrator')
" 2>/dev/null || echo "  Orchestrator not responding"

echo ""
echo "=== Services Started ==="
echo "  Orchestrator: http://localhost:8000"
echo "  TRIBE v2:     http://localhost:8001"
echo "  MiroFish:     http://localhost:5001"
echo "  UI:           http://localhost:5173"
echo ""
echo "Press Ctrl+C to stop all services."
wait
