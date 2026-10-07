# Run Docling Pipelines with Docker Compose

Run from the repository root.

## Stage 0: Set the OpenSearch password

Compose requires `OPENSEARCH_PASSWORD`. Run this in each terminal before using Compose:

```bash
export OPENSEARCH_PASSWORD='DocpipeLocal9!Secure'
```

## Stage 1: Build the images

```bash
docker compose -f docker/docker-compose.yml build
```

## Stage 2: Run the API

```bash
docker compose -f docker/docker-compose.yml up -d --no-build
```

Check API health:

```bash
curl --fail http://localhost:8080/health
```

API docs: `http://localhost:8080/api/v1/docs`.

### API logs (optional)

Log commands stream until you press `Ctrl+C`.

```bash
docker compose -f docker/docker-compose.yml logs -f --tail=100 docpipe
```

### Run a sample flow through the API (optional)

Pull the embedding model, upload the sample flow, then start a run using the flow ID
returned by the upload:

```bash
docker compose -f docker/docker-compose.yml exec ollama ollama pull nomic-embed-text

curl --fail-with-body -sS \
  -X POST http://localhost:8080/api/v1/flows \
  -H 'Content-Type: application/json' \
  --data-binary @sample_flows/quickstart/docker_e2e_ollama_opensearch.json

curl --fail-with-body -sS \
  -X POST http://localhost:8080/api/v1/job_runs \
  -H 'Content-Type: application/json' \
  -d '{"entity":{"job":{"asset_ref":"PASTE_FLOW_ID"}}}'
```

## Stage 3: Run the sample flow in the UI

1. Open the UI: `http://localhost:8080/ui/home`.
2. Click **Start** on **Get started with sample data**. The sample flow opens in the canvas.
3. Click **Run flow** in the canvas to run it and view its progress and results.

#### Optional: Watch BFF logs

To monitor BFF activity while using the UI, start this log stream before step 1:

```bash
docker compose -f docker/docker-compose.yml logs -f --tail=100 bff
```

## Stop the stack

```bash
docker compose -f docker/docker-compose.yml down
```

Named data volumes are retained. Add `-v` to remove them.
