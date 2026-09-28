import argparse
import json
import os
import uuid
from datetime import datetime, timezone

from confluent_kafka import SerializingProducer
from confluent_kafka.schema_registry import SchemaRegistryClient, Schema
from confluent_kafka.schema_registry.json_schema import JSONSerializer
from dotenv import load_dotenv

load_dotenv()

BOOTSTRAP_SERVERS = os.environ["KAFKA_BOOTSTRAP_SERVERS"]
TOPIC = os.environ["KAFKA_TOPIC"]
SCHEMA_REGISTRY_URL = os.environ["SCHEMA_REGISTRY_URL"]

_registry_client = SchemaRegistryClient({"url": SCHEMA_REGISTRY_URL})
# Fetch the latest registered schema for the topic's value subject
_registered_schema = _registry_client.get_latest_version("%s-value" % TOPIC)
_serializer = JSONSerializer(_registered_schema.schema.schema_str, _registry_client)


def build_event(*, event_type: str, connection_id: str, flow_id: str, file_path: str) -> dict:
    return {
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "event_timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "connection_id": connection_id,
        "flow_id": flow_id,
        "file_path": file_path,
    }


def delivery_report(err, msg):
    if err:
        print("Delivery failed: %s" % err)
    else:
        print("Delivered to %s [partition %d] offset %d" % (msg.topic(), msg.partition(), msg.offset()))


def produce(*, event_type: str, connection_id: str, flow_id: str, file_path: str) -> None:
    producer = SerializingProducer(
        {
            "bootstrap.servers": BOOTSTRAP_SERVERS,
            "value.serializer": _serializer,
        }
    )

    event = build_event(
        event_type=event_type,
        connection_id=connection_id,
        flow_id=flow_id,
        file_path=file_path,
    )

    producer.produce(
        topic=TOPIC,
        key=event["event_id"],
        value=event,
        on_delivery=delivery_report,
    )
    producer.flush()
    print("Event: %s" % json.dumps(event, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Produce a docpipe file event to Kafka.")
    parser.add_argument("--event-type", choices=["created", "modified", "deleted"], required=True)
    parser.add_argument("--connection-id", required=True, help="UUID of the source connection.")
    parser.add_argument("--flow-id", required=True, help="UUID of the docpipe flow to trigger.")
    parser.add_argument("--file-path", required=True, help="Fully qualified path/URI to the file.")
    args = parser.parse_args()

    produce(
        event_type=args.event_type,
        connection_id=args.connection_id,
        flow_id=args.flow_id,
        file_path=args.file_path,
    )
