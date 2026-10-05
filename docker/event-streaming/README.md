# Run the Kafka example

Start in the repository root. This example requires `uv` and Docker Compose.

## Start Kafka and register the schema

```bash
uv sync --extra dev
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
