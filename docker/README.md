```bash
# Set before running Compose commands (replace with your own strong password)
export OPENSEARCH_PASSWORD='DocpipeLocal9!Secure'

# Build
docker compose -f docker/docker-compose.yml build

# Pull
docker compose -f docker/docker-compose.yml pull

# Run without building
docker compose -f docker/docker-compose.yml up -d --no-build

# Tail API container logs
docker compose -f docker/docker-compose.yml logs -f --tail=100 docpipe

# Download the embedding model for the end-to-end flow
docker compose -f docker/docker-compose.yml exec ollama ollama pull nomic-embed-text:v1.5

# Upload the flow (run from the repository root)
curl --fail-with-body -sS \
  -X POST http://localhost:8080/api/v1/flows \
  -H 'Content-Type: application/json' \
  --data-binary @sample_flows/quickstart/docker_e2e_ollama_opensearch.json

# Run the flow (replace PASTE_FLOW_ID with the ID returned by upload)
curl --fail-with-body -sS \
  -X POST http://localhost:8080/api/v1/job_runs \
  -H 'Content-Type: application/json' \
  -d '{"entity":{"job":{"asset_ref":"PASTE_FLOW_ID"}}}'

# Bring down the stack (retain named data volumes)
docker compose -f docker/docker-compose.yml down
```
