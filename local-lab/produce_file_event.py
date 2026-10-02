"""Send a file event to the local lab Kafka input topic."""

import argparse
import json
import os
import uuid
from datetime import UTC, datetime

from confluent_kafka import SerializingProducer
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.json_schema import JSONSerializer


def main() -> None:
    parser = argparse.ArgumentParser(description="Produce a file event for the local lab.")
    parser.add_argument("--event-type", choices=["created", "modified", "deleted"], required=True)
    parser.add_argument("--connection-id", required=True)
    parser.add_argument("--flow-id", required=True)
    parser.add_argument("--file-path", required=True)
    args = parser.parse_args()

    topic = os.getenv("KAFKA_INPUT_TOPIC", "docpipe-poc")
    registry_url = os.getenv("SCHEMA_REGISTRY_URL", "http://127.0.0.1:8081")
    bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "127.0.0.1:9092")

    registry_client = SchemaRegistryClient({"url": registry_url})
    registered_schema = registry_client.get_latest_version(f"{topic}-value")
    serializer = JSONSerializer(registered_schema.schema.schema_str, registry_client)
    producer = SerializingProducer({"bootstrap.servers": bootstrap_servers, "value.serializer": serializer})

    event = {
        "event_id": str(uuid.uuid4()),
        "event_type": args.event_type,
        "event_timestamp": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "connection_id": args.connection_id,
        "flow_id": args.flow_id,
        "file_path": args.file_path,
    }
    delivery_errors = []

    def on_delivery(*callback_args):
        if callback_args[0]:
            delivery_errors.append(callback_args[0])

    producer.produce(topic=topic, key=event["event_id"], value=event, on_delivery=on_delivery)
    if producer.flush(timeout=10) or delivery_errors:
        raise RuntimeError("Could not deliver Kafka file event")
    print(json.dumps(event, indent=2))


if __name__ == "__main__":
    main()
