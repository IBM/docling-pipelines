import os
import signal

from confluent_kafka import DeserializingConsumer, KafkaError
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.json_schema import JSONDeserializer
from dotenv import load_dotenv

load_dotenv()

BOOTSTRAP_SERVERS = os.environ["KAFKA_BOOTSTRAP_SERVERS"]
TOPIC = os.environ["KAFKA_TOPIC"]
GROUP_ID = os.environ.get("KAFKA_GROUP_ID", "docpipe-file-events-consumer")
SCHEMA_REGISTRY_URL = os.environ["SCHEMA_REGISTRY_URL"]

_registry_client = SchemaRegistryClient({"url": SCHEMA_REGISTRY_URL})
# Fetch the latest registered schema for the topic's value subject
_registered_schema = _registry_client.get_latest_version("%s-value" % TOPIC)
_deserializer = JSONDeserializer(_registered_schema.schema.schema_str, schema_registry_client=_registry_client)

_running = True


def _handle_shutdown(sig, frame):
    global _running
    print("\nShutting down...")
    _running = False


signal.signal(signal.SIGINT, _handle_shutdown)
signal.signal(signal.SIGTERM, _handle_shutdown)


def handle_event(event: dict) -> None:
    """Called for each valid event. Replace with pipeline trigger logic."""
    print(
        "[%s] event_type=%s connection_id=%s flow_id=%s file_path=%s"
        % (event["event_timestamp"], event["event_type"], event["connection_id"], event["flow_id"], event["file_path"])
    )


def consume() -> None:
    consumer = DeserializingConsumer(
        {
            "bootstrap.servers": BOOTSTRAP_SERVERS,
            "group.id": GROUP_ID,
            "auto.offset.reset": "earliest",
            "value.deserializer": _deserializer,
        }
    )
    consumer.subscribe([TOPIC])
    print("Listening on topic '%s' (group: %s) ..." % (TOPIC, GROUP_ID))

    try:
        while _running:
            msg = consumer.poll(timeout=1.0)
            if msg is None:
                continue
            if msg.error():
                if msg.error().code() != KafkaError._PARTITION_EOF:
                    print("Consumer error: %s" % msg.error())
                continue

            handle_event(msg.value())
    finally:
        consumer.close()


if __name__ == "__main__":
    consume()
