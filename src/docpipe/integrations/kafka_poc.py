"""Kafka POC.

`docpipe-poc` — each message body is posted to `POST /api/v1/job_runs`.
`docpipe-poc-status` — `{path, flow_id, status}` after that run finishes.
The result topic is separate so a completion does not start another run.
"""

from __future__ import annotations

import json
import os
import threading
import urllib.error
import urllib.request

from confluent_kafka import Consumer, KafkaError, Message, Producer

from docpipe.core.constants.constants import EnvironmentVariables
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger()

_API_BASE_URL = "http://127.0.0.1:8080"
_JOB_RUNS_PATH = "/api/v1/job_runs"
_INPUT_TOPIC = "docpipe-poc"
_OUTPUT_TOPIC = "docpipe-poc-status"


class KafkaConsumerService:
    """Background consumer started from the API lifespan."""

    def __init__(self) -> None:
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Start consuming."""
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="kafka-consumer", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop consuming."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join()
            self._thread = None

    def _run(self) -> None:
        topic = os.getenv(EnvironmentVariables.KAFKA_TOPIC, _INPUT_TOPIC)
        while not self._stop.is_set():
            consumer = Consumer(
                {
                    "bootstrap.servers": os.environ[EnvironmentVariables.KAFKA_BOOTSTRAP_SERVERS],
                    "group.id": os.getenv(EnvironmentVariables.KAFKA_CONSUMER_GROUP_ID, "docpipe-api"),
                    "auto.offset.reset": "earliest",
                    "enable.auto.commit": False,
                    "topic.metadata.refresh.interval.ms": 5000,
                }
            )
            try:
                consumer.subscribe([topic])
                logger.info("Kafka consumer listening on topic %s", topic)
                while not self._stop.is_set():
                    message = consumer.poll(1.0)
                    if message is None:
                        continue
                    if message.error():
                        if message.error().code() != KafkaError._PARTITION_EOF:
                            logger.error("Kafka consumer error: %s", message.error())
                        continue
                    self._post_and_commit(consumer=consumer, message=message)
            except Exception:
                logger.exception("Kafka consumer error; reconnecting")
                self._stop.wait(2)
            finally:
                consumer.close()

    def _post_and_commit(self, *, consumer: Consumer, message: Message) -> None:
        payload = message.value()
        if not payload:
            consumer.commit(message=message, asynchronous=False)
            return

        while not self._stop.is_set():
            try:
                job_run_id = _post_job_run(payload=payload)
            except urllib.error.HTTPError as exc:
                if 400 <= exc.code < 500:
                    logger.error("Dropping Kafka message offset=%s: HTTP %s", message.offset(), exc.code)
                    consumer.commit(message=message, asynchronous=False)
                    return
                logger.warning("Job run API HTTP %s; retrying", exc.code)
            except ValueError as exc:
                logger.error("Dropping Kafka message offset=%s: %s", message.offset(), exc)
                consumer.commit(message=message, asynchronous=False)
                return
            except urllib.error.URLError as exc:
                logger.warning("Job run API unavailable (%s); retrying", exc.reason)
            else:
                logger.info("Started Kafka job run %s", job_run_id)
                consumer.commit(message=message, asynchronous=False)
                return
            if self._stop.wait(2):
                return


def publish_flow_result(*, path: str, flow_id: str, status: str) -> None:
    """Publish one completion. No-op when Kafka is not configured."""
    bootstrap = os.getenv(EnvironmentVariables.KAFKA_BOOTSTRAP_SERVERS)
    if not bootstrap:
        return
    topic = os.getenv(EnvironmentVariables.KAFKA_OUTPUT_TOPIC, _OUTPUT_TOPIC)
    payload = json.dumps({"path": path, "flow_id": flow_id, "status": status}).encode("utf-8")
    producer = Producer({"bootstrap.servers": bootstrap})
    producer.produce(topic, key=path.encode("utf-8"), value=payload)
    if producer.flush(10):
        logger.error("Kafka flow result was not delivered for path=%s", path)
        return
    logger.info("Published flow result path=%s flow_id=%s status=%s", path, flow_id, status)


def _post_job_run(*, payload: bytes) -> str:
    api_base = os.getenv(EnvironmentVariables.DOCPIPE_API_BASE_URL, _API_BASE_URL).rstrip("/")
    request = urllib.request.Request(
        url=f"{api_base}{_JOB_RUNS_PATH}",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        body = json.loads(response.read().decode("utf-8"))
    job_run_id = body.get("job_run_id")
    if not isinstance(job_run_id, str) or not job_run_id:
        raise ValueError("job run response did not include job_run_id")
    return job_run_id
