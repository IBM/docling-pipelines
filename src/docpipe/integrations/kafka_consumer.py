"""Minimal Kafka consumer for the API POC."""

from __future__ import annotations

import json
import os
import threading

from confluent_kafka import Consumer

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
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Start consuming in a background thread."""
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._consume, name="kafka-consumer", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop consuming and wait for the worker to exit."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join()
            self._thread = None

    def _consume(self) -> None:
        consumer = Consumer(
            {
                "bootstrap.servers": os.environ[EnvironmentVariables.KAFKA_BOOTSTRAP_SERVERS],
                "group.id": os.getenv(
                    EnvironmentVariables.KAFKA_CONSUMER_GROUP_ID,
                    "docpipe-api",
                ),
                "auto.offset.reset": "earliest",
            }
        )
        topic = os.getenv(EnvironmentVariables.KAFKA_TOPIC, "docpipe-poc")

        try:
            consumer.subscribe([topic])
            logger.info("Kafka consumer listening on topic %s", topic)
            while not self._stop_event.is_set():
                message = consumer.poll(1.0)
                if message is None:
                    continue
                if message.error():
                    logger.error("Kafka consumer error: %s", message.error())
                    continue

                request_body = JobsAPIExecuteModel.model_validate(json.loads(message.value()))
                result = self._job_management_service.create_job_run_from_request(request_body=request_body)
                logger.info("Started Kafka job run %s", result[DocpipeConstants.JOB_RUN_ID])
        except Exception:
            logger.exception("Kafka consumer stopped after an error")
        finally:
            consumer.close()
