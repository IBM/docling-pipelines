"""Register the file event schema used by Kafka producers and consumers."""

import os
from pathlib import Path

from confluent_kafka.schema_registry import Schema, SchemaRegistryClient

from docpipe.core.constants.constants import EnvironmentVariables
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger(__name__)


class KafkaSchemaRegistryInitializer:
    """Register Kafka input and notification schemas when the API starts."""

    @staticmethod
    def initialize() -> None:
        """Register the bundled schemas, failing startup if registration fails."""
        registry_url = os.environ[EnvironmentVariables.SCHEMA_REGISTRY_URL]
        client = SchemaRegistryClient({"url": registry_url})
        for topic_name, schema_file in (
            (EnvironmentVariables.KAFKA_INPUT_TOPIC, "file_event_schema.json"),
            (EnvironmentVariables.KAFKA_NOTIFICATION_TOPIC, "file_event_status_schema.json"),
        ):
            topic = os.environ[topic_name]
            schema_str = Path(__file__).with_name(schema_file).read_text(encoding="utf-8")
            schema_id = client.register_schema(f"{topic}-value", Schema(schema_str, schema_type="JSON"))
            logger.info("Registered Kafka schema for %s-value (id=%d)", topic, schema_id)
