#!/usr/bin/env bash
# Delete old MiroFish simulation data from Neo4j.
# Usage: bash scripts/cleanup_neo4j.sh [--days N] [--dry-run]
#
# Deletes simulation nodes (agents, ontology, conversations) older than N days.
# Default: 30 days. Use --days 0 to delete all simulation data.

set -euo pipefail

DAYS=30
DRY_RUN=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --days) DAYS="$2"; shift 2 ;;
        --dry-run) DRY_RUN=true; shift ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

NEO4J_URL="${NEO4J_URL:-http://localhost:7474}"
NEO4J_USER="${NEO4J_USER:-neo4j}"
NEO4J_PASSWORD="${NEO4J_PASSWORD:?Set NEO4J_PASSWORD env var}"

AUTH=$(echo -n "${NEO4J_USER}:${NEO4J_PASSWORD}" | base64)

echo "=== Neo4j Cleanup ==="
echo "Deleting simulation data older than $DAYS days"
echo "URL: $NEO4J_URL"
echo ""

# Count before
BEFORE=$(curl -sf -X POST "${NEO4J_URL}/db/neo4j/tx/commit" \
  -H "Authorization: Basic ${AUTH}" \
  -H "Content-Type: application/json" \
  -d '{"statements": [{"statement": "MATCH (n) RETURN count(n) as count"}]}') || {
    echo "ERROR: Could not connect to Neo4j at ${NEO4J_URL}"
    echo "Is Neo4j running? Try: docker compose up -d neo4j"
    exit 1
}

if command -v jq &>/dev/null; then
    BEFORE_COUNT=$(echo "$BEFORE" | jq -r '.results[0].data[0].row[0] // "N/A"')
    echo "Nodes before cleanup: $BEFORE_COUNT"
fi

if [ "$DRY_RUN" = true ]; then
    echo "[DRY RUN] Would delete simulation data older than $DAYS days"
    exit 0
fi

# Delete old simulation nodes and their relationships
# MiroFish creates nodes with labels like Agent, Post, Action, etc.
if [ "$DAYS" -eq 0 ]; then
    CYPHER="MATCH (n) WHERE n:Agent OR n:Post OR n:Action OR n:Message OR n:SimulationRun DETACH DELETE n"
else
    CYPHER="MATCH (n) WHERE (n:Agent OR n:Post OR n:Action OR n:Message OR n:SimulationRun) AND n.created_at < datetime() - duration('P${DAYS}D') DETACH DELETE n"
fi

curl -sf -X POST "${NEO4J_URL}/db/neo4j/tx/commit" \
  -H "Authorization: Basic ${AUTH}" \
  -H "Content-Type: application/json" \
  -d "{\"statements\": [{\"statement\": \"$CYPHER\"}]}" > /dev/null

# Count after
AFTER=$(curl -sf -X POST "${NEO4J_URL}/db/neo4j/tx/commit" \
  -H "Authorization: Basic ${AUTH}" \
  -H "Content-Type: application/json" \
  -d '{"statements": [{"statement": "MATCH (n) RETURN count(n) as count"}]}')

if command -v jq &>/dev/null; then
    AFTER_COUNT=$(echo "$AFTER" | jq -r '.results[0].data[0].row[0] // "N/A"')
    echo "Nodes after cleanup:  $AFTER_COUNT"
    if [ "$BEFORE_COUNT" != "N/A" ] && [ "$AFTER_COUNT" != "N/A" ]; then
        echo "Nodes deleted:        $((BEFORE_COUNT - AFTER_COUNT))"
    fi
fi

echo ""
echo "=== Cleanup Complete ==="
