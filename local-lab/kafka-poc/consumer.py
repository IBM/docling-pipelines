import json
import os
import pathlib
import signal
import sys

import jsonschema
from confluent_kafka import Consumer, KafkaError
from dotenv import load_dotenv

load_dotenv()

BOOTSTRAP_SERVERS = os.environ["KAFKA_BOOTSTRAP_SERVERS"]
TOPIC = os.environ["KAFKA_TOPIC"]
GROUP_ID = os.environ.get("KAFKA_GROUP_ID", "docpipe-file-events-consumer")
SCHEMA_PATH = os.environ.get("SCHEMA_PATH", str(pathlib.Path(__file__).parent / "file_event_schema.json"))

_SCHEMA = json.loads(pathlib.Path(SCHEMA_PATH).read_text())

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
    consumer = Consumer(
        {
            "bootstrap.servers": BOOTSTRAP_SERVERS,
            "group.id": GROUP_ID,
            "auto.offset.reset": "earliest",
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

            try:
                event = json.loads(msg.value())
                jsonschema.validate(instance=event, schema=_SCHEMA)
                handle_event(event)
            except json.JSONDecodeError as exc:
                print("Skipping non-JSON message: %s" % exc)
            except jsonschema.ValidationError as exc:
                print("Skipping invalid event: %s" % exc.message)
    finally:
        consumer.close()


if __name__ == "__main__":
    consume()
