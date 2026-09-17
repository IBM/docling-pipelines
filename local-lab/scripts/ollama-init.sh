#!/bin/sh
set -e

# ---------------------------------------------------------------------------
# local-lab init script — run once after compose is up, from local-lab/
# Handles Ollama model pull (MinIO seeding is done by the minio-init container)
# Requires: curl
# Usage: ./scripts/ollama-init.sh
# ---------------------------------------------------------------------------

OLLAMA_HOST="${OLLAMA_HOST:-http://localhost:11434}"

# Wait for Ollama to be ready.
echo "Waiting for Ollama at $OLLAMA_HOST..."
i=0
until curl -sf "$OLLAMA_HOST" > /dev/null 2>&1; do
  i=$((i+1))
  if [ "$i" -gt 30 ]; then echo "Ollama did not become ready. Exiting."; exit 1; fi
  sleep 2
done
echo "Ollama is ready."

# Pull the embedding model used by the pipeline.
echo "Pulling nomic-embed-text..."
curl -sf -X POST "$OLLAMA_HOST/api/pull" -d '{"name":"nomic-embed-text:v1.5"}' | tail -1
echo "Model ready."

echo ""
echo "Init complete. Local lab is ready."
