"""Consume JSON messages from the configured topic using its latest value schema."""

import json
import os

from confluent_kafka import DeserializingConsumer, KafkaError
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.json_schema import JSONDeserializer

BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "127.0.0.1:9092")
TOPIC = os.environ["KAFKA_TOPIC"]
GROUP_ID = os.getenv("KAFKA_GROUP_ID", "docpipe-event-consumer")
SCHEMA_REGISTRY_URL = os.getenv("SCHEMA_REGISTRY_URL", "http://localhost:8081")


def consume() -> None:
    registry = SchemaRegistryClient({"url": SCHEMA_REGISTRY_URL})
    registered_schema = registry.get_latest_version(f"{TOPIC}-value")
    deserializer = JSONDeserializer(
        registered_schema.schema.schema_str,
        schema_registry_client=registry,
    )
    consumer = DeserializingConsumer(
        {
            "bootstrap.servers": BOOTSTRAP_SERVERS,
            "group.id": GROUP_ID,
            "auto.offset.reset": "earliest",
            "value.deserializer": deserializer,
        }
    )
    consumer.subscribe([TOPIC])
    print(f"Listening on {TOPIC}", flush=True)

    try:
        while True:
            message = consumer.poll(timeout=1.0)
            if message is None:
                continue
            if message.error():
                if message.error().code() != KafkaError._PARTITION_EOF:
                    print(f"Consumer error: {message.error()}")
                continue
            print(json.dumps(message.value()), flush=True)
    except KeyboardInterrupt:
        pass
    finally:
        consumer.close()


if __name__ == "__main__":
    consume()
