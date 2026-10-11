# Run Docling Pipelines with Docker Compose

Run from the repository root.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Stage 0: Configure the environment](#stage-0-configure-the-environment)
- [Stage 1: Build the images](#stage-1-build-the-images)
- [Stage 2: Run the existing Kafka, Schema Registry, Ollama, OpenSearch, and API stack](#stage-2-run-the-existing-kafka-schema-registry-ollama-opensearch-and-api-stack)
- [Stage 3: Run the Kafka example](#stage-3-run-the-kafka-example)
- [Stop the stack](#stop-the-stack)

## Prerequisites

- Docker Engine 24.0+ and Docker Compose 2.24+; the Docker daemon must be running.
- At least 6 GB of RAM available for containers.
- Internet access to build images and download the embedding model.

## Stage 0: Configure the environment

```bash
cp -n docker/event-streaming/.env.example docker/event-streaming/.env
```

The run command enables the listener for the current Compose invocation; the existing `.env` can stay unchanged.

## Stage 1: Build the images

```bash
docker compose --env-file docker/event-streaming/.env -f docker/event-streaming/docker-compose.yml config --quiet
docker compose --env-file docker/event-streaming/.env -f docker/event-streaming/docker-compose.yml build
```

For a GPU build:

```bash
# docker compose --env-file docker/event-streaming/.env -f docker/event-streaming/docker-compose.yml build --build-arg COMPUTE_BACKEND=gpu
```

## Stage 2: Run the existing Kafka, Schema Registry, Ollama, OpenSearch, and API stack

```bash
DOCPIPE_EVENT_STREAMING_ENABLED=true docker compose --env-file docker/event-streaming/.env -f docker/event-streaming/docker-compose.yml up -d --no-build
docker compose --env-file docker/event-streaming/.env -f docker/event-streaming/docker-compose.yml exec -T ollama ollama pull nomic-embed-text
```

This starts the services already defined in the Compose file. The listener is enabled for this run.

Check API health:

```bash
curl --fail http://localhost:8080/health
```

API docs: `http://localhost:8080/api/v1/docs`.

Create the existing Ollama and OpenSearch sample flow from the repository root:

```bash
curl --fail-with-body --request POST http://localhost:8080/api/v1/flows \
  --header 'Content-Type: application/json' \
  --data-binary @sample_flows/quickstart/docker_e2e_ollama_opensearch.json
```

Register the returned `flow_id` for a routing key:

```bash
curl --fail-with-body --request POST http://localhost:8080/api/v1/event_mappings \
  --header 'Content-Type: application/json' \
  --data '{"key":"kafka-e2e-20261011","flow_id":"<flow_id>"}'
```

For later runs, reuse the saved flow and mapping and publish a new event with a fresh `event_id`.

### API logs (optional)

```bash
docker compose --env-file docker/event-streaming/.env -f docker/event-streaming/docker-compose.yml logs -f --tail=100 docpipe
```

## Stage 3: Run the Kafka example

Install the Kafka dependencies into the project virtual environment:

```bash
uv sync --extra dev --extra event-streaming
```

Confirm that the input topic and event schema were initialized:

```bash
docker compose --env-file docker/event-streaming/.env -f docker/event-streaming/docker-compose.yml logs kafka-init register-schema
curl --fail http://localhost:8081/subjects/docpipe-input-value/versions/latest
```

To inspect events independently, run the sample consumer in another terminal:

```bash
uv run --env-file docker/event-streaming/.env --extra event-streaming python docker/event-streaming/helpers/kafka_consumer.py
```

Produce an event:

```bash
uv run --env-file docker/event-streaming/.env --extra event-streaming python docker/event-streaming/helpers/kafka_producer.py \
  --message '{"event_id":"550e8400-e29b-41d4-a716-446655440000","event_timestamp":"2026-01-01T00:00:00Z","routing_key":"kafka-e2e-20261011","operation":"update","file_reference":"/documents/TR-INV_001_3_2.1.pdf"}'
```

When the listener is enabled and the `kafka-e2e-20261011` mapping points to a saved flow, the API logs the returned
`job_run_id`.
Use `GET http://localhost:8080/api/v1/job_runs/<job_run_id>` to check the run status and output. A successful run
reports `Completed`, one processed document, and zero failures. The flow runs filesystem ingest, Docling extraction,
chunking, Ollama embeddings, and OpenSearch indexing. The tested PDF produced 11 chunks, all indexed successfully.

```bash
docker compose --env-file docker/event-streaming/.env -f docker/event-streaming/docker-compose.yml logs --since 2m docpipe | grep 'Dispatched event'
```

Use the `job_run_id` from that log line in the status request.

```bash
RUN_ID="paste-job-run-id-from-log"
curl --fail "http://localhost:8080/api/v1/job_runs/${RUN_ID}"
```

Check the OpenSearch index count:

```bash
docker compose --env-file docker/event-streaming/.env -f docker/event-streaming/docker-compose.yml exec -T opensearch sh -c 'curl --fail --silent --show-error -u "admin:$OPENSEARCH_INITIAL_ADMIN_PASSWORD" -H "Content-Type: application/json" -d "{\"query\":{\"match\":{\"doc_name\":\"TR-INV_001_3_2.1.pdf\"}}}" http://localhost:9200/docker-e2e-documents/_count'
```

The count should be 11 for the tested PDF.

## Stop the stack

```bash
docker compose --env-file docker/event-streaming/.env -f docker/event-streaming/docker-compose.yml down
```

This stops and removes the Compose containers while preserving their data volumes.
