# Run Docling Pipelines with Docker Compose

Run all commands from repo root.

## Prerequisites

- Docker Engine 24.0+ and Docker Compose 2.24+; the Docker daemon must be running.
- At least 6 GB of RAM available for containers.
- Internet access to build images and download the embedding model.

## Step 0: Setup Environment

```bash
cp -n docker/event-streaming/.env.example docker/event-streaming/.env
```

## Step 1: Verify Configuration

```bash
docker compose --env-file docker/event-streaming/.env -f docker/event-streaming/docker-compose.yml config --quiet
```

## Step 2: Build Image

```bash
docker compose --env-file docker/event-streaming/.env -f docker/event-streaming/docker-compose.yml build
```

or, for a GPU build, use:

```bash
# docker compose --env-file docker/event-streaming/.env -f docker/event-streaming/docker-compose.yml build --build-arg COMPUTE_BACKEND=gpu
```

## Step 3: Start Application

```bash
docker compose --env-file docker/event-streaming/.env -f docker/event-streaming/docker-compose.yml up -d --no-build
```

### Check application health:

```bash
docker compose --env-file docker/event-streaming/.env -f docker/event-streaming/docker-compose.yml ps
curl --fail http://localhost:8080/health
```

### View API logs (optional)

In a separate terminal, run this command to follow the API logs. Press `Ctrl+C` to stop the stream.

```bash
docker compose --env-file docker/event-streaming/.env -f docker/event-streaming/docker-compose.yml logs -f docpipe
```

## Step 4: Event Streaming: Run a sample producer and consumer

Install the Event Streaming dependencies:

```bash
uv sync --extra dev --extra event-streaming
```

### Confirm the topic was created

The stack creates the input topic at startup. Check the initialization logs before sending an event:

```bash
docker compose --env-file docker/event-streaming/.env -f docker/event-streaming/docker-compose.yml logs kafka-init
```

### Confirm the schema is ready

The stack registers the event schema at startup. Check the registration logs before sending an event:

```bash
docker compose --env-file docker/event-streaming/.env -f docker/event-streaming/docker-compose.yml logs register-schema
```

### Start listening for events

Open a new terminal and leave the consumer running. It will print each event as it arrives:

```bash
uv run --env-file docker/event-streaming/.env python docker/event-streaming/helpers/kafka_consumer.py
```

### Send a sample event

Open a new terminal, publish a sample `create` event. You should see it appear in the consumer output:

```bash
uv run --env-file docker/event-streaming/.env python docker/event-streaming/helpers/kafka_producer.py \
  --message '{"event_id":"00000000-0000-0000-0000-000000000000","event_timestamp":"2026-01-01T00:00:00Z","routing_key":"example","operation":"create","file_reference":"/documents/example.txt"}'
```

## Stop the stack

```bash
docker compose --env-file docker/event-streaming/.env -f docker/event-streaming/docker-compose.yml down
```

Named data volumes are retained. Add `-v` to remove them.
