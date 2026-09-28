"""Background Kafka consumer for file events."""

import os
from threading import Event, Thread

from confluent_kafka import DeserializingConsumer, KafkaError
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.json_schema import JSONDeserializer

from docpipe.core.constants.constants import EnvironmentVariables
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger(__name__)


class KafkaFileEventConsumer:
    """Consume file events in a thread for the lifetime of the API process."""

    def __init__(self) -> None:
        self.topic = os.environ[EnvironmentVariables.KAFKA_TOPIC]
        group_id = os.getenv(EnvironmentVariables.KAFKA_GROUP_ID, "docpipe-file-events-consumer")
        registry_client = SchemaRegistryClient({"url": os.environ[EnvironmentVariables.SCHEMA_REGISTRY_URL]})
        registered_schema = registry_client.get_latest_version(f"{self.topic}-value")
        deserializer = JSONDeserializer(registered_schema.schema.schema_str, schema_registry_client=registry_client)
        self._consumer = DeserializingConsumer(
            {
                "bootstrap.servers": os.environ[EnvironmentVariables.KAFKA_BOOTSTRAP_SERVERS],
                "group.id": group_id,
                "auto.offset.reset": "earliest",
                "value.deserializer": deserializer,
            }
        )
        self._stop_event = Event()
        self._thread = Thread(target=self._consume, name="docpipe-kafka-consumer", daemon=True)

    def start(self) -> None:
        """Start consuming in a background thread."""
        self._thread.start()

    def stop(self) -> None:
        """Stop polling and close the consumer on its thread."""
        self._stop_event.set()
        self._thread.join(timeout=5)

    def _consume(self) -> None:
        self._consumer.subscribe([self.topic])
        logger.info("Listening for Kafka file events on %s", self.topic)
        try:
            while not self._stop_event.is_set():
                message = self._consumer.poll(timeout=1.0)
                if message is None:
                    continue
                if message.error():
                    if message.error().code() != KafkaError._PARTITION_EOF:
                        logger.error("Kafka consumer error: %s", message.error())
                    continue
                self._handle_event(message.value())
        finally:
            self._consumer.close()

    @staticmethod
    def _handle_event(event: dict) -> None:
        logger.info(
            "Kafka file event: type=%s connection_id=%s flow_id=%s file_path=%s",
            event["event_type"],
            event["connection_id"],
            event["flow_id"],
            event["file_path"],
        )
