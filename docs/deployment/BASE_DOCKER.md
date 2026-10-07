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
docker compose -f docker/docker-compose.yml exec ollama ollama pull nomic-embed-text

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

## Run the default flow from the UI

1. Start the stack from the repository root:

   ```bash
   docker compose -f docker/docker-compose.yml up -d --no-build
   ```

2. Open `http://localhost:8080/ui` in your browser to access the UI home page.
3. Click **Start** on the **Get started with sample data** tile. The flow opens automatically in the canvas.
4. Click **Run flow** in the canvas toolbar to execute the default flow and view its progress and results.
