#!/bin/bash
# Reads the current OAuth token from Claude Code credentials and updates .env
# Run this before docker compose up to ensure fresh API key

CRED_FILE="$HOME/.claude/.credentials.json"
ENV_FILE="$(dirname "$0")/../.env"

if [ ! -f "$CRED_FILE" ]; then
    echo "Error: $CRED_FILE not found"
    exit 1
fi

# Extract accessToken from credentials JSON
TOKEN=$(python -c "import json; f=open('$CRED_FILE'); d=json.load(f); print(d['claudeAiOauth']['accessToken'])" 2>/dev/null)

if [ -z "$TOKEN" ]; then
    echo "Error: Could not extract accessToken from credentials"
    exit 1
fi

# Update ANTHROPIC_API_KEY in .env
if grep -q "^ANTHROPIC_API_KEY=" "$ENV_FILE"; then
    sed -i "s|^ANTHROPIC_API_KEY=.*|ANTHROPIC_API_KEY=$TOKEN|" "$ENV_FILE"
else
    echo "ANTHROPIC_API_KEY=$TOKEN" >> "$ENV_FILE"
fi

echo "Updated ANTHROPIC_API_KEY in .env (token: ${TOKEN:0:20}...)"
