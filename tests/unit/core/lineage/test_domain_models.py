"""Unit tests for lineage domain models and port interfaces."""

import pyarrow as pa

from docpipe.core.lineage.domain.models import (
    LineageDataset,
    LineageEventType,
    LineageJob,
    LineageRun,
    SchemaField,
)
from docpipe.core.lineage.domain.ports import (
    ExecutionLifecycleObserverPort,
    LineagePublisherPort,
)
from docpipe.core.orchestration.models import (
    FlowAbortContext,
    FlowCompleteContext,
    FlowFailContext,
    FlowRunningContext,
    FlowStartContext,
    NodeCompleteContext,
    NodeFailContext,
    NodeSkipContext,
    NodeStartContext,
)


def test_lineage_event_type_values() -> None:
    """Verify all required OpenLineage event types exist in the enum."""
    assert LineageEventType.START == "START"
    assert LineageEventType.RUNNING == "RUNNING"
    assert LineageEventType.COMPLETE == "COMPLETE"
    assert LineageEventType.FAIL == "FAIL"
    assert LineageEventType.ABORT == "ABORT"
    assert LineageEventType.OTHER == "OTHER"


def test_schema_field_creation() -> None:
    """Verify SchemaField model instantiation."""
    field = SchemaField(name="content", type="STRING", description="Document text")
    assert field.name == "content"
    assert field.type == "STRING"
    assert field.description == "Document text"


def test_lineage_dataset_model() -> None:
    """Verify LineageDataset model instantiation and default facets."""
    dataset = LineageDataset(namespace="s3://bucket", name="docs/data")
    assert dataset.namespace == "s3://bucket"
    assert dataset.name == "docs/data"
    assert dataset.facets == {}

    custom_dataset = LineageDataset(
        namespace="duckdb://local",
        name="document-set/1",
        facets={"schema": {"fields": []}},
    )
    assert "schema" in custom_dataset.facets


def test_lineage_job_model() -> None:
    """Verify LineageJob model instantiation."""
    job = LineageJob(namespace="docpipe://local", name="test-flow")
    assert job.namespace == "docpipe://local"
    assert job.name == "test-flow"
    assert job.facets == {}


def test_lineage_run_model() -> None:
    """Verify LineageRun model instantiation."""
    run = LineageRun(run_id="run-123", status="Completed")
    assert run.run_id == "run-123"
    assert run.status == "Completed"
    assert run.facets == {}


def test_execution_event_contexts() -> None:
    """Verify context data structures passed to lifecycle observer."""
    flow_start = FlowStartContext(
        flow_id="f1",
        flow_name="test_flow",
        job_run_id="r1",
        flow_def={"flow_name": "test"},
    )
    assert flow_start.flow_id == "f1"

    table = pa.table({"col1": [1, 2]})
    flow_running = FlowRunningContext(
        flow_id="f1",
        flow_name="test_flow",
        job_run_id="r1",
        ingested_table=table,
        ingest_node_id="node_a",
    )
    assert flow_running.ingested_table is not None

    flow_complete = FlowCompleteContext(
        flow_id="f1",
        flow_name="test_flow",
        job_run_id="r1",
        flow_def={},
        output_tables=[table],
    )
    assert len(flow_complete.output_tables) == 1

    flow_fail = FlowFailContext(
        flow_id="f1",
        flow_name="test_flow",
        job_run_id="r1",
        error_message="failed step",
    )
    assert flow_fail.error_message == "failed step"

    flow_abort = FlowAbortContext(
        flow_id="f1",
        flow_name="test_flow",
        job_run_id="r1",
        reason="user canceled",
    )
    assert flow_abort.status == "Canceled"

    node_start = NodeStartContext(
        flow_id="f1",
        flow_name="test_flow",
        job_run_id="r1",
        node_id="n1",
        node_name="node1",
        operator_type="chunker",
    )
    assert node_start.node_id == "n1"

    node_complete = NodeCompleteContext(
        flow_id="f1",
        flow_name="test_flow",
        job_run_id="r1",
        node_id="n1",
        node_name="node1",
        operator_type="chunker",
    )
    assert node_complete.node_id == "n1"

    node_fail = NodeFailContext(
        flow_id="f1",
        flow_name="test_flow",
        job_run_id="r1",
        node_id="n1",
        node_name="node1",
        operator_type="chunker",
        error_message="chunker error",
    )
    assert node_fail.error_message == "chunker error"

    node_skip = NodeSkipContext(
        flow_id="f1",
        flow_name="test_flow",
        job_run_id="r1",
        node_id="n1",
        node_name="node1",
        operator_type="chunker",
        reason="empty input",
    )
    assert node_skip.reason == "empty input"


def test_port_subclassing() -> None:
    """Verify that concrete implementations can subclass publisher and observer ports."""

    class DummyPublisher(LineagePublisherPort):
        def publish(
            self,
            *,
            event_type: LineageEventType,
            run: LineageRun,
            job: LineageJob,
            inputs: list[LineageDataset] | None = None,
            outputs: list[LineageDataset] | None = None,
        ) -> None:
            pass

    publisher = DummyPublisher()
    assert isinstance(publisher, LineagePublisherPort)

    class DummyObserver(ExecutionLifecycleObserverPort):
        def on_flow_start(self, *, context: FlowStartContext) -> None:
            pass

        def on_flow_running(self, *, context: FlowRunningContext) -> None:
            pass

        def on_flow_complete(self, *, context: FlowCompleteContext) -> None:
            pass

        def on_flow_fail(self, *, context: FlowFailContext) -> None:
            pass

        def on_flow_abort(self, *, context: FlowAbortContext) -> None:
            pass

        def on_node_start(self, *, context: NodeStartContext) -> None:
            pass

        def on_node_complete(self, *, context: NodeCompleteContext) -> None:
            pass

        def on_node_fail(self, *, context: NodeFailContext) -> None:
            pass

        def on_node_skip(self, *, context: NodeSkipContext) -> None:
            pass

    observer = DummyObserver()
    assert isinstance(observer, ExecutionLifecycleObserverPort)
