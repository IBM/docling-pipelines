import argparse
import json
import os
import pathlib
import uuid
from datetime import datetime, timezone

import jsonschema
from confluent_kafka import Producer
from dotenv import load_dotenv

load_dotenv()

BOOTSTRAP_SERVERS = os.environ["KAFKA_BOOTSTRAP_SERVERS"]
TOPIC = os.environ["KAFKA_TOPIC"]
SCHEMA_PATH = os.environ.get("SCHEMA_PATH", str(pathlib.Path(__file__).parent / "file_event_schema.json"))

_SCHEMA = json.loads(pathlib.Path(SCHEMA_PATH).read_text())


def build_event(*, event_type: str, connection_id: str, flow_id: str, file_path: str) -> dict:
    event = {
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "event_timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "connection_id": connection_id,
        "flow_id": flow_id,
        "file_path": file_path,
    }
    jsonschema.validate(instance=event, schema=_SCHEMA)
    return event


def delivery_report(err, msg):
    if err:
        print("Delivery failed: %s" % err)
    else:
        print("Delivered to %s [partition %d] offset %d" % (msg.topic(), msg.partition(), msg.offset()))


def produce(*, event_type: str, connection_id: str, flow_id: str, file_path: str) -> None:
    producer = Producer({"bootstrap.servers": BOOTSTRAP_SERVERS})

    event = build_event(
        event_type=event_type,
        connection_id=connection_id,
        flow_id=flow_id,
        file_path=file_path,
    )

    producer.produce(
        topic=TOPIC,
        key=event["event_id"],
        value=json.dumps(event),
        callback=delivery_report,
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
