import json
import os
import pathlib

from confluent_kafka.schema_registry import SchemaRegistryClient, Schema
from dotenv import load_dotenv

load_dotenv()

SCHEMA_REGISTRY_URL = os.environ["SCHEMA_REGISTRY_URL"]
TOPIC = os.environ["KAFKA_TOPIC"]
SCHEMA_PATH = os.environ.get("SCHEMA_PATH", str(pathlib.Path(__file__).parent / "file_event_schema.json"))

SUBJECT = "%s-value" % TOPIC


def register() -> None:
    schema_str = pathlib.Path(SCHEMA_PATH).read_text()
    client = SchemaRegistryClient({"url": SCHEMA_REGISTRY_URL})
    schema_id = client.register_schema(SUBJECT, Schema(schema_str, schema_type="JSON"))
    print("Registered schema for subject '%s' with id %d" % (SUBJECT, schema_id))


if __name__ == "__main__":
    register()
