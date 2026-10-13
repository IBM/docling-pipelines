"""Produce a JSON message using the latest registered topic schema."""

import argparse
import json
import os

from confluent_kafka import SerializingProducer
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.json_schema import JSONSerializer

BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "127.0.0.1:9092")
TOPIC = os.environ["KAFKA_TOPIC"]
SCHEMA_REGISTRY_URL = os.getenv("SCHEMA_REGISTRY_URL", "http://localhost:8081")


def produce(*, message: dict) -> None:
    registry = SchemaRegistryClient({"url": SCHEMA_REGISTRY_URL})
    registered_schema = registry.get_latest_version(f"{TOPIC}-value")
    serializer = JSONSerializer(
        registered_schema.schema.schema_str,
        registry,
        conf={"auto.register.schemas": False},
    )
    producer = SerializingProducer(
        {
            "bootstrap.servers": BOOTSTRAP_SERVERS,
            "value.serializer": serializer,
        }
    )
    producer.produce(topic=TOPIC, key=None, value=message)
    remaining = producer.flush(timeout=5)
    if remaining > 0:
        raise RuntimeError("Kafka did not deliver the event before the timeout")
    print(f"Produced: {json.dumps(message)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Produce a JSON message using the latest registered topic schema.")
    parser.add_argument("--message", required=True, help="JSON message object to produce.")
    args = parser.parse_args()
    try:
        message = json.loads(args.message)
    except json.JSONDecodeError as error:
        parser.error(f"--message must contain valid JSON: {error}")
    if not isinstance(message, dict):
        parser.error("--message must be a JSON object")
    produce(message=message)
