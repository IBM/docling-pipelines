"""Minimal Kafka consumer for the API POC."""

from __future__ import annotations

import asyncio
import os
import threading

from confluent_kafka import Consumer, KafkaError

from docpipe.core.constants.constants import EnvironmentVariables
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger()


class KafkaConsumerService:
    """Consume messages in a background thread owned by the API lifespan."""

    def __init__(self) -> None:
        self._stop_event = threading.Event()
        self._task: asyncio.Task[None] | None = None

    @property
    def is_running(self) -> bool:
        """Whether the background consumer task is still active."""
        return self._task is not None and not self._task.done()

    async def start(self) -> None:
        """Start consuming without blocking the API event loop."""
        self._stop_event.clear()
        self._task = asyncio.create_task(asyncio.to_thread(self._consume))
        self._task.add_done_callback(self._on_task_done)

    def _on_task_done(self, task: asyncio.Task[None]) -> None:
        if self._stop_event.is_set():
            return
        try:
            task.result()
        except asyncio.CancelledError:
            logger.error("Kafka consumer task was cancelled unexpectedly")
        except Exception:
            logger.exception("Kafka consumer task failed")
        else:
            logger.error("Kafka consumer task exited unexpectedly")

    async def stop(self) -> None:
        """Stop consuming and wait for the worker to exit."""
        self._stop_event.set()
        if self._task is not None:
            await self._task
            self._task = None

    def _consume(self) -> None:
        consumer = Consumer(
            {
                "bootstrap.servers": os.getenv(
                    EnvironmentVariables.KAFKA_BOOTSTRAP_SERVERS,
                    "localhost:9092",
                ),
                "group.id": os.getenv(
                    EnvironmentVariables.KAFKA_CONSUMER_GROUP_ID,
                    "docpipe-api",
                ),
                "auto.offset.reset": "earliest",
                "enable.auto.commit": False,
                "enable.auto.offset.store": False,
            }
        )
        topic = os.getenv(EnvironmentVariables.KAFKA_TOPIC, "docpipe-poc")
        consumer.subscribe([topic])

        try:
            logger.info("Kafka consumer listening on topic %s", topic)
            while not self._stop_event.is_set():
                message = consumer.poll(1.0)
                if message is None:
                    continue
                if message.error():
                    if message.error().code() != KafkaError._PARTITION_EOF:
                        logger.error("Kafka consumer error: %s", message.error())
                    continue

                # Do not commit log-only messages; job-run handling will define success.
                logger.info(
                    "Received Kafka message topic=%s partition=%s offset=%s",
                    message.topic(),
                    message.partition(),
                    message.offset(),
                )
        finally:
            consumer.close()
