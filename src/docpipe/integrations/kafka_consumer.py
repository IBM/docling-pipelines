"""Minimal Kafka consumer for the API POC."""

from __future__ import annotations

import asyncio
import json
import os
import threading

from confluent_kafka import Consumer, KafkaError

from docpipe.api.dto.job_run_dto import JobsAPIExecuteModel
from docpipe.core.constants.constants import DocpipeConstants, EnvironmentVariables
from docpipe.core.job_management.application.services import JobManagementService
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger()


class KafkaConsumerService:
    """Consume messages in a background thread owned by the API lifespan."""

    def __init__(self, *, job_management_service: JobManagementService) -> None:
        self._job_management_service = job_management_service
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

                try:
                    request_body = JobsAPIExecuteModel.model_validate(json.loads(message.value()))
                    result = self._job_management_service.create_job_run_from_request(request_body=request_body)
                    job_run_id = result.get(DocpipeConstants.JOB_RUN_ID)
                    if not job_run_id:
                        raise RuntimeError("Job run creation did not return a job_run_id")

                    event_key = message.key()
                    logger.info(
                        "Started Kafka job run %s from event=%s topic=%s partition=%s offset=%s",
                        job_run_id,
                        event_key.decode("utf-8", errors="replace") if event_key else None,
                        message.topic(),
                        message.partition(),
                        message.offset(),
                    )
                    committed = consumer.commit(message=message, asynchronous=False)
                    if not committed or any(partition.err is not None for partition in committed):
                        raise RuntimeError("Kafka offset commit failed")
                except Exception:
                    logger.exception(
                        "Failed Kafka message topic=%s partition=%s offset=%s",
                        message.topic(),
                        message.partition(),
                        message.offset(),
                    )
                    raise
        finally:
            consumer.close()
