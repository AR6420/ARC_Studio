#!/usr/bin/env bash
# Check Neo4j heap usage and graph size.
# Usage: bash scripts/neo4j_heap_check.sh
#
# Requires: curl, jq (optional for pretty output)

set -euo pipefail

NEO4J_URL="${NEO4J_URL:-http://localhost:7474}"
NEO4J_USER="${NEO4J_USER:-neo4j}"
NEO4J_PASSWORD="${NEO4J_PASSWORD:?Set NEO4J_PASSWORD env var}"

AUTH=$(echo -n "${NEO4J_USER}:${NEO4J_PASSWORD}" | base64)

echo "=== Neo4j Heap & Graph Status ==="
echo "URL: $NEO4J_URL"
echo ""

# Query node and relationship counts
RESPONSE=$(curl -sf -X POST "${NEO4J_URL}/db/neo4j/tx/commit" \
  -H "Authorization: Basic ${AUTH}" \
  -H "Content-Type: application/json" \
  -d '{
    "statements": [
      {"statement": "MATCH (n) RETURN count(n) as node_count"},
      {"statement": "MATCH ()-[r]->() RETURN count(r) as rel_count"},
      {"statement": "CALL dbms.queryJmx(\"java.lang:type=Memory\") YIELD attributes RETURN attributes.HeapMemoryUsage.value.used as heap_used, attributes.HeapMemoryUsage.value.max as heap_max"}
    ]
  }') || {
    echo "ERROR: Could not connect to Neo4j at ${NEO4J_URL}"
    echo "Is Neo4j running? Try: docker compose up -d neo4j"
    exit 1
}

if command -v jq &>/dev/null; then
    NODE_COUNT=$(echo "$RESPONSE" | jq -r '.results[0].data[0].row[0] // "N/A"')
    REL_COUNT=$(echo "$RESPONSE" | jq -r '.results[1].data[0].row[0] // "N/A"')
    HEAP_USED=$(echo "$RESPONSE" | jq -r '.results[2].data[0].row[0] // "N/A"')
    HEAP_MAX=$(echo "$RESPONSE" | jq -r '.results[2].data[0].row[1] // "N/A"')

    echo "Nodes:          $NODE_COUNT"
    echo "Relationships:  $REL_COUNT"

    if [ "$HEAP_USED" != "N/A" ] && [ "$HEAP_MAX" != "N/A" ]; then
        HEAP_USED_MB=$((HEAP_USED / 1048576))
        HEAP_MAX_MB=$((HEAP_MAX / 1048576))
        HEAP_PCT=$((HEAP_USED * 100 / HEAP_MAX))
        echo "Heap Used:      ${HEAP_USED_MB} MB / ${HEAP_MAX_MB} MB (${HEAP_PCT}%)"

        if [ "$HEAP_PCT" -gt 70 ]; then
            echo ""
            echo "WARNING: Heap usage >70%. Consider running: scripts/cleanup_neo4j.sh"
        fi
    else
        echo "Heap:           (JMX query not supported -- check Neo4j edition)"
        echo "Heap Max:       2048 MB (from docker-compose config)"
    fi
else
    echo "Raw response (install jq for formatted output):"
    echo "$RESPONSE"
fi

echo ""
echo "=== Done ==="
