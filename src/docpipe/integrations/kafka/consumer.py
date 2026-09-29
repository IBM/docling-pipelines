"""Background Kafka consumer for file events."""

import os
from threading import Event, Thread

import httpx
from confluent_kafka import DeserializingConsumer, KafkaError
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.json_schema import JSONDeserializer

from docpipe.core.constants.constants import EnvironmentVariables
from docpipe.integrations.kafka.producer import KafkaFileEventNotificationProducer
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger(__name__)


class KafkaFileEventConsumer:
    """Consume file events in a thread for the lifetime of the API process."""

    def __init__(self) -> None:
        self.topic = os.environ[EnvironmentVariables.KAFKA_INPUT_TOPIC]
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
        self._notification_producer = KafkaFileEventNotificationProducer()
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

    def _handle_event(self, event: dict) -> None:
        logger.info(
            "Kafka file event: type=%s connection_id=%s flow_id=%s file_path=%s",
            event["event_type"],
            event["connection_id"],
            event["flow_id"],
            event["file_path"],
        )
        if event["event_type"] not in {"created", "modified"}:
            self._notification_producer.publish_status(event=event, status="skipped", reason="Event type is not supported")
            return

        api_url = os.getenv("DOCPIPE_API_URL", "http://127.0.0.1:8080").rstrip("/")
        request_body = {
            "entity": {
                "job": {
                    "asset_ref": event["flow_id"],
                    "asset_ref_type": "ibm_udp_flow",
                    "name": event["flow_id"],
                },
                "job_run": {
                    "configuration": {
                        "event_streaming": True,
                        "file_path": event["file_path"],
                        "metadata": {
                            "event_id": event["event_id"],
                            "event_type": event["event_type"],
                            "event_timestamp": event["event_timestamp"],
                            "connection_id": event["connection_id"],
                        },
                    }
                },
            }
        }
        try:
            response = httpx.post(f"{api_url}/api/v1/job_runs", json=request_body, timeout=30)
            response.raise_for_status()
            job_run_id = response.json()["job_run_id"]
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            logger.error("Could not create job run for event %s: %s", event["event_id"], exc)
            self._notification_producer.publish_status(event=event, status="failed", reason=str(exc))
            return

        logger.info("Created job run %s for event %s", job_run_id, event["event_id"])
        self._notification_producer.publish_status(event=event, status="received", reason=f"job_run_id={job_run_id}")
