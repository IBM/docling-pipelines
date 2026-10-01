"""Unit tests for OpenLineageExecutionObserver."""

from unittest.mock import MagicMock

import pytest

from docpipe.core.constants.constants import LineageConstants
from docpipe.core.lineage.adapters.openlineage.observer import OpenLineageExecutionObserver
from docpipe.core.lineage.application.lineage_service import LineageService
from docpipe.core.orchestration.models.execution_event_context import (
    FlowAbortContext,
    FlowCompleteContext,
    FlowFailContext,
    FlowRunningContext,
    FlowStartContext,
    NodeCompleteContext,
    NodeFailContext,
    NodeSkipContext,
    NodeStartContext,
    NodeTableSummary,
)


@pytest.fixture
def mock_service() -> MagicMock:
    return MagicMock(spec=LineageService)


@pytest.fixture
def flow_observer(mock_service: MagicMock) -> OpenLineageExecutionObserver:
    return OpenLineageExecutionObserver(lineage_service=mock_service, mode=LineageConstants.MODE_FLOW)


@pytest.fixture
def operator_observer(mock_service: MagicMock) -> OpenLineageExecutionObserver:
    return OpenLineageExecutionObserver(lineage_service=mock_service, mode=LineageConstants.MODE_OPERATOR)


@pytest.fixture
def sample_summary() -> NodeTableSummary:
    return NodeTableSummary(schema_fields=[("id", "string"), ("content", "string")], row_count=1)


class TestFlowModeObserver:
    """Flow mode emits only flow-level events; node events are no-ops."""

    def test_on_flow_start_delegates(
        self, flow_observer: OpenLineageExecutionObserver, mock_service: MagicMock
    ) -> None:
        context = FlowStartContext(flow_id="f1", flow_name="test", job_run_id="r1", flow_def={})
        flow_observer.on_flow_start(context=context)
        mock_service.emit_flow_start.assert_called_once_with(context=context)

    def test_on_flow_running_delegates(
        self, flow_observer: OpenLineageExecutionObserver, mock_service: MagicMock
    ) -> None:
        context = FlowRunningContext(flow_id="f1", flow_name="test", job_run_id="r1")
        flow_observer.on_flow_running(context=context)
        mock_service.emit_flow_running.assert_called_once_with(context=context)

    def test_on_flow_complete_delegates(
        self, flow_observer: OpenLineageExecutionObserver, mock_service: MagicMock
    ) -> None:
        context = FlowCompleteContext(flow_id="f1", flow_name="test", job_run_id="r1", flow_def={})
        flow_observer.on_flow_complete(context=context)
        mock_service.emit_flow_complete.assert_called_once_with(context=context)

    def test_on_flow_fail_delegates(self, flow_observer: OpenLineageExecutionObserver, mock_service: MagicMock) -> None:
        context = FlowFailContext(flow_id="f1", flow_name="test", job_run_id="r1", error_message="boom")
        flow_observer.on_flow_fail(context=context)
        mock_service.emit_flow_fail.assert_called_once_with(context=context)

    def test_on_flow_abort_delegates(
        self, flow_observer: OpenLineageExecutionObserver, mock_service: MagicMock
    ) -> None:
        context = FlowAbortContext(flow_id="f1", flow_name="test", job_run_id="r1")
        flow_observer.on_flow_abort(context=context)
        mock_service.emit_flow_abort.assert_called_once_with(context=context)

    def test_node_events_are_noop_in_flow_mode(
        self, flow_observer: OpenLineageExecutionObserver, mock_service: MagicMock
    ) -> None:
        flow_observer.on_node_start(
            context=NodeStartContext(
                flow_id="f1",
                flow_name="test",
                job_run_id="r1",
                node_id="n1",
                node_name="chunker",
                operator_type="chunker",
            )
        )
        flow_observer.on_node_complete(
            context=NodeCompleteContext(
                flow_id="f1",
                flow_name="test",
                job_run_id="r1",
                node_id="n1",
                node_name="chunker",
                operator_type="chunker",
            )
        )
        flow_observer.on_node_fail(
            context=NodeFailContext(
                flow_id="f1",
                flow_name="test",
                job_run_id="r1",
                node_id="n1",
                node_name="chunker",
                operator_type="chunker",
                error_message="err",
            )
        )
        flow_observer.on_node_skip(
            context=NodeSkipContext(
                flow_id="f1",
                flow_name="test",
                job_run_id="r1",
                node_id="n1",
                node_name="chunker",
                operator_type="chunker",
                reason="empty",
            )
        )
        mock_service.emit_node_start.assert_not_called()
        mock_service.emit_node_complete.assert_not_called()
        mock_service.emit_node_fail.assert_not_called()
        mock_service.emit_node_skip.assert_not_called()


class TestOperatorModeObserver:
    """Operator mode delegates all node events directly to the service."""

    def test_on_node_start_delegates(
        self,
        operator_observer: OpenLineageExecutionObserver,
        mock_service: MagicMock,
        sample_summary: NodeTableSummary,
    ) -> None:
        context = NodeStartContext(
            flow_id="f1",
            flow_name="test",
            job_run_id="r1",
            node_id="n1",
            node_name="chunker",
            operator_type="chunker",
            input_summary=sample_summary,
        )
        operator_observer.on_node_start(context=context)
        mock_service.emit_node_start.assert_called_once_with(context=context)

    def test_on_node_start_no_input_summary(
        self,
        operator_observer: OpenLineageExecutionObserver,
        mock_service: MagicMock,
    ) -> None:
        context = NodeStartContext(
            flow_id="f1",
            flow_name="test",
            job_run_id="r1",
            node_id="n1",
            node_name="chunker",
            operator_type="chunker",
        )
        operator_observer.on_node_start(context=context)
        mock_service.emit_node_start.assert_called_once_with(context=context)

    def test_on_node_complete_delegates(
        self,
        operator_observer: OpenLineageExecutionObserver,
        mock_service: MagicMock,
        sample_summary: NodeTableSummary,
    ) -> None:
        context = NodeCompleteContext(
            flow_id="f1",
            flow_name="test",
            job_run_id="r1",
            node_id="n1",
            node_name="chunker",
            operator_type="chunker",
            output_summaries=[sample_summary],
        )
        operator_observer.on_node_complete(context=context)
        mock_service.emit_node_complete.assert_called_once_with(context=context)

    def test_on_node_fail_delegates(
        self,
        operator_observer: OpenLineageExecutionObserver,
        mock_service: MagicMock,
        sample_summary: NodeTableSummary,
    ) -> None:
        context = NodeFailContext(
            flow_id="f1",
            flow_name="test",
            job_run_id="r1",
            node_id="n1",
            node_name="chunker",
            operator_type="chunker",
            error_message="error",
            input_summary=sample_summary,
        )
        operator_observer.on_node_fail(context=context)
        mock_service.emit_node_fail.assert_called_once_with(context=context)

    def test_on_node_fail_without_input_summary(
        self,
        operator_observer: OpenLineageExecutionObserver,
        mock_service: MagicMock,
    ) -> None:
        context = NodeFailContext(
            flow_id="f1",
            flow_name="test",
            job_run_id="r1",
            node_id="n2",
            node_name="embeddings",
            operator_type="embeddings",
            error_message="error",
        )
        operator_observer.on_node_fail(context=context)
        mock_service.emit_node_fail.assert_called_once_with(context=context)

    def test_on_node_skip_delegates(
        self,
        operator_observer: OpenLineageExecutionObserver,
        mock_service: MagicMock,
    ) -> None:
        context = NodeSkipContext(
            flow_id="f1",
            flow_name="test",
            job_run_id="r1",
            node_id="n1",
            node_name="chunker",
            operator_type="chunker",
            reason="empty input",
        )
        operator_observer.on_node_skip(context=context)
        mock_service.emit_node_skip.assert_called_once_with(context=context)
