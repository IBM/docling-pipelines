# Run Docling Pipelines with Docker Compose

Run from the repository root.

## Stage 0: Set the OpenSearch password

Compose requires `OPENSEARCH_PASSWORD`. Run this in each terminal before using Compose:

```bash
export OPENSEARCH_PASSWORD='MyStrongPass@123' # pragma: allowlist secret
```

## Stage 1: Build the images

```bash
docker compose -f docker/event-streaming/docker-compose.yml config --quiet
docker compose -f docker/event-streaming/docker-compose.yml build
```

or, for a GPU build, use:

```bash
# docker compose -f docker/event-streaming/docker-compose.yml config --quiet
# docker compose -f docker/event-streaming/docker-compose.yml build --build-arg COMPUTE_BACKEND=gpu
```

## Stage 2: Run the API

```bash
docker compose -f docker/event-streaming/docker-compose.yml up -d --no-build
docker compose -f docker/event-streaming/docker-compose.yml ps
```

Check API health:

```bash
curl --fail http://localhost:8080/health
```

API docs: `http://localhost:8080/api/v1/docs`.

### API logs (optional)

Log commands stream until you press `Ctrl+C`.

```bash
docker compose -f docker/event-streaming/docker-compose.yml logs -f --tail=100 docpipe
```

### Run a sample flow through the API (optional)

Pull the embedding model:

```bash
docker compose -f docker/event-streaming/docker-compose.yml exec ollama ollama pull nomic-embed-text
```

Upload the sample flow and use `python3` to capture and print the returned flow ID:

```bash
FLOW_ID=$(curl --fail-with-body -sS \
  -X POST http://localhost:8080/api/v1/flows \
  -H 'Content-Type: application/json' \
  --data-binary @sample_flows/quickstart/docker_e2e_ollama_opensearch.json \
  | python3 -c 'import json, sys; print(json.load(sys.stdin)["flow_id"])')
printf 'FLOW_ID=%s\n' "$FLOW_ID"
```

Start the run in the same terminal using the captured flow ID:

```bash
curl --fail-with-body -sS \
  -X POST http://localhost:8080/api/v1/job_runs \
  -H 'Content-Type: application/json' \
  -d "{\"entity\":{\"job\":{\"asset_ref\":\"${FLOW_ID:?Run the flow upload command first}\"}}}"
```

## Stop the stack

```bash
docker compose -f docker/event-streaming/docker-compose.yml down
```

Named data volumes are retained. Add `-v` to remove them.

# Run the Kafka example

Start in the repository root. This example requires `uv` and Docker Compose.

## Start Kafka and register the schema

```bash
uv sync --extra dev --extra event-streaming
source .venv/bin/activate
cd docker/event-streaming
export KAFKA_TOPIC=docpipe-poc
docker compose up -d
```

## Consume messages

In a new terminal opened at the repository root:

```bash
source .venv/bin/activate
cd docker/event-streaming
export KAFKA_TOPIC=docpipe-poc
python kafka_consumer.py
```

## Produce a message

In another terminal opened at the repository root:

```bash
source .venv/bin/activate
cd docker/event-streaming
export KAFKA_TOPIC=docpipe-poc
python kafka_producer.py --message '{"event_id":"event-001","event_timestamp":"2026-01-01T00:00:00Z"}'
```

The producer prints the result; the consumer prints the message.

## Stop Kafka

```bash
cd docker/event-streaming
docker compose down
```
