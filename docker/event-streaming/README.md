# Run Docling Pipelines with Docker Compose

Run from the repository root.

## Stage 0: Configure the environment

```bash
cp -n docker/event-streaming/.env.example docker/event-streaming/.env
```

## Stage 1: Build the images

```bash
docker compose --env-file docker/event-streaming/.env -f docker/event-streaming/docker-compose.yml config --quiet
docker compose --env-file docker/event-streaming/.env -f docker/event-streaming/docker-compose.yml build
```

For a GPU build:

```bash
#docker compose --env-file docker/event-streaming/.env -f docker/event-streaming/docker-compose.yml config --quiet
#docker compose --env-file docker/event-streaming/.env -f docker/event-streaming/docker-compose.yml build --build-arg COMPUTE_BACKEND=gpu
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

```bash
docker compose --env-file docker/event-streaming/.env -f docker/event-streaming/docker-compose.yml logs -f --tail=100 docpipe
```

## Stage 3: Run the Kafka example

Install the Kafka dependencies:

```bash
uv sync --extra dev --extra event-streaming
```

Check the event schema registration:

```bash
docker compose --env-file docker/event-streaming/.env -f docker/event-streaming/docker-compose.yml logs register-schema
```

Consume messages in a new terminal:

```bash
uv run --env-file docker/event-streaming/.env python docker/event-streaming/helpers/kafka_consumer.py
```

Produce a message in another terminal:

```bash
uv run --env-file docker/event-streaming/.env python docker/event-streaming/helpers/kafka_producer.py \
  --message '{"event_id":"550e8400-e29b-41d4-a716-446655440000","event_timestamp":"2026-01-01T00:00:00Z","routing_key":"invoices","operation":"update","file_reference":"/documents/invoice.pdf"}'
```

## Stop the stack

```bash
docker compose --env-file docker/event-streaming/.env -f docker/event-streaming/docker-compose.yml down
```

Add `-v` to remove named data volumes.
