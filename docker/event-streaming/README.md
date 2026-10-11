# Run Docling Pipelines with Docker Compose

Run from the repository root.

## Stage 0: Set the OpenSearch password

Copy the event-streaming environment example once. Compose also requires `OPENSEARCH_PASSWORD`; run this in each terminal before using Compose:

```bash
cp -n docker/event-streaming/.env.example docker/event-streaming/.env
export OPENSEARCH_PASSWORD='MyStrongPass@123' # pragma: allowlist secret
```

## Stage 1: Build the images

```bash
docker compose --env-file docker/event-streaming/.env -f docker/event-streaming/docker-compose.yml config --quiet
docker compose --env-file docker/event-streaming/.env -f docker/event-streaming/docker-compose.yml build
```

or, for a GPU build, use:

```bash
# docker compose --env-file docker/event-streaming/.env -f docker/event-streaming/docker-compose.yml config --quiet
# docker compose --env-file docker/event-streaming/.env -f docker/event-streaming/docker-compose.yml build --build-arg COMPUTE_BACKEND=gpu
```

## Stage 2: Run the API

```bash
docker compose --env-file docker/event-streaming/.env -f docker/event-streaming/docker-compose.yml up -d --no-build
docker compose --env-file docker/event-streaming/.env -f docker/event-streaming/docker-compose.yml ps
```

Check API health:

```bash
curl --fail http://localhost:8080/health
```

API docs: `http://localhost:8080/api/v1/docs`.

### API logs (optional)

Log commands stream until you press `Ctrl+C`.

```bash
docker compose --env-file docker/event-streaming/.env -f docker/event-streaming/docker-compose.yml logs -f --tail=100 docpipe
```

### Run a sample flow through the API (optional)

Pull the embedding model:

```bash
docker compose --env-file docker/event-streaming/.env -f docker/event-streaming/docker-compose.yml exec ollama ollama pull nomic-embed-text
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
docker compose --env-file docker/event-streaming/.env -f docker/event-streaming/docker-compose.yml down
```

Named data volumes are retained. Add `-v` to remove them.

# Run the Kafka example

Start in the repository root. This example requires `uv` and Docker Compose.

## Start Kafka and register the event schema

```bash
uv sync --extra dev --extra event-streaming
source .venv/bin/activate
set -a
source docker/event-streaming/.env
set +a
cd docker/event-streaming
docker compose --env-file .env up -d kafka kafka-init schema-registry register-schema
```

Confirm that the schema is registered for the configured topic:

```bash
curl --fail --silent --show-error \
  "${SCHEMA_REGISTRY_URL}/subjects/${KAFKA_INPUT_TOPIC}-value/versions/latest"
```

## Consume messages

In a new terminal opened at the repository root:

```bash
source .venv/bin/activate
set -a
source docker/event-streaming/.env
set +a
cd docker/event-streaming
python helpers/kafka_consumer.py
```

## Produce a message

In another terminal opened at the repository root:

```bash
source .venv/bin/activate
set -a
source docker/event-streaming/.env
set +a
cd docker/event-streaming
python helpers/kafka_producer.py --message '{"event_id":"550e8400-e29b-41d4-a716-446655440000","event_timestamp":"2026-01-01T00:00:00Z","routing_key":"invoices","operation":"update","file_reference":"/documents/invoice.pdf"}'
```

The producer logs the delivery; the consumer logs each message.

Each event requires a UUID `event_id` and RFC 3339 `event_timestamp`, alongside `routing_key`, `operation`, and `file_reference`.

## Stop the Compose project

```bash
cd docker/event-streaming
docker compose --env-file .env down
```
