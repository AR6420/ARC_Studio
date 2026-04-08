#!/bin/bash
# Reads the current OAuth token from Claude Code credentials and updates .env
# Then optionally recreates the LiteLLM container to pick up the new key.
#
# Usage:
#   ./scripts/refresh-env.sh            # Update .env only
#   ./scripts/refresh-env.sh --restart   # Update .env and recreate LiteLLM container

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$SCRIPT_DIR/../.env"
RESTART_LITELLM=false

if [[ "${1:-}" == "--restart" ]]; then
    RESTART_LITELLM=true
fi

# Extract accessToken using Python (handles both Unix and Windows paths)
TOKEN=$(python -c "
import json, os, sys
path = os.path.expanduser('~/.claude/.credentials.json')
try:
    with open(path) as f:
        d = json.load(f)
    token = d.get('claudeAiOauth', {}).get('accessToken', '')
    if not token:
        print('', end='')
        sys.exit(1)
    print(token, end='')
except Exception as e:
    print('', end='')
    sys.exit(1)
" 2>/dev/null)

if [ -z "$TOKEN" ]; then
    echo "Error: Could not extract accessToken from ~/.claude/.credentials.json"
    exit 1
fi

# Update ANTHROPIC_API_KEY in .env using Python (cross-platform, no sed issues)
python -c "
import sys
env_file = sys.argv[1]
token = sys.argv[2]
with open(env_file) as f:
    lines = f.readlines()
found = False
with open(env_file, 'w') as f:
    for line in lines:
        if line.startswith('ANTHROPIC_API_KEY='):
            f.write(f'ANTHROPIC_API_KEY={token}\n')
            found = True
        else:
            f.write(line)
    if not found:
        f.write(f'ANTHROPIC_API_KEY={token}\n')
" "$ENV_FILE" "$TOKEN"

echo "Updated ANTHROPIC_API_KEY in .env"

if [ "$RESTART_LITELLM" = true ]; then
    echo "Recreating LiteLLM container to pick up new key..."
    cd "$SCRIPT_DIR/.."
    docker compose up -d litellm 2>&1
    echo "LiteLLM container recreated. Waiting for health check..."
    sleep 10
    HEALTH=$(curl -s http://localhost:4000/health 2>/dev/null || echo "FAILED")
    echo "LiteLLM health: $HEALTH"
fi
