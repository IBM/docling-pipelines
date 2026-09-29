"""Publish file event notifications to Kafka."""

import os
from datetime import UTC, datetime

from confluent_kafka import SerializingProducer
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.json_schema import JSONSerializer

from docpipe.core.constants.constants import EnvironmentVariables
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger(__name__)


class KafkaFileEventNotificationProducer:
    """Publish schema-validated status events to the notification topic."""

    def __init__(self) -> None:
        self.topic = os.environ[EnvironmentVariables.KAFKA_NOTIFICATION_TOPIC]
        registry_client = SchemaRegistryClient({"url": os.environ[EnvironmentVariables.SCHEMA_REGISTRY_URL]})
        registered_schema = registry_client.get_latest_version(f"{self.topic}-value")
        serializer = JSONSerializer(registered_schema.schema.schema_str, registry_client)
        self._producer = SerializingProducer(
            {
                "bootstrap.servers": os.environ[EnvironmentVariables.KAFKA_BOOTSTRAP_SERVERS],
                "value.serializer": serializer,
            }
        )

    def publish_status(self, *, event: dict, status: str, reason: str | None = None) -> None:
        """Publish a status for an input file event."""
        status_event = {
            "event_id": event["event_id"],
            "event_type": event["event_type"],
            "event_timestamp": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "connection_id": event["connection_id"],
            "flow_id": event["flow_id"],
            "file_path": event["file_path"],
            "status": status,
        }
        if reason is not None:
            status_event["reason"] = reason
        delivery_errors = []

        def on_delivery(*callback_args):
            if callback_args[0]:
                delivery_errors.append(callback_args[0])

        self._producer.produce(
            topic=self.topic,
            key=event["event_id"],
            value=status_event,
            on_delivery=on_delivery,
        )
        if self._producer.flush(timeout=10) or delivery_errors:
            raise RuntimeError("Could not deliver Kafka file event status")
        logger.info("Published Kafka file event notification %s for %s", status, event["event_id"])
