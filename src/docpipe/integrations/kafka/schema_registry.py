"""Register the file event schema used by Kafka producers and consumers."""

import os
from pathlib import Path

from confluent_kafka.schema_registry import Schema, SchemaRegistryClient

from docpipe.core.constants.constants import EnvironmentVariables
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger(__name__)


class KafkaSchemaRegistryInitializer:
    """Register the file event schema when the API starts."""

    @staticmethod
    def initialize() -> None:
        """Register the bundled schema, failing startup if registration fails."""
        registry_url = os.environ[EnvironmentVariables.SCHEMA_REGISTRY_URL]
        kafka_topic = os.environ[EnvironmentVariables.KAFKA_TOPIC]
        schema_str = Path(__file__).with_name("file_event_schema.json").read_text(encoding="utf-8")
        client = SchemaRegistryClient({"url": registry_url})
        schema_id = client.register_schema(f"{kafka_topic}-value", Schema(schema_str, schema_type="JSON"))
        logger.info("Registered Kafka file event schema for %s-value (id=%d)", kafka_topic, schema_id)
