"""Minimal Kafka consumer for the API POC.

Each message body is a job-run request. The consumer posts it to the
job-runs API and does not construct flows or jobs itself.
"""

from __future__ import annotations

import json
import os
import threading
import urllib.error
import urllib.request

from confluent_kafka import Consumer, KafkaError, Message

from docpipe.core.constants.constants import EnvironmentVariables
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger()

_DEFAULT_API_BASE_URL = "http://127.0.0.1:8080"
_JOB_RUNS_PATH = "/api/v1/job_runs"
_RETRY_SECONDS = 2


class _PermanentAPIError(Exception):
    """The API rejected the message. Retrying will not succeed."""


class _RetryableAPIError(Exception):
    """The API was unreachable or failed temporarily."""


class KafkaConsumerService:
    """Consume messages in a background thread owned by the API lifespan."""

    def __init__(self) -> None:
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
        topic = os.getenv(EnvironmentVariables.KAFKA_TOPIC, "docpipe-poc")
        while not self._stop_event.is_set():
            consumer = self._build_consumer()
            try:
                consumer.subscribe([topic])
                logger.info("Kafka consumer listening on topic %s", topic)
                while not self._stop_event.is_set():
                    message = consumer.poll(1.0)
                    if message is None:
                        continue
                    if message.error():
                        if message.error().code() != KafkaError._PARTITION_EOF:
                            logger.error("Kafka consumer error: %s", message.error())
                        continue
                    self._handle_message(consumer=consumer, message=message)
            except Exception:
                logger.exception("Kafka consumer error; reconnecting")
                if self._stop_event.wait(_RETRY_SECONDS):
                    return
            finally:
                consumer.close()

    def _build_consumer(self) -> Consumer:
        return Consumer(
            {
                "bootstrap.servers": os.environ[EnvironmentVariables.KAFKA_BOOTSTRAP_SERVERS],
                "group.id": os.getenv(
                    EnvironmentVariables.KAFKA_CONSUMER_GROUP_ID,
                    "docpipe-api",
                ),
                "auto.offset.reset": "earliest",
                "enable.auto.commit": False,
                "topic.metadata.refresh.interval.ms": 5000,
            }
        )

    def _handle_message(self, *, consumer: Consumer, message: Message) -> None:
        payload = message.value()
        if not payload:
            logger.error("Dropping empty Kafka message at offset %s", message.offset())
            consumer.commit(message=message, asynchronous=False)
            return

        while not self._stop_event.is_set():
            try:
                job_run_id = _post_job_run(payload=payload)
            except _PermanentAPIError as exc:
                logger.error(
                    "Dropping Kafka message topic=%s offset=%s: %s",
                    message.topic(),
                    message.offset(),
                    exc,
                )
                consumer.commit(message=message, asynchronous=False)
                return
            except _RetryableAPIError as exc:
                logger.warning(
                    "Job run API unavailable (%s); retrying topic=%s offset=%s",
                    exc,
                    message.topic(),
                    message.offset(),
                )
                if self._stop_event.wait(_RETRY_SECONDS):
                    return
                continue

            logger.info("Started Kafka job run %s", job_run_id)
            consumer.commit(message=message, asynchronous=False)
            return


def _post_job_run(*, payload: bytes) -> str:
    """POST one job-run request and return the created job_run_id."""
    api_base = os.getenv(EnvironmentVariables.DOCPIPE_API_BASE_URL, _DEFAULT_API_BASE_URL).rstrip("/")
    request = urllib.request.Request(
        url=f"{api_base}{_JOB_RUNS_PATH}",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        if 400 <= exc.code < 500:
            raise _PermanentAPIError(f"HTTP {exc.code}: {detail}") from exc
        raise _RetryableAPIError(f"HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise _RetryableAPIError(str(exc.reason)) from exc

    job_run_id = body.get("job_run_id")
    if not isinstance(job_run_id, str) or not job_run_id:
        raise _PermanentAPIError("job run response did not include job_run_id")
    return job_run_id
