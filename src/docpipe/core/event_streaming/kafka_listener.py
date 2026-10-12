"""Kafka listener for file event dispatch."""

from __future__ import annotations

import asyncio
import importlib
import os
import threading
from typing import Any

from docpipe.core.constants.constants import EnvironmentVariables
from docpipe.core.event_streaming.dispatch_service import EventDispatchService
from docpipe.core.event_streaming.models import InputEvent
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger()


class KafkaEventListener:
    """Consume, validate, dispatch, and acknowledge file events."""

    def __init__(
        self,
        *,
        dispatch_service: EventDispatchService,
        bootstrap_servers: str,
        topic: str,
        group_id: str,
        schema_registry_url: str,
    ) -> None:
        self._dispatch_service = dispatch_service
        self._bootstrap_servers = bootstrap_servers
        self._topic = topic
        self._group_id = group_id
        self._schema_registry_url = schema_registry_url
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    @classmethod
    def from_environment(cls, *, dispatch_service: EventDispatchService) -> KafkaEventListener | None:
        """Build the listener only when enabled and validate its required settings."""
        enabled = os.getenv(EnvironmentVariables.DOCPIPE_EVENT_STREAMING_ENABLED, "false").strip().lower()
        if enabled != "true":
            return None

        environment_names = {
            "bootstrap_servers": EnvironmentVariables.KAFKA_BOOTSTRAP_SERVERS,
            "topic": EnvironmentVariables.KAFKA_INPUT_TOPIC,
            "group_id": EnvironmentVariables.KAFKA_GROUP_ID,
            "schema_registry_url": EnvironmentVariables.SCHEMA_REGISTRY_URL,
        }
        settings = {key: os.getenv(name, "").strip() for key, name in environment_names.items()}
        missing = [name for name, value in settings.items() if not value]
        if missing:
            missing_names = [environment_names[name] for name in missing]
            raise ValueError(f"Kafka event streaming requires: {', '.join(missing_names)}")

        try:
            importlib.import_module("confluent_kafka.schema_registry.json_schema")
        except ImportError as exc:
            raise RuntimeError("Kafka event streaming requires the 'event-streaming' dependency extra") from exc

        return cls(
            dispatch_service=dispatch_service,
            **settings,
        )

    def start(self) -> None:
        """Start the consumer thread without blocking API startup."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._consume, name="docpipe-kafka-listener", daemon=True)
        self._thread.start()
        logger.info("Started Kafka event listener for topic %s", self._topic)

    async def stop(self) -> None:
        """Request cooperative shutdown and join without blocking the event loop."""
        self._stop_event.set()
        if self._thread is None:
            return
        await asyncio.to_thread(self._thread.join, 5.0)
        if self._thread.is_alive():
            logger.warning("Kafka event listener did not stop within the shutdown timeout")

    def _consume(self) -> None:
        consumer = None
        try:
            from confluent_kafka import Consumer
            from confluent_kafka.schema_registry import SchemaRegistryClient
            from confluent_kafka.schema_registry.json_schema import JSONDeserializer
            from confluent_kafka.serialization import MessageField, SerializationContext

            registry = SchemaRegistryClient({"url": self._schema_registry_url})
            registered_schema = registry.get_latest_version(f"{self._topic}-value")
            deserializer = JSONDeserializer(
                registered_schema.schema.schema_str,
                schema_registry_client=registry,
            )
            consumer = Consumer(
                {
                    "bootstrap.servers": self._bootstrap_servers,
                    "group.id": self._group_id,
                    "auto.offset.reset": "earliest",
                    "enable.auto.commit": False,
                    "enable.auto.offset.store": False,
                }
            )
            consumer.subscribe([self._topic])

            while not self._stop_event.is_set():
                message = consumer.poll(timeout=1.0)
                if message is None:
                    continue
                if message.error() is not None:
                    logger.error(
                        "Kafka message error for topic %s: %s",
                        self._topic,
                        message.error(),
                    )
                    continue

                event_id = "unknown"
                try:
                    payload = deserializer(
                        message.value(),
                        SerializationContext(self._topic, MessageField.VALUE),
                    )
                    if isinstance(payload, dict) and payload.get("event_id") is not None:
                        event_id = str(payload["event_id"])
                    event = InputEvent.model_validate(payload)
                    event_id = str(event.event_id)
                    self._dispatch_service.dispatch(event=event)
                except Exception:
                    logger.exception(
                        "Event %s dispatch failed for Kafka message %s[%s] offset %s; acknowledging terminal failure",
                        event_id,
                        message.topic(),
                        message.partition(),
                        message.offset(),
                    )
                self._commit(consumer=consumer, message=message)
        except Exception:
            logger.exception("Kafka event listener stopped after a consumer error")
        finally:
            if consumer is not None:
                try:
                    consumer.close()
                except Exception:
                    logger.exception("Failed to close Kafka consumer for topic %s", self._topic)
            logger.info("Stopped Kafka event listener for topic %s", self._topic)

    @staticmethod
    def _commit(*, consumer: Any, message: Any) -> None:
        """Commit this message after dispatch succeeds or reaches terminal failure."""
        try:
            committed_partitions = consumer.commit(message=message, asynchronous=False)
            for partition in committed_partitions or []:
                if partition.error is not None:
                    logger.error(
                        "Kafka commit failed for %s[%s] offset %s: %s",
                        partition.topic,
                        partition.partition,
                        partition.offset,
                        partition.error,
                    )
        except Exception:
            logger.exception(
                "Kafka commit failed for %s[%s] offset %s",
                message.topic(),
                message.partition(),
                message.offset(),
            )
