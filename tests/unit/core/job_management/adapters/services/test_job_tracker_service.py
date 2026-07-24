"""
Unit tests for JobTrackerService.

Tests cover:
- Service lifecycle methods (start_tracking_job, end_job, get_job, get_job_run_stats)
- Final document counting logic (Phase 7)
- Status normalization
- Keyword-only argument compliance

Final document counting algorithm:
1. Failed documents (from any node's failed_docs list)
2. Completed documents (reached destination nodes, not failed)
3. Skipped documents (from ingest, neither completed nor failed)
"""

from unittest.mock import Mock

import pytest

from docpipe.core.constants.constants import ExecutionStatus
from docpipe.core.job_management.adapters.services.job_tracker_service import JobTrackerService
from docpipe.core.job_management.domain.models.job_stats import JobStats
from docpipe.core.job_management.domain.models.node_stats import NodeStats

# Test UUIDs (36 characters, hex format)
JOB_ID = "12345678-1234-1234-1234-123456789012"
JOB_RUN_ID = "87654321-4321-4321-4321-210987654321"
INGEST_NODE_ID = "a1111111-0000-0000-0000-000000000001"
TRANSFORM_NODE_ID = "b2222222-0000-0000-0000-000000000001"
DEST_NODE_ID_1 = "c3333333-0000-0000-0000-000000000001"
DEST_NODE_ID_2 = "c4444444-0000-0000-0000-000000000002"
NODE_ID_1 = "d5555555-0000-0000-0000-000000000001"
NODE_ID_2 = "d6666666-0000-0000-0000-000000000002"
BATCH_ID = "e1111111-0000-0000-0000-000000000001"


@pytest.fixture
def mock_store():
    """Create mock JobStatsStore."""
    return Mock()


@pytest.fixture
def mock_aggregator():
    """Create mock NodeStatsAggregator."""
    return Mock()


@pytest.fixture
def job_tracker_service(*, mock_store, mock_aggregator):
    """Create JobTrackerService with mocked dependencies."""
    return JobTrackerService(job_stats_store=mock_store, node_stats_aggregator=mock_aggregator)


@pytest.fixture
def sample_dag_linear():
    """Linear DAG: Ingest -> Transform -> Destination."""
    return [
        {"id": INGEST_NODE_ID, "input_edges": [], "output_edges": [TRANSFORM_NODE_ID]},
        {
            "id": TRANSFORM_NODE_ID,
            "input_edges": [INGEST_NODE_ID],
            "output_edges": [DEST_NODE_ID_1],
        },
        {"id": DEST_NODE_ID_1, "input_edges": [TRANSFORM_NODE_ID], "output_edges": []},
    ]


@pytest.fixture
def sample_dag_branching():
    """Branching DAG: Ingest -> Transform -> [Dest1, Dest2]."""
    return [
        {"id": INGEST_NODE_ID, "input_edges": [], "output_edges": [TRANSFORM_NODE_ID]},
        {
            "id": TRANSFORM_NODE_ID,
            "input_edges": [INGEST_NODE_ID],
            "output_edges": [DEST_NODE_ID_1, DEST_NODE_ID_2],
        },
        {"id": DEST_NODE_ID_1, "input_edges": [TRANSFORM_NODE_ID], "output_edges": []},
        {"id": DEST_NODE_ID_2, "input_edges": [TRANSFORM_NODE_ID], "output_edges": []},
    ]


class TestFinalDocumentCounting:
    """Test final document counting logic."""

    def test_all_documents_completed(self, *, job_tracker_service, sample_dag_linear):
        """Test when all documents complete successfully."""
        job_stats = JobStats(
            job_id=JOB_ID,
            job_run_id=JOB_RUN_ID,
            total_docs=3,
            node_stats={
                INGEST_NODE_ID: NodeStats(
                    node_id=INGEST_NODE_ID,
                    name="Ingest",
                    total_docs=["doc1", "doc2", "doc3"],
                    docs_completed=["doc1", "doc2", "doc3"],
                    failed_docs=[],
                    skipped_docs=[],
                ),
                TRANSFORM_NODE_ID: NodeStats(
                    node_id=TRANSFORM_NODE_ID,
                    name="Transform",
                    total_docs=["doc1", "doc2", "doc3"],
                    docs_completed=["doc1", "doc2", "doc3"],
                    failed_docs=[],
                    skipped_docs=[],
                ),
                DEST_NODE_ID_1: NodeStats(
                    node_id=DEST_NODE_ID_1,
                    name="Destination",
                    total_docs=["doc1", "doc2", "doc3"],
                    docs_completed=["doc1", "doc2", "doc3"],
                    failed_docs=[],
                    skipped_docs=[],
                ),
            },
        )

        job_tracker_service.determine_and_update_final_documents_count(job_stats=job_stats, dag_nodes=sample_dag_linear)

        assert job_stats.completed_docs == 3
        assert job_stats.failed_docs == 0
        assert job_stats.skipped_docs == 0
        assert job_stats.processed_docs == 3

    def test_some_documents_failed(self, *, job_tracker_service, sample_dag_linear):
        """Test when some documents fail during processing."""
        job_stats = JobStats(
            job_id=JOB_ID,
            job_run_id=JOB_RUN_ID,
            total_docs=3,
            node_stats={
                INGEST_NODE_ID: NodeStats(
                    node_id=INGEST_NODE_ID,
                    name="Ingest",
                    total_docs=["doc1", "doc2", "doc3"],
                    docs_completed=["doc1", "doc2", "doc3"],
                    failed_docs=[],
                    skipped_docs=[],
                ),
                TRANSFORM_NODE_ID: NodeStats(
                    node_id=TRANSFORM_NODE_ID,
                    name="Transform",
                    total_docs=["doc1", "doc2", "doc3"],
                    docs_completed=["doc1", "doc2"],
                    failed_docs=["doc3"],
                    skipped_docs=[],
                ),
                DEST_NODE_ID_1: NodeStats(
                    node_id=DEST_NODE_ID_1,
                    name="Destination",
                    total_docs=["doc1", "doc2"],
                    docs_completed=["doc1", "doc2"],
                    failed_docs=[],
                    skipped_docs=[],
                ),
            },
        )

        job_tracker_service.determine_and_update_final_documents_count(job_stats=job_stats, dag_nodes=sample_dag_linear)

        assert job_stats.completed_docs == 2
        assert job_stats.failed_docs == 1
        assert job_stats.skipped_docs == 0
        assert job_stats.processed_docs == 3

    def test_some_documents_skipped(self, *, job_tracker_service, sample_dag_linear):
        """Test when some documents are skipped (not processed)."""
        job_stats = JobStats(
            job_id=JOB_ID,
            job_run_id=JOB_RUN_ID,
            total_docs=5,
            node_stats={
                INGEST_NODE_ID: NodeStats(
                    node_id=INGEST_NODE_ID,
                    name="Ingest",
                    total_docs=["doc1", "doc2", "doc3", "doc4", "doc5"],
                    docs_completed=["doc1", "doc2", "doc3"],
                    failed_docs=[],
                    skipped_docs=[],
                ),
                TRANSFORM_NODE_ID: NodeStats(
                    node_id=TRANSFORM_NODE_ID,
                    name="Transform",
                    total_docs=["doc1", "doc2", "doc3"],
                    docs_completed=["doc1", "doc2", "doc3"],
                    failed_docs=[],
                    skipped_docs=[],
                ),
                DEST_NODE_ID_1: NodeStats(
                    node_id=DEST_NODE_ID_1,
                    name="Destination",
                    total_docs=["doc1", "doc2", "doc3"],
                    docs_completed=["doc1", "doc2", "doc3"],
                    failed_docs=[],
                    skipped_docs=[],
                ),
            },
        )

        job_tracker_service.determine_and_update_final_documents_count(job_stats=job_stats, dag_nodes=sample_dag_linear)

        assert job_stats.completed_docs == 3
        assert job_stats.failed_docs == 0
        assert job_stats.skipped_docs == 2
        assert job_stats.processed_docs == 5

    def test_mixed_outcomes(self, *, job_tracker_service, sample_dag_linear):
        """Test with mixed outcomes: completed, failed, and skipped."""
        job_stats = JobStats(
            job_id=JOB_ID,
            job_run_id=JOB_RUN_ID,
            total_docs=5,
            node_stats={
                INGEST_NODE_ID: NodeStats(
                    node_id=INGEST_NODE_ID,
                    name="Ingest",
                    total_docs=["doc1", "doc2", "doc3", "doc4", "doc5"],
                    docs_completed=["doc1", "doc2", "doc3", "doc4"],
                    failed_docs=[],
                    skipped_docs=[],
                ),
                TRANSFORM_NODE_ID: NodeStats(
                    node_id=TRANSFORM_NODE_ID,
                    name="Transform",
                    total_docs=["doc1", "doc2", "doc3", "doc4"],
                    docs_completed=["doc1", "doc2"],
                    failed_docs=["doc3"],
                    skipped_docs=[],
                ),
                DEST_NODE_ID_1: NodeStats(
                    node_id=DEST_NODE_ID_1,
                    name="Destination",
                    total_docs=["doc1", "doc2"],
                    docs_completed=["doc1", "doc2"],
                    failed_docs=[],
                    skipped_docs=[],
                ),
            },
        )

        job_tracker_service.determine_and_update_final_documents_count(job_stats=job_stats, dag_nodes=sample_dag_linear)

        assert job_stats.completed_docs == 2
        assert job_stats.failed_docs == 1
        assert job_stats.skipped_docs == 2
        assert job_stats.processed_docs == 5

    def test_multiple_destination_nodes(self, *, job_tracker_service, sample_dag_branching):
        """Test with multiple destination nodes (branching flow)."""
        job_stats = JobStats(
            job_id=JOB_ID,
            job_run_id=JOB_RUN_ID,
            total_docs=4,
            node_stats={
                INGEST_NODE_ID: NodeStats(
                    node_id=INGEST_NODE_ID,
                    name="Ingest",
                    total_docs=["doc1", "doc2", "doc3", "doc4"],
                    docs_completed=["doc1", "doc2", "doc3", "doc4"],
                    failed_docs=[],
                    skipped_docs=[],
                ),
                TRANSFORM_NODE_ID: NodeStats(
                    node_id=TRANSFORM_NODE_ID,
                    name="Transform",
                    total_docs=["doc1", "doc2", "doc3", "doc4"],
                    docs_completed=["doc1", "doc2", "doc3", "doc4"],
                    failed_docs=[],
                    skipped_docs=[],
                ),
                DEST_NODE_ID_1: NodeStats(
                    node_id=DEST_NODE_ID_1,
                    name="Destination 1",
                    total_docs=["doc1", "doc2"],
                    docs_completed=["doc1", "doc2"],
                    failed_docs=[],
                    skipped_docs=[],
                ),
                DEST_NODE_ID_2: NodeStats(
                    node_id=DEST_NODE_ID_2,
                    name="Destination 2",
                    total_docs=["doc3", "doc4"],
                    docs_completed=["doc3", "doc4"],
                    failed_docs=[],
                    skipped_docs=[],
                ),
            },
        )

        job_tracker_service.determine_and_update_final_documents_count(
            job_stats=job_stats, dag_nodes=sample_dag_branching
        )

        assert job_stats.completed_docs == 4
        assert job_stats.failed_docs == 0
        assert job_stats.skipped_docs == 0
        assert job_stats.processed_docs == 4

    def test_failed_takes_precedence_over_completed(self, *, job_tracker_service, sample_dag_branching):
        """Test that failed status takes precedence even if doc reached a destination."""
        job_stats = JobStats(
            job_id=JOB_ID,
            job_run_id=JOB_RUN_ID,
            total_docs=2,
            node_stats={
                INGEST_NODE_ID: NodeStats(
                    node_id=INGEST_NODE_ID,
                    name="Ingest",
                    total_docs=["doc1", "doc2"],
                    docs_completed=["doc1", "doc2"],
                    failed_docs=[],
                    skipped_docs=[],
                ),
                TRANSFORM_NODE_ID: NodeStats(
                    node_id=TRANSFORM_NODE_ID,
                    name="Transform",
                    total_docs=["doc1", "doc2"],
                    docs_completed=["doc1", "doc2"],
                    failed_docs=[],
                    skipped_docs=[],
                ),
                DEST_NODE_ID_1: NodeStats(
                    node_id=DEST_NODE_ID_1,
                    name="Destination 1",
                    total_docs=["doc1", "doc2"],
                    docs_completed=["doc1", "doc2"],
                    failed_docs=[],
                    skipped_docs=[],
                ),
                DEST_NODE_ID_2: NodeStats(
                    node_id=DEST_NODE_ID_2,
                    name="Destination 2",
                    total_docs=["doc1", "doc2"],
                    docs_completed=["doc2"],
                    failed_docs=["doc1"],
                    skipped_docs=[],
                ),
            },
        )

        job_tracker_service.determine_and_update_final_documents_count(
            job_stats=job_stats, dag_nodes=sample_dag_branching
        )

        assert job_stats.completed_docs == 1
        assert job_stats.failed_docs == 1
        assert job_stats.skipped_docs == 0
        assert job_stats.processed_docs == 2

    def test_empty_node_stats(self, *, job_tracker_service, sample_dag_linear):
        """Test with empty node stats."""
        job_stats = JobStats(job_id=JOB_ID, job_run_id=JOB_RUN_ID, total_docs=0, node_stats={})

        job_tracker_service.determine_and_update_final_documents_count(job_stats=job_stats, dag_nodes=sample_dag_linear)

        assert job_stats.completed_docs == 0
        assert job_stats.failed_docs == 0
        assert job_stats.skipped_docs == 0
        assert job_stats.processed_docs == 0

    def test_no_destination_nodes(self, *, job_tracker_service):
        """Test when DAG has no destination nodes (all nodes have output edges)."""
        dag_nodes = [
            {"id": NODE_ID_1, "input_edges": [], "output_edges": [NODE_ID_2]},
            {"id": NODE_ID_2, "input_edges": [NODE_ID_1], "output_edges": [NODE_ID_1]},
        ]

        job_stats = JobStats(
            job_id=JOB_ID,
            job_run_id=JOB_RUN_ID,
            total_docs=2,
            node_stats={
                NODE_ID_1: NodeStats(
                    node_id=NODE_ID_1,
                    name="Node 1",
                    total_docs=["doc1", "doc2"],
                    docs_completed=["doc1", "doc2"],
                    failed_docs=[],
                    skipped_docs=[],
                )
            },
        )

        job_tracker_service.determine_and_update_final_documents_count(job_stats=job_stats, dag_nodes=dag_nodes)

        assert job_stats.completed_docs == 0
        assert job_stats.failed_docs == 0
        assert job_stats.skipped_docs == 2
        assert job_stats.processed_docs == 2


class TestHelperMethods:
    """Test individual helper methods."""

    def test_mark_failed_documents(self, *, job_tracker_service):
        """Test _mark_failed_documents helper."""
        job_stats = JobStats(
            job_id=JOB_ID,
            job_run_id=JOB_RUN_ID,
            node_stats={
                NODE_ID_1: NodeStats(node_id=NODE_ID_1, name="Node 1", failed_docs=["doc1", "doc2"]),
                NODE_ID_2: NodeStats(node_id=NODE_ID_2, name="Node 2", failed_docs=["doc3"]),
            },
        )

        final_docs_status = {}
        job_tracker_service._mark_failed_documents(job_stats=job_stats, final_docs_status=final_docs_status)

        assert final_docs_status == {
            "doc1": "FAILED",
            "doc2": "FAILED",
            "doc3": "FAILED",
        }

    def test_identify_ingest_and_destination_nodes(self, *, job_tracker_service, sample_dag_linear):
        """Test _identify_ingest_and_destination_nodes helper."""
        ingest_id, dest_ids = job_tracker_service._identify_ingest_and_destination_nodes(dag_nodes=sample_dag_linear)

        assert ingest_id == INGEST_NODE_ID
        assert dest_ids == [DEST_NODE_ID_1]

    def test_mark_completed_documents(self, *, job_tracker_service):
        """Test _mark_completed_documents helper."""
        job_stats = JobStats(
            job_id=JOB_ID,
            job_run_id=JOB_RUN_ID,
            node_stats={
                DEST_NODE_ID_1: NodeStats(
                    node_id=DEST_NODE_ID_1,
                    name="Destination",
                    docs_completed=["doc1", "doc2", "doc3"],
                )
            },
        )

        final_docs_status = {"doc3": "FAILED"}
        job_tracker_service._mark_completed_documents(
            job_stats=job_stats,
            destination_node_ids=[DEST_NODE_ID_1],
            final_docs_status=final_docs_status,
        )

        assert final_docs_status == {
            "doc1": "COMPLETED",
            "doc2": "COMPLETED",
            "doc3": "FAILED",
        }

    def test_mark_skipped_documents(self, *, job_tracker_service):
        """Test _mark_skipped_documents helper."""
        job_stats = JobStats(
            job_id=JOB_ID,
            job_run_id=JOB_RUN_ID,
            node_stats={
                INGEST_NODE_ID: NodeStats(
                    node_id=INGEST_NODE_ID,
                    name="Ingest",
                    total_docs=["doc1", "doc2", "doc3", "doc4"],
                )
            },
        )

        final_docs_status = {"doc1": "COMPLETED", "doc2": "FAILED"}

        job_tracker_service._mark_skipped_documents(
            job_stats=job_stats,
            ingest_node_id=INGEST_NODE_ID,
            final_docs_status=final_docs_status,
        )

        assert final_docs_status == {
            "doc1": "COMPLETED",
            "doc2": "FAILED",
            "doc3": "SKIPPED",
            "doc4": "SKIPPED",
        }


class TestStartTrackingJob:
    """Test start_tracking_job method."""

    def test_start_tracking_job_basic(self, *, job_tracker_service, mock_store):
        """Start tracking creates initial job stats."""
        job_tracker_service.start_tracking_job(
            job_id=JOB_ID,
            job_run_id=JOB_RUN_ID,
            flow_name="test_flow",
            user_id="test_user",
        )

        # Verify store_job_stats was called
        assert mock_store.store_job_stats.called
        call_args = mock_store.store_job_stats.call_args
        job_stats = call_args[0][0]

        assert job_stats.job_id == JOB_ID
        assert job_stats.job_run_id == JOB_RUN_ID
        assert job_stats.flow_id == "test_flow"
        assert job_stats.user_id == "test_user"
        assert job_stats.status == ExecutionStatus.RUNNING
        assert job_stats.start_time is not None

    def test_start_tracking_job_default_user(self, *, job_tracker_service, mock_store):
        """Start tracking with no user_id uses default."""
        job_tracker_service.start_tracking_job(job_id=JOB_ID, job_run_id=JOB_RUN_ID, flow_name="test_flow")

        call_args = mock_store.store_job_stats.call_args
        job_stats = call_args[0][0]

        assert job_stats.user_id is None


class TestEndJob:
    """Test end_job method."""

    def test_end_job_completed(self, *, job_tracker_service, mock_store):
        """End job with COMPLETED status."""
        # Setup mock
        job_stats = JobStats(
            job_id=JOB_ID,
            job_run_id=JOB_RUN_ID,
            status=ExecutionStatus.RUNNING.value,
            start_time=1000,
        )
        mock_store.get_job_stats.return_value = job_stats

        job_tracker_service.end_job(job_run_id=JOB_RUN_ID, status=ExecutionStatus.COMPLETED)

        # Verify store_job_stats was called with updated stats
        assert mock_store.store_job_stats.called
        call_args = mock_store.store_job_stats.call_args
        updated_stats = call_args[0][0]

        assert updated_stats.status == ExecutionStatus.COMPLETED
        assert updated_stats.end_time is not None
        assert updated_stats.duration is not None

    def test_end_job_failed(self, *, job_tracker_service, mock_store):
        """End job with FAILED status."""
        job_stats = JobStats(
            job_id=JOB_ID,
            job_run_id=JOB_RUN_ID,
            status=ExecutionStatus.RUNNING.value,
            start_time=1000,
        )
        mock_store.get_job_stats.return_value = job_stats

        job_tracker_service.end_job(
            job_run_id=JOB_RUN_ID,
            status=ExecutionStatus.FAILED,
            job_run_stats={"message": "Test error"},
        )

        call_args = mock_store.store_job_stats.call_args
        updated_stats = call_args[0][0]

        assert updated_stats.status == ExecutionStatus.FAILED
        assert updated_stats.message == "Test error"

    def test_end_job_canceled(self, *, job_tracker_service, mock_store):
        """End job with CANCELED status."""
        job_stats = JobStats(
            job_id=JOB_ID,
            job_run_id=JOB_RUN_ID,
            status=ExecutionStatus.RUNNING.value,
            start_time=1000,
        )
        mock_store.get_job_stats.return_value = job_stats

        job_tracker_service.end_job(job_run_id=JOB_RUN_ID, status=ExecutionStatus.CANCELED)

        call_args = mock_store.store_job_stats.call_args
        updated_stats = call_args[0][0]

        assert updated_stats.status == ExecutionStatus.CANCELED

    def test_end_job_not_found(self, *, job_tracker_service, mock_store):
        """End job raises JobRunNotFoundException if job not found."""
        mock_store.get_job_stats.return_value = None

        from docpipe.exceptions.docpipe_exceptions import JobRunNotFoundException

        with pytest.raises(JobRunNotFoundException, match="Job run not found"):
            job_tracker_service.end_job(job_run_id=JOB_RUN_ID, status=ExecutionStatus.COMPLETED)


class TestGetJob:
    """Test get_job method with aggregation options."""

    def test_get_job_with_node_stats(self, *, job_tracker_service, mock_store, mock_aggregator):
        """Get job with aggregated node stats."""
        job_stats = JobStats(job_id=JOB_ID, job_run_id=JOB_RUN_ID, status=ExecutionStatus.RUNNING)
        mock_store.get_job_stats.return_value = job_stats

        aggregated_node_stats = {
            INGEST_NODE_ID: NodeStats(
                node_id=INGEST_NODE_ID,
                name="TestNode",
                node_status=ExecutionStatus.COMPLETED,
            )
        }
        mock_aggregator.get_aggregated_node_stats.return_value = aggregated_node_stats

        result = job_tracker_service.get_job(job_run_id=JOB_RUN_ID, include_node_stats=True, include_batch_stats=False)

        assert result is not None
        assert result.node_stats == aggregated_node_stats
        assert result.batch_node_stats == {}
        assert mock_aggregator.get_aggregated_node_stats.called

    def test_get_job_with_batch_stats(self, *, job_tracker_service, mock_store, mock_aggregator):
        """Get job with batch-level node stats."""
        job_stats = JobStats(job_id=JOB_ID, job_run_id=JOB_RUN_ID, status=ExecutionStatus.RUNNING)
        mock_store.get_job_stats.return_value = job_stats

        batch_node_stats = {
            INGEST_NODE_ID: {
                BATCH_ID: NodeStats(
                    node_id=INGEST_NODE_ID,
                    name="TestNode",
                    batch_id=BATCH_ID,
                    batch_num=0,
                )
            }
        }
        mock_aggregator.get_batch_node_stats.return_value = batch_node_stats

        result = job_tracker_service.get_job(job_run_id=JOB_RUN_ID, include_node_stats=False, include_batch_stats=True)

        assert result is not None
        assert result.node_stats == {}
        assert result.batch_node_stats == batch_node_stats
        assert mock_aggregator.get_batch_node_stats.called

    def test_get_job_without_aggregation(self, *, job_tracker_service, mock_store, mock_aggregator):
        """Get job without any aggregation."""
        job_stats = JobStats(job_id=JOB_ID, job_run_id=JOB_RUN_ID, status=ExecutionStatus.RUNNING)
        mock_store.get_job_stats.return_value = job_stats

        result = job_tracker_service.get_job(job_run_id=JOB_RUN_ID, include_node_stats=False, include_batch_stats=False)

        assert result is not None
        assert result.node_stats == {}
        assert result.batch_node_stats == {}
        assert not mock_aggregator.get_aggregated_node_stats.called
        assert not mock_aggregator.get_batch_node_stats.called

    def test_get_job_not_found(self, *, job_tracker_service, mock_store):
        """Get job returns None if not found."""
        mock_store.get_job_stats.return_value = None

        result = job_tracker_service.get_job(job_run_id=JOB_RUN_ID)

        assert result is None


class TestGetJobRunStats:
    """Test get_job_run_stats method (lightweight retrieval)."""

    def test_get_job_run_stats_basic(self, *, job_tracker_service, mock_store):
        """Get job run stats without aggregation."""
        job_stats = JobStats(job_id=JOB_ID, job_run_id=JOB_RUN_ID, status=ExecutionStatus.RUNNING)
        mock_store.get_job_stats.return_value = job_stats

        result = job_tracker_service.get_job_run_stats(job_run_id=JOB_RUN_ID)

        assert result is not None
        assert result.job_run_id == JOB_RUN_ID
        assert mock_store.get_job_stats.called

    def test_get_job_run_stats_not_found(self, *, job_tracker_service, mock_store):
        """Get job run stats returns None if not found."""
        mock_store.get_job_stats.return_value = None

        result = job_tracker_service.get_job_run_stats(job_run_id=JOB_RUN_ID)

        assert result is None


class TestNormalizeExecutionStatus:
    """Test normalize_execution_status static method."""

    def test_normalize_enum_value(self, *, job_tracker_service):
        """Normalize ExecutionStatus enum."""
        result = job_tracker_service.normalize_execution_status(ExecutionStatus.COMPLETED)
        assert result == ExecutionStatus.COMPLETED

    def test_normalize_string_exact(self, *, job_tracker_service):
        """Normalize exact string match."""
        result = job_tracker_service.normalize_execution_status("Completed")
        assert result == ExecutionStatus.COMPLETED

    def test_normalize_string_uppercase(self, *, job_tracker_service):
        """Normalize uppercase string via enum key lookup."""
        result = job_tracker_service.normalize_execution_status("COMPLETED")
        assert result == ExecutionStatus.COMPLETED

    def test_normalize_string_case_insensitive(self, *, job_tracker_service):
        """Normalize case-insensitive string."""
        result = job_tracker_service.normalize_execution_status("completed")
        assert result == ExecutionStatus.COMPLETED

    def test_normalize_string_with_spaces(self, *, job_tracker_service):
        """Normalize string with spaces."""
        result = job_tracker_service.normalize_execution_status("  Completed  ")
        assert result == ExecutionStatus.COMPLETED

    def test_normalize_invalid_status(self, *, job_tracker_service):
        """Normalize invalid status raises ValueError."""
        with pytest.raises(ValueError, match="Invalid status"):
            job_tracker_service.normalize_execution_status("INVALID_STATUS")

    def test_normalize_empty_status(self, *, job_tracker_service):
        """Normalize empty status raises ValueError."""
        with pytest.raises(ValueError, match="Invalid status: empty value"):
            job_tracker_service.normalize_execution_status("")


class TestStartNodeExecution:
    """Test start_node_execution method."""

    def test_start_node_execution_non_batch(self, *, job_tracker_service, mock_store):
        """Start node execution without batch context."""
        job_tracker_service.start_node_execution(
            job_run_id=JOB_RUN_ID,
            node_id=INGEST_NODE_ID,
            node_name="Ingest",
            total_docs=["doc1", "doc2", "doc3"],
        )

        assert mock_store.store_node_stats.called
        call_args = mock_store.store_node_stats.call_args
        node_stats = call_args[1]["node_stats"]

        assert node_stats.node_id == INGEST_NODE_ID
        assert node_stats.name == "Ingest"
        assert node_stats.node_status == ExecutionStatus.RUNNING.value
        assert node_stats.total_docs == ["doc1", "doc2", "doc3"]
        assert node_stats.batch_id is None
        assert node_stats.batch_num is None

    def test_start_node_execution_with_batch(self, *, job_tracker_service, mock_store):
        """Start node execution with batch context."""
        job_tracker_service.start_node_execution(
            job_run_id=JOB_RUN_ID,
            node_id=TRANSFORM_NODE_ID,
            node_name="Transform",
            total_docs=["doc1", "doc2"],
            batch_id=BATCH_ID,
            batch_num=0,
        )

        call_args = mock_store.store_node_stats.call_args
        node_stats = call_args[1]["node_stats"]

        assert node_stats.batch_id == BATCH_ID
        assert node_stats.batch_num == 0


class TestCompleteNodeExecution:
    """Test complete_node_execution method."""

    def test_complete_node_execution_success(self, *, job_tracker_service, mock_store):
        """Complete node execution successfully."""
        # Setup existing node with realistic timestamp
        import time

        current_time = int(time.time())
        existing_node = NodeStats(
            node_id=INGEST_NODE_ID,
            name="Ingest",
            start_time=current_time - 10,  # Started 10 seconds ago
            total_docs=["doc1", "doc2", "doc3"],
            node_status=ExecutionStatus.RUNNING.value,
        )
        mock_store.get_node_stats_by_batch_and_node.return_value = existing_node

        job_tracker_service.complete_node_execution(
            job_run_id=JOB_RUN_ID,
            node_id=INGEST_NODE_ID,
            node_name="Ingest",
            docs_completed=["doc1", "doc2", "doc3"],
            failed_docs=[],
            skipped_docs=[],
            col_names=["col1", "col2"],
            node_status=ExecutionStatus.COMPLETED.value,
        )

        assert mock_store.store_node_stats.called
        call_args = mock_store.store_node_stats.call_args
        node_stats = call_args[1]["node_stats"]

        assert node_stats.node_status == ExecutionStatus.COMPLETED.value
        assert node_stats.docs_completed == ["doc1", "doc2", "doc3"]
        assert node_stats.docs_completed_count == 3
        assert node_stats.end_time is not None
        assert node_stats.time_taken is not None

    def test_complete_node_execution_with_failures(self, *, job_tracker_service, mock_store):
        """Complete node execution with some failures."""
        import time

        current_time = int(time.time())
        existing_node = NodeStats(
            node_id=TRANSFORM_NODE_ID,
            name="Transform",
            start_time=current_time - 10,
            total_docs=["doc1", "doc2", "doc3"],
            node_status=ExecutionStatus.RUNNING.value,
        )
        mock_store.get_node_stats_by_batch_and_node.return_value = existing_node

        job_tracker_service.complete_node_execution(
            job_run_id=JOB_RUN_ID,
            node_id=TRANSFORM_NODE_ID,
            node_name="Transform",
            docs_completed=["doc1", "doc2"],
            failed_docs=["doc3"],
            skipped_docs=[],
            col_names=["col1"],
            node_status=ExecutionStatus.COMPLETED.value,
        )

        call_args = mock_store.store_node_stats.call_args
        node_stats = call_args[1]["node_stats"]

        assert node_stats.docs_completed_count == 2
        assert node_stats.failed_docs == ["doc3"]
        assert "1 failed" in node_stats.error

    def test_complete_node_execution_with_batch(self, *, job_tracker_service, mock_store):
        """Complete node execution with batch context."""
        import time

        current_time = int(time.time())
        existing_node = NodeStats(
            node_id=TRANSFORM_NODE_ID,
            name="Transform",
            start_time=current_time - 10,
            total_docs=["doc1", "doc2"],
            node_status=ExecutionStatus.RUNNING.value,
            batch_id=BATCH_ID,
            batch_num=0,
        )
        mock_store.get_node_stats_by_batch_and_node.return_value = existing_node

        job_tracker_service.complete_node_execution(
            job_run_id=JOB_RUN_ID,
            node_id=TRANSFORM_NODE_ID,
            node_name="Transform",
            docs_completed=["doc1", "doc2"],
            failed_docs=[],
            skipped_docs=[],
            col_names=["col1"],
            node_status=ExecutionStatus.COMPLETED.value,
            batch_id=BATCH_ID,
            batch_num=0,
        )

        call_args = mock_store.store_node_stats.call_args
        node_stats = call_args[1]["node_stats"]

        assert node_stats.batch_id == BATCH_ID
        assert node_stats.batch_num == 0

    def test_complete_node_execution_not_started(self, *, job_tracker_service, mock_store):
        """Complete node execution raises error if not started."""
        mock_store.get_node_stats_by_batch_and_node.return_value = None

        with pytest.raises(ValueError, match="Node execution was not started"):
            job_tracker_service.complete_node_execution(
                job_run_id=JOB_RUN_ID,
                node_id=INGEST_NODE_ID,
                node_name="Ingest",
                docs_completed=["doc1"],
                failed_docs=[],
                skipped_docs=[],
                col_names=[],
                node_status=ExecutionStatus.COMPLETED.value,
            )


class TestFailNodeExecution:
    """Test fail_node_execution method."""

    def test_fail_node_execution_with_exception(self, *, job_tracker_service, mock_store):
        """Fail node execution with exception."""
        import time

        current_time = int(time.time())
        existing_node = NodeStats(
            node_id=TRANSFORM_NODE_ID,
            name="Transform",
            start_time=current_time - 10,
            total_docs=["doc1", "doc2"],
            node_status=ExecutionStatus.RUNNING.value,
        )
        mock_store.get_node_stats_by_batch_and_node.return_value = existing_node

        test_exception = ValueError("Test error message")
        job_tracker_service.fail_node_execution(
            job_run_id=JOB_RUN_ID,
            node_id=TRANSFORM_NODE_ID,
            node_name="Transform",
            exception=test_exception,
        )

        assert mock_store.store_node_stats.called
        call_args = mock_store.store_node_stats.call_args
        node_stats = call_args[1]["node_stats"]

        assert node_stats.node_status == ExecutionStatus.FAILED.value
        assert "Test error message" in node_stats.error
        assert node_stats.docs_completed_count == 0

    def test_fail_node_execution_with_error_string(self, *, job_tracker_service, mock_store):
        """Fail node execution with error string."""
        import time

        current_time = int(time.time())
        existing_node = NodeStats(
            node_id=TRANSFORM_NODE_ID,
            name="Transform",
            start_time=current_time - 10,
            total_docs=["doc1"],
            node_status=ExecutionStatus.RUNNING.value,
        )
        mock_store.get_node_stats_by_batch_and_node.return_value = existing_node

        job_tracker_service.fail_node_execution(
            job_run_id=JOB_RUN_ID,
            node_id=TRANSFORM_NODE_ID,
            node_name="Transform",
            error="Custom error message",
        )

        call_args = mock_store.store_node_stats.call_args
        node_stats = call_args[1]["node_stats"]

        assert node_stats.error == "Custom error message"

    def test_fail_node_execution_with_batch(self, *, job_tracker_service, mock_store):
        """Fail node execution with batch context."""
        import time

        current_time = int(time.time())
        existing_node = NodeStats(
            node_id=TRANSFORM_NODE_ID,
            name="Transform",
            start_time=current_time - 10,
            total_docs=["doc1"],
            node_status=ExecutionStatus.RUNNING.value,
            batch_id=BATCH_ID,
            batch_num=0,
        )
        mock_store.get_node_stats_by_batch_and_node.return_value = existing_node

        job_tracker_service.fail_node_execution(
            job_run_id=JOB_RUN_ID,
            node_id=TRANSFORM_NODE_ID,
            node_name="Transform",
            error="Batch failed",
            batch_id=BATCH_ID,
            batch_num=0,
        )

        call_args = mock_store.store_node_stats.call_args
        node_stats = call_args[1]["node_stats"]

        assert node_stats.batch_id == BATCH_ID
        assert node_stats.batch_num == 0

    def test_fail_node_execution_no_error(self, *, job_tracker_service, mock_store):
        """Fail node execution raises error if no exception or error provided."""
        with pytest.raises(ValueError, match="Either exception or error must be provided"):
            job_tracker_service.fail_node_execution(
                job_run_id=JOB_RUN_ID, node_id=TRANSFORM_NODE_ID, node_name="Transform"
            )


class TestCancelNodeExecution:
    """Test cancel_node_execution method."""

    def test_cancel_node_execution_basic(self, *, job_tracker_service, mock_store):
        """Cancel node execution."""
        import time

        current_time = int(time.time())
        existing_node = NodeStats(
            node_id=TRANSFORM_NODE_ID,
            name="Transform",
            start_time=current_time - 10,
            total_docs=["doc1", "doc2"],
            node_status=ExecutionStatus.RUNNING.value,
        )
        mock_store.get_node_stats_by_batch_and_node.return_value = existing_node

        job_tracker_service.cancel_node_execution(
            job_run_id=JOB_RUN_ID, node_id=TRANSFORM_NODE_ID, node_name="Transform"
        )

        assert mock_store.store_node_stats.called
        call_args = mock_store.store_node_stats.call_args
        node_stats = call_args[1]["node_stats"]

        assert node_stats.node_status == ExecutionStatus.CANCELED.value
        assert node_stats.docs_completed_count == 0

    def test_cancel_node_execution_with_batch(self, *, job_tracker_service, mock_store):
        """Cancel node execution with batch context."""
        import time

        current_time = int(time.time())
        existing_node = NodeStats(
            node_id=TRANSFORM_NODE_ID,
            name="Transform",
            start_time=current_time - 10,
            total_docs=["doc1"],
            node_status=ExecutionStatus.RUNNING.value,
            batch_id=BATCH_ID,
            batch_num=0,
        )
        mock_store.get_node_stats_by_batch_and_node.return_value = existing_node

        job_tracker_service.cancel_node_execution(
            job_run_id=JOB_RUN_ID,
            node_id=TRANSFORM_NODE_ID,
            node_name="Transform",
            batch_id=BATCH_ID,
            batch_num=0,
        )

        call_args = mock_store.store_node_stats.call_args
        node_stats = call_args[1]["node_stats"]

        assert node_stats.batch_id == BATCH_ID
        assert node_stats.batch_num == 0


class TestAbortNodeExecution:
    """Test abort_node_execution method."""

    def test_abort_node_execution_basic(self, *, job_tracker_service, mock_store):
        """Abort node execution with reason."""
        import time

        current_time = int(time.time())
        existing_node = NodeStats(
            node_id=TRANSFORM_NODE_ID,
            name="Transform",
            start_time=current_time - 10,
            total_docs=["doc1", "doc2"],
            node_status=ExecutionStatus.RUNNING.value,
        )
        mock_store.get_node_stats_by_batch_and_node.return_value = existing_node

        job_tracker_service.abort_node_execution(
            job_run_id=JOB_RUN_ID,
            node_id=TRANSFORM_NODE_ID,
            node_name="Transform",
            reason="Upstream failure",
        )

        assert mock_store.store_node_stats.called
        call_args = mock_store.store_node_stats.call_args
        node_stats = call_args[1]["node_stats"]

        assert node_stats.node_status == ExecutionStatus.ABORTED.value
        assert node_stats.error == "Upstream failure"
        assert node_stats.docs_completed_count == 0


class TestSkipNodeExecution:
    """Test skip_node_execution method."""

    def test_skip_node_execution_basic(self, *, job_tracker_service, mock_store):
        """Skip node execution with reason."""
        import time

        current_time = int(time.time())
        existing_node = NodeStats(
            node_id=TRANSFORM_NODE_ID,
            name="Transform",
            start_time=current_time - 10,
            total_docs=["doc1"],
            node_status=ExecutionStatus.RUNNING.value,
        )
        mock_store.get_node_stats_by_batch_and_node.return_value = existing_node

        job_tracker_service.skip_node_execution(
            job_run_id=JOB_RUN_ID,
            node_id=TRANSFORM_NODE_ID,
            node_name="Transform",
            reason="No documents to process",
            col_names=["col1"],
        )

        assert mock_store.store_node_stats.called
        call_args = mock_store.store_node_stats.call_args
        node_stats = call_args[1]["node_stats"]

        assert node_stats.node_status == ExecutionStatus.SKIPPED.value
        assert node_stats.error == "No documents to process"
        assert node_stats.col_names == ["col1"]

    def test_fail_node_execution_metadata_structure(self, *, job_tracker_service, mock_store):
        """Verify fail_node_execution creates proper nested metadata structure."""
        import time

        from docpipe.core.constants.constants import Metrics

        current_time = int(time.time())
        existing_node = NodeStats(
            node_id=TRANSFORM_NODE_ID,
            name="Transform",
            start_time=current_time - 10,
            total_docs=["doc1"],
            node_status=ExecutionStatus.RUNNING.value,
        )
        mock_store.get_node_stats_by_batch_and_node.return_value = existing_node

        job_tracker_service.fail_node_execution(
            job_run_id=JOB_RUN_ID,
            node_id=TRANSFORM_NODE_ID,
            node_name="Transform",
            error="Test failure",
        )

        call_args = mock_store.store_node_stats.call_args
        node_stats = call_args[1]["node_stats"]

        # Verify proper nested structure
        assert node_stats.node_metadata is not None
        assert "id" in node_stats.node_metadata
        assert "operator" in node_stats.node_metadata
        assert "node_metadata" in node_stats.node_metadata
        assert node_stats.node_metadata["id"] == TRANSFORM_NODE_ID
        assert node_stats.node_metadata["operator"] == "Transform"
        assert Metrics.External.NODE_STATUS in node_stats.node_metadata["node_metadata"]
        assert node_stats.node_metadata["node_metadata"][Metrics.External.NODE_STATUS] == ExecutionStatus.FAILED.value

    def test_skip_node_execution_metadata_structure(self, *, job_tracker_service, mock_store):
        """Verify skip_node_execution creates proper nested metadata structure."""
        import time

        from docpipe.core.constants.constants import Metrics

        current_time = int(time.time())
        existing_node = NodeStats(
            node_id=TRANSFORM_NODE_ID,
            name="Transform",
            start_time=current_time - 10,
            total_docs=["doc1", "doc2"],
            node_status=ExecutionStatus.RUNNING.value,
        )
        mock_store.get_node_stats_by_batch_and_node.return_value = existing_node

        job_tracker_service.skip_node_execution(
            job_run_id=JOB_RUN_ID,
            node_id=TRANSFORM_NODE_ID,
            node_name="Transform",
            reason="Skipped for testing",
            col_names=["col1"],
        )

        call_args = mock_store.store_node_stats.call_args
        node_stats = call_args[1]["node_stats"]

        # Verify proper nested structure
        assert node_stats.node_metadata is not None
        assert "id" in node_stats.node_metadata
        assert "operator" in node_stats.node_metadata
        assert "node_metadata" in node_stats.node_metadata
        assert node_stats.node_metadata["id"] == TRANSFORM_NODE_ID
        assert node_stats.node_metadata["operator"] == "Transform"
        assert Metrics.External.NODE_STATUS in node_stats.node_metadata["node_metadata"]
        assert node_stats.node_metadata["node_metadata"][Metrics.External.NODE_STATUS] == ExecutionStatus.SKIPPED.value
        assert Metrics.External.TOTAL_DOCS in node_stats.node_metadata["node_metadata"]
        assert node_stats.node_metadata["node_metadata"][Metrics.External.TOTAL_DOCS] == 2


class TestUpdateNodeStats:
    """Test update_node_stats merge behavior."""

    def test_update_node_stats_no_existing_state(self, *, job_tracker_service, mock_store):
        """Test update with no existing state creates new record."""
        mock_store.get_node_stats_by_batch_and_node.return_value = None

        job_tracker_service.update_node_stats(
            job_run_id=JOB_RUN_ID,
            node_id=NODE_ID_1,
            node_stats={
                "name": "Test Node",
                "node_status": "COMPLETED",
                "docs_completed": ["doc1", "doc2"],
                "docs_completed_count": 2,
            },
        )

        mock_store.store_node_stats.assert_called_once()
        stored_stats = mock_store.store_node_stats.call_args[1]["node_stats"]
        assert stored_stats.node_id == NODE_ID_1
        assert stored_stats.name == "Test Node"
        assert stored_stats.node_status == "COMPLETED"
        assert stored_stats.docs_completed == ["doc1", "doc2"]
        assert stored_stats.docs_completed_count == 2

    def test_update_node_stats_merges_with_existing(self, *, job_tracker_service, mock_store):
        """Test update merges with existing state."""
        existing_stats = NodeStats(
            node_id=NODE_ID_1,
            name="Test Node",
            node_status=ExecutionStatus.RUNNING,
            start_time=1000,
            total_docs=["doc1", "doc2", "doc3"],
            docs_completed=[],
            docs_completed_count=0,
        )
        mock_store.get_node_stats_by_batch_and_node.return_value = existing_stats

        job_tracker_service.update_node_stats(
            job_run_id=JOB_RUN_ID,
            node_id=NODE_ID_1,
            node_stats={
                "node_status": "COMPLETED",
                "end_time": 2000,
                "time_taken": 1000,
                "docs_completed": ["doc1", "doc2"],
                "docs_completed_count": 2,
            },
        )

        mock_store.store_node_stats.assert_called_once()
        stored_stats = mock_store.store_node_stats.call_args[1]["node_stats"]

        # Verify merge: existing fields preserved
        assert stored_stats.node_id == NODE_ID_1
        assert stored_stats.name == "Test Node"
        assert stored_stats.start_time == 1000
        assert stored_stats.total_docs == ["doc1", "doc2", "doc3"]

        # Verify merge: new fields applied
        assert stored_stats.node_status == "COMPLETED"
        assert stored_stats.end_time == 2000
        assert stored_stats.time_taken == 1000
        assert stored_stats.docs_completed == ["doc1", "doc2"]
        assert stored_stats.docs_completed_count == 2

    def test_update_node_stats_preserves_metadata(self, *, job_tracker_service, mock_store):
        """Test update preserves existing metadata when not provided."""
        existing_stats = NodeStats(
            node_id=NODE_ID_1,
            name="Test Node",
            node_status=ExecutionStatus.RUNNING,
            node_metadata={
                "id": NODE_ID_1,
                "operator": "TestOperator",
                "node_metadata": {"custom_field": "value1", "counter": 42},
            },
        )
        mock_store.get_node_stats_by_batch_and_node.return_value = existing_stats

        job_tracker_service.update_node_stats(
            job_run_id=JOB_RUN_ID,
            node_id=NODE_ID_1,
            node_stats={"node_status": "COMPLETED", "docs_completed_count": 5},
        )

        stored_stats = mock_store.store_node_stats.call_args[1]["node_stats"]

        # Verify metadata preserved
        assert stored_stats.node_metadata is not None
        assert stored_stats.node_metadata["id"] == NODE_ID_1
        assert stored_stats.node_metadata["operator"] == "TestOperator"
        assert stored_stats.node_metadata["node_metadata"]["custom_field"] == "value1"
        assert stored_stats.node_metadata["node_metadata"]["counter"] == 42

        # Verify new fields applied
        assert stored_stats.node_status == "COMPLETED"
        assert stored_stats.docs_completed_count == 5

    def test_update_node_stats_partial_update_preserves_counters(self, *, job_tracker_service, mock_store):
        """Test partial update doesn't discard existing counters."""
        existing_stats = NodeStats(
            node_id=NODE_ID_1,
            name="Test Node",
            node_status=ExecutionStatus.RUNNING,
            start_time=1000,
            total_docs=["doc1", "doc2", "doc3"],
            docs_completed=["doc1"],
            docs_completed_count=1,
            failed_docs=["doc2"],
            skipped_docs=[],
        )
        mock_store.get_node_stats_by_batch_and_node.return_value = existing_stats

        # Partial update with only status change
        job_tracker_service.update_node_stats(
            job_run_id=JOB_RUN_ID,
            node_id=NODE_ID_1,
            node_stats={"node_status": "COMPLETED"},
        )

        stored_stats = mock_store.store_node_stats.call_args[1]["node_stats"]

        # Verify all existing fields preserved
        assert stored_stats.start_time == 1000
        assert stored_stats.total_docs == ["doc1", "doc2", "doc3"]
        assert stored_stats.docs_completed == ["doc1"]
        assert stored_stats.docs_completed_count == 1
        assert stored_stats.failed_docs == ["doc2"]
        assert stored_stats.skipped_docs == []

        # Verify only status updated
        assert stored_stats.node_status == "COMPLETED"

    def test_update_node_stats_with_batch_id(self, *, job_tracker_service, mock_store):
        """Test update with batch_id parameter."""
        existing_stats = NodeStats(
            node_id=NODE_ID_1,
            name="Test Node",
            batch_id=BATCH_ID,
            batch_num=1,
            node_status=ExecutionStatus.RUNNING,
        )
        mock_store.get_node_stats_by_batch_and_node.return_value = existing_stats

        job_tracker_service.update_node_stats(
            job_run_id=JOB_RUN_ID,
            node_id=NODE_ID_1,
            node_stats={"node_status": "COMPLETED"},
            batch_id=BATCH_ID,
        )

        # Verify get called with batch_id
        mock_store.get_node_stats_by_batch_and_node.assert_called_once_with(
            job_run_id=JOB_RUN_ID, node_id=NODE_ID_1, batch_id=BATCH_ID
        )

        stored_stats = mock_store.store_node_stats.call_args[1]["node_stats"]
        assert stored_stats.batch_id == BATCH_ID
        assert stored_stats.batch_num == 1

    def test_update_node_stats_with_node_stats_dto(self, *, job_tracker_service, mock_store):
        """Test update accepts NodeStats input."""
        existing_stats = NodeStats(
            node_id=NODE_ID_1,
            name="Test Node",
            node_status=ExecutionStatus.RUNNING,
            start_time=1000,
        )
        mock_store.get_node_stats_by_batch_and_node.return_value = existing_stats

        update_dto = NodeStats(
            node_id=NODE_ID_1,
            name="Test Node",
            node_status=ExecutionStatus.COMPLETED,
            end_time=2000,
        )

        job_tracker_service.update_node_stats(job_run_id=JOB_RUN_ID, node_id=NODE_ID_1, node_stats=update_dto)

        stored_stats = mock_store.store_node_stats.call_args[1]["node_stats"]
        assert stored_stats.start_time == 1000  # Preserved from existing
        assert stored_stats.end_time == 2000  # From update
        assert stored_stats.node_status == ExecutionStatus.COMPLETED

    def test_update_node_stats_invalid_type(self, *, job_tracker_service, mock_store):
        """Test update raises error for invalid input type."""
        mock_store.get_node_stats_by_batch_and_node.return_value = None

        with pytest.raises(ValueError, match="Invalid node_stats type"):
            job_tracker_service.update_node_stats(job_run_id=JOB_RUN_ID, node_id=NODE_ID_1, node_stats="invalid_string")


class TestRequestCancelJob:
    """Test request_cancel_job method."""

    @pytest.mark.parametrize(
        "terminal_status",
        [
            ExecutionStatus.COMPLETED,
            ExecutionStatus.COMPLETED_WITH_ERRORS,
            ExecutionStatus.COMPLETED_WITH_WARNINGS,
            ExecutionStatus.CANCELED,
            ExecutionStatus.FAILED,
            ExecutionStatus.ABORTED,
        ],
    )
    def test_cancel_job_in_terminal_state_raises_exception(self, *, job_tracker_service, mock_store, terminal_status):
        """Test that canceling a job in terminal state raises JobRunInvalidStateException."""
        from docpipe.exceptions.docpipe_exceptions import JobRunInvalidStateException

        # Arrange
        job_run_id = "test-job-run-123"
        job_stats = JobStats(
            job_id="test-job-123",
            job_run_id=job_run_id,
            status=terminal_status,
        )
        mock_store.get_job_stats.return_value = job_stats

        # Act & Assert
        with pytest.raises(JobRunInvalidStateException) as exc_info:
            job_tracker_service.request_cancel_job(job_run_id=job_run_id)

        # Verify exception details
        assert exc_info.value.job_run_id == job_run_id
        assert exc_info.value.current_state == terminal_status.value
        assert terminal_status.value in str(exc_info.value)
        assert "Cannot cancel" in str(exc_info.value)

    @pytest.mark.parametrize(
        "active_status",
        [
            ExecutionStatus.QUEUED,
            ExecutionStatus.PENDING,
            ExecutionStatus.STARTING,
            ExecutionStatus.RUNNING,
            ExecutionStatus.PAUSED,
            ExecutionStatus.RESUMING,
        ],
    )
    def test_cancel_job_in_active_state_succeeds(self, *, job_tracker_service, mock_store, active_status):
        """Test that canceling a job in active state succeeds."""
        # Arrange
        job_run_id = "test-job-run-456"
        job_stats = JobStats(
            job_id="test-job-456",
            job_run_id=job_run_id,
            status=active_status,
        )
        mock_store.get_job_stats.return_value = job_stats

        # Act
        job_tracker_service.request_cancel_job(job_run_id=job_run_id)

        # Assert
        mock_store.store_job_stats.assert_called_once()
        stored_stats = mock_store.store_job_stats.call_args[0][0]
        assert stored_stats.status == ExecutionStatus.CANCELING

    def test_cancel_already_canceling_job_succeeds(self, *, job_tracker_service, mock_store):
        """Test that canceling a job already in CANCELING state succeeds (idempotent)."""
        # Arrange
        job_run_id = "test-job-run-789"
        job_stats = JobStats(
            job_id="test-job-789",
            job_run_id=job_run_id,
            status=ExecutionStatus.CANCELING,
        )
        mock_store.get_job_stats.return_value = job_stats

        # Act
        job_tracker_service.request_cancel_job(job_run_id=job_run_id)

        # Assert - should remain in CANCELING state
        mock_store.store_job_stats.assert_called_once()
        _ = mock_store.store_job_stats.call_args[0][0]


class TestUpdateNodeStatsEdgeCases:
    """Test update_node_stats edge cases."""

    def test_update_with_empty_metadata(self, *, job_tracker_service, mock_store):
        """Test empty metadata dict."""
        job_run_id = "test-job-run-001"
        node_stats = NodeStats(
            node_id=NODE_ID_1,
            name="Test Node",
            total_docs=["doc1", "doc2"],
            docs_completed=["doc1", "doc2"],
            failed_docs=[],
            skipped_docs=[],
            node_metadata={},  # Empty metadata
        )

        mock_store.get_node_stats_by_batch_and_node.return_value = None

        job_tracker_service.update_node_stats(job_run_id=job_run_id, node_id=NODE_ID_1, node_stats=node_stats)

        mock_store.store_node_stats.assert_called_once()
        stored_stats = mock_store.store_node_stats.call_args.kwargs["node_stats"]
        assert stored_stats.node_id == NODE_ID_1

    def test_update_with_minimal_values(self, *, job_tracker_service, mock_store):
        """Test minimal required values in stats."""
        job_run_id = "test-job-run-002"
        node_stats = NodeStats(
            node_id=NODE_ID_1,
            name="Test Node",
            total_docs=[],  # Empty list instead of None
            docs_completed=[],
            failed_docs=[],
            skipped_docs=[],
        )

        mock_store.get_node_stats_by_batch_and_node.return_value = None

        job_tracker_service.update_node_stats(job_run_id=job_run_id, node_id=NODE_ID_1, node_stats=node_stats)

        mock_store.store_node_stats.assert_called_once()
        stored_stats = mock_store.store_node_stats.call_args.kwargs["node_stats"]
        assert stored_stats.node_id == NODE_ID_1

    def test_concurrent_updates(self, *, job_tracker_service, mock_store):
        """Test multiple simultaneous updates."""
        job_run_id = "test-job-run-003"

        # Simulate concurrent updates to different nodes
        node_stats_1 = NodeStats(
            node_id=NODE_ID_1,
            name="Node 1",
            total_docs=["doc1"],
            docs_completed=["doc1"],
            failed_docs=[],
            skipped_docs=[],
        )

        node_stats_2 = NodeStats(
            node_id=NODE_ID_2,
            name="Node 2",
            total_docs=["doc2"],
            docs_completed=["doc2"],
            failed_docs=[],
            skipped_docs=[],
        )

        mock_store.get_node_stats_by_batch_and_node.return_value = None

        job_tracker_service.update_node_stats(job_run_id=job_run_id, node_id=NODE_ID_1, node_stats=node_stats_1)
        job_tracker_service.update_node_stats(job_run_id=job_run_id, node_id=NODE_ID_2, node_stats=node_stats_2)

        assert mock_store.store_node_stats.call_count == 2

    def test_update_nonexistent_node(self, *, job_tracker_service, mock_store):
        """Test updating node that doesn't exist."""
        job_run_id = "test-job-run-004"
        nonexistent_node_id = "nonexistent-node-id"
        node_stats = NodeStats(
            node_id=nonexistent_node_id,
            name="Nonexistent Node",
            total_docs=["doc1"],
            docs_completed=["doc1"],
            failed_docs=[],
            skipped_docs=[],
        )

        mock_store.get_node_stats_by_batch_and_node.return_value = None

        # Should still store the node stats (creates new entry)
        job_tracker_service.update_node_stats(job_run_id=job_run_id, node_id=nonexistent_node_id, node_stats=node_stats)

        mock_store.store_node_stats.assert_called_once()


class TestComplexBatchAggregation:
    """Test complex batch aggregation scenarios."""

    def test_nested_batch_hierarchy(self, *, job_tracker_service, mock_store, mock_aggregator):
        """Test multi-level batch nesting."""
        job_run_id = "test-job-run-batch-001"

        # Create nested batch structure
        parent_batch_id = "parent-batch-001"
        child_batch_id_1 = "child-batch-001"
        child_batch_id_2 = "child-batch-002"

        node_stats_parent = NodeStats(
            node_id=NODE_ID_1,
            name="Parent Node",
            batch_id=parent_batch_id,
            batch_num=1,
            total_docs=["doc1", "doc2", "doc3", "doc4"],
            docs_completed=["doc1", "doc2", "doc3", "doc4"],
            failed_docs=[],
            skipped_docs=[],
        )

        node_stats_child_1 = NodeStats(
            node_id=NODE_ID_1,
            name="Child Node 1",
            batch_id=child_batch_id_1,
            batch_num=1,
            total_docs=["doc1", "doc2"],
            docs_completed=["doc1", "doc2"],
            failed_docs=[],
            skipped_docs=[],
        )

        node_stats_child_2 = NodeStats(
            node_id=NODE_ID_1,
            name="Child Node 2",
            batch_id=child_batch_id_2,
            batch_num=2,
            total_docs=["doc3", "doc4"],
            docs_completed=["doc3", "doc4"],
            failed_docs=[],
            skipped_docs=[],
        )

        mock_store.get_node_stats_by_batch_and_node.return_value = None

        # Store all batch stats
        job_tracker_service.update_node_stats(
            job_run_id=job_run_id, node_id=NODE_ID_1, node_stats=node_stats_parent, batch_id=parent_batch_id
        )
        job_tracker_service.update_node_stats(
            job_run_id=job_run_id, node_id=NODE_ID_1, node_stats=node_stats_child_1, batch_id=child_batch_id_1
        )
        job_tracker_service.update_node_stats(
            job_run_id=job_run_id, node_id=NODE_ID_1, node_stats=node_stats_child_2, batch_id=child_batch_id_2
        )

        assert mock_store.store_node_stats.call_count == 3

    def test_mixed_batch_statuses(self, *, job_tracker_service, mock_store):
        """Test batches with different statuses."""
        job_run_id = "test-job-run-batch-002"

        # Batch 1: Completed
        node_stats_1 = NodeStats(
            node_id=NODE_ID_1,
            name="Batch 1",
            batch_id=BATCH_ID,
            batch_num=1,
            node_status=ExecutionStatus.COMPLETED.value,
            total_docs=["doc1", "doc2"],
            docs_completed=["doc1", "doc2"],
            failed_docs=[],
            skipped_docs=[],
        )

        # Batch 2: Failed
        node_stats_2 = NodeStats(
            node_id=NODE_ID_1,
            name="Batch 2",
            batch_id=BATCH_ID,
            batch_num=2,
            node_status=ExecutionStatus.FAILED.value,
            total_docs=["doc3", "doc4"],
            docs_completed=[],
            failed_docs=["doc3", "doc4"],
            skipped_docs=[],
        )

        mock_store.get_node_stats_by_batch_and_node.return_value = None

        job_tracker_service.update_node_stats(
            job_run_id=job_run_id, node_id=NODE_ID_1, node_stats=node_stats_1, batch_id=BATCH_ID
        )
        job_tracker_service.update_node_stats(
            job_run_id=job_run_id, node_id=NODE_ID_1, node_stats=node_stats_2, batch_id=BATCH_ID
        )

        assert mock_store.store_node_stats.call_count == 2

    def test_batch_with_errors(self, *, job_tracker_service, mock_store):
        """Test error propagation in batches."""
        job_run_id = "test-job-run-batch-003"

        node_stats = NodeStats(
            node_id=NODE_ID_1,
            name="Error Batch",
            batch_id=BATCH_ID,
            batch_num=1,
            node_status=ExecutionStatus.FAILED.value,
            total_docs=["doc1", "doc2", "doc3"],
            docs_completed=["doc1"],
            failed_docs=["doc2", "doc3"],
            skipped_docs=[],
            error="Processing error occurred",
        )

        mock_store.get_node_stats_by_batch_and_node.return_value = None

        job_tracker_service.update_node_stats(
            job_run_id=job_run_id, node_id=NODE_ID_1, node_stats=node_stats, batch_id=BATCH_ID
        )

        mock_store.store_node_stats.assert_called_once()
        stored_stats = mock_store.store_node_stats.call_args.kwargs["node_stats"]
        assert stored_stats.error == "Processing error occurred"
        assert len(stored_stats.failed_docs) == 2

    def test_large_batch_count(self, *, job_tracker_service, mock_store):
        """Test performance with many batches."""
        job_run_id = "test-job-run-batch-004"

        mock_store.get_node_stats_by_batch_and_node.return_value = None

        # Create 100 batches
        for batch_num in range(1, 101):
            node_stats = NodeStats(
                node_id=NODE_ID_1,
                name=f"Batch {batch_num}",
                batch_id=BATCH_ID,
                batch_num=batch_num,
                total_docs=[f"doc{batch_num}"],
                docs_completed=[f"doc{batch_num}"],
                failed_docs=[],
                skipped_docs=[],
            )
            job_tracker_service.update_node_stats(
                job_run_id=job_run_id, node_id=NODE_ID_1, node_stats=node_stats, batch_id=BATCH_ID
            )

        assert mock_store.store_node_stats.call_count == 100


# ---------------------------------------------------------------------------
# Additional tests added to increase coverage
# ---------------------------------------------------------------------------


class TestUpdateDocCounts:
    """Test update_doc_counts method."""

    def test_update_doc_counts_not_found_raises(self, *, job_tracker_service, mock_store):
        """Raises JobRunNotFoundException when job run not found."""
        mock_store.get_job_stats.return_value = None

        from docpipe.exceptions.docpipe_exceptions import JobRunNotFoundException

        with pytest.raises(JobRunNotFoundException):
            job_tracker_service.update_doc_counts(
                job_run_id=JOB_RUN_ID,
                metadata={},
                operator_category="ingest",
            )

    def test_update_doc_counts_ingest_list(self, *, job_tracker_service, mock_store):
        """Ingest operator: total_docs updated from list value."""
        from docpipe.core.constants.constants import Metrics
        from docpipe.core.operators.abstract_operator import OperatorCategory

        job_stats = JobStats(job_id=JOB_ID, job_run_id=JOB_RUN_ID, status=ExecutionStatus.RUNNING, total_docs=0)
        mock_store.get_job_stats.return_value = job_stats

        job_tracker_service.update_doc_counts(
            job_run_id=JOB_RUN_ID,
            metadata={Metrics.External.TOTAL_DOCS: ["doc1", "doc2", "doc3"]},
            operator_category=OperatorCategory.Ingest.value,
        )

        call_args = mock_store.store_job_stats.call_args[0][0]
        assert call_args.total_docs == 3

    def test_update_doc_counts_ingest_int(self, *, job_tracker_service, mock_store):
        """Ingest operator: total_docs updated from int value."""
        from docpipe.core.constants.constants import Metrics
        from docpipe.core.operators.abstract_operator import OperatorCategory

        job_stats = JobStats(job_id=JOB_ID, job_run_id=JOB_RUN_ID, status=ExecutionStatus.RUNNING, total_docs=0)
        mock_store.get_job_stats.return_value = job_stats

        job_tracker_service.update_doc_counts(
            job_run_id=JOB_RUN_ID,
            metadata={Metrics.External.TOTAL_DOCS: 10},
            operator_category=OperatorCategory.Ingest.value,
        )

        call_args = mock_store.store_job_stats.call_args[0][0]
        assert call_args.total_docs == 10

    def test_update_doc_counts_deleted_docs(self, *, job_tracker_service, mock_store):
        """deleted_doc_count updated from metadata."""
        from docpipe.core.constants.constants import Metrics

        job_stats = JobStats(job_id=JOB_ID, job_run_id=JOB_RUN_ID, status=ExecutionStatus.RUNNING, deleted_doc_count=0)
        mock_store.get_job_stats.return_value = job_stats

        job_tracker_service.update_doc_counts(
            job_run_id=JOB_RUN_ID,
            metadata={Metrics.External.DELETED_DOC_COUNT: 5},
            operator_category="extract",
        )

        call_args = mock_store.store_job_stats.call_args[0][0]
        assert call_args.deleted_doc_count == 5

    def test_update_doc_counts_pages_processed(self, *, job_tracker_service, mock_store):
        """total_pages_processed and execution_time updated from metadata."""
        from docpipe.core.constants.operator_constants import OperatorConstants

        job_stats = JobStats(
            job_id=JOB_ID,
            job_run_id=JOB_RUN_ID,
            status=ExecutionStatus.RUNNING,
            total_pages_processed=0,
            start_time=1000,
        )
        mock_store.get_job_stats.return_value = job_stats

        job_tracker_service.update_doc_counts(
            job_run_id=JOB_RUN_ID,
            metadata={OperatorConstants.Metadata.TOTAL_PAGES_PROCESSED: 50},
            operator_category="extract",
        )

        call_args = mock_store.store_job_stats.call_args[0][0]
        assert call_args.total_pages_processed == 50

    def test_update_doc_counts_page_type_stats_merge(self, *, job_tracker_service, mock_store):
        """page_type_stats merged (summed) across multiple calls."""
        from docpipe.core.constants.operator_constants import OperatorConstants

        job_stats = JobStats(
            job_id=JOB_ID,
            job_run_id=JOB_RUN_ID,
            status=ExecutionStatus.RUNNING,
            page_type_stats={"pdf": 10, "docx": 5},
        )
        mock_store.get_job_stats.return_value = job_stats

        job_tracker_service.update_doc_counts(
            job_run_id=JOB_RUN_ID,
            metadata={OperatorConstants.Metadata.PAGE_TYPE_STATS: {"pdf": 3, "xlsx": 2}},
            operator_category="extract",
        )

        call_args = mock_store.store_job_stats.call_args[0][0]
        assert call_args.page_type_stats["pdf"] == 13
        assert call_args.page_type_stats["docx"] == 5
        assert call_args.page_type_stats["xlsx"] == 2

    def test_update_doc_counts_page_type_stats_initialized_when_none(self, *, job_tracker_service, mock_store):
        """page_type_stats initialized from None when first update arrives."""
        from docpipe.core.constants.operator_constants import OperatorConstants

        job_stats = JobStats(job_id=JOB_ID, job_run_id=JOB_RUN_ID, status=ExecutionStatus.RUNNING, page_type_stats=None)
        mock_store.get_job_stats.return_value = job_stats

        job_tracker_service.update_doc_counts(
            job_run_id=JOB_RUN_ID,
            metadata={OperatorConstants.Metadata.PAGE_TYPE_STATS: {"html": 7}},
            operator_category="extract",
        )

        call_args = mock_store.store_job_stats.call_args[0][0]
        assert call_args.page_type_stats == {"html": 7}


class TestBulkStoreNodeStats:
    """Test bulk_store_node_stats delegation."""

    def test_bulk_store_delegates_to_store(self, *, job_tracker_service, mock_store):
        """bulk_store_node_stats delegates to job_stats_store."""
        node_stats_list = [
            NodeStats(node_id=NODE_ID_1, name="n1"),
            NodeStats(node_id=NODE_ID_2, name="n2"),
        ]

        job_tracker_service.bulk_store_node_stats(
            job_id=JOB_ID,
            job_run_id=JOB_RUN_ID,
            node_stats_list=node_stats_list,
        )

        mock_store.bulk_store_node_stats.assert_called_once_with(job_run_id=JOB_RUN_ID, node_stats_list=node_stats_list)


class TestStoreJobStats:
    """Test store_job_stats delegation."""

    def test_store_job_stats_delegates(self, *, job_tracker_service, mock_store):
        """store_job_stats delegates to job_stats_store."""
        job_stats = JobStats(job_id=JOB_ID, job_run_id=JOB_RUN_ID)

        job_tracker_service.store_job_stats(job_stats=job_stats)

        mock_store.store_job_stats.assert_called_once_with(job_stats)


class TestRequestDeleteJobRun:
    """Test request_delete_job_run method."""

    def test_delete_job_run_success(self, *, job_tracker_service, mock_store):
        """Successful deletion returns confirmation message."""
        job_stats = JobStats(job_id=JOB_ID, job_run_id=JOB_RUN_ID)
        mock_store.get_job_stats.return_value = job_stats

        result = job_tracker_service.request_delete_job_run(job_run_id=JOB_RUN_ID)

        mock_store.delete_job_stats.assert_called_once_with(JOB_RUN_ID)
        assert JOB_RUN_ID in result
        assert "deleted" in result.lower()

    def test_delete_job_run_not_found_raises(self, *, job_tracker_service, mock_store):
        """Raises JobRunNotFoundException when job run not found."""
        mock_store.get_job_stats.return_value = None

        from docpipe.exceptions.docpipe_exceptions import JobRunNotFoundException

        with pytest.raises(JobRunNotFoundException):
            job_tracker_service.request_delete_job_run(job_run_id=JOB_RUN_ID)


class TestCancelJobRunIfCancelling:
    """Test cancel_job_run_if_cancelling method."""

    def test_returns_false_when_not_found(self, *, job_tracker_service, mock_store):
        """Returns False when job not found."""
        mock_store.get_job_stats.return_value = None

        result = job_tracker_service.cancel_job_run_if_cancelling(job_run_id=JOB_RUN_ID)

        assert result is False

    def test_returns_false_when_not_canceling(self, *, job_tracker_service, mock_store):
        """Returns False when job is not in CANCELING state."""
        job_stats = JobStats(job_id=JOB_ID, job_run_id=JOB_RUN_ID, status=ExecutionStatus.RUNNING)
        mock_store.get_job_stats.return_value = job_stats

        result = job_tracker_service.cancel_job_run_if_cancelling(job_run_id=JOB_RUN_ID)

        assert result is False
        mock_store.store_job_stats.assert_not_called()

    def test_cancels_and_returns_true_when_canceling(self, *, job_tracker_service, mock_store):
        """Returns True and stores CANCELED status when in CANCELING state."""
        job_stats = JobStats(job_id=JOB_ID, job_run_id=JOB_RUN_ID, status=ExecutionStatus.CANCELING)
        mock_store.get_job_stats.return_value = job_stats

        result = job_tracker_service.cancel_job_run_if_cancelling(job_run_id=JOB_RUN_ID)

        assert result is True
        call_args = mock_store.store_job_stats.call_args[0][0]
        assert call_args.status == ExecutionStatus.CANCELED
        assert call_args.end_time is not None

    def test_writes_job_logs_when_path_provided(self, *, job_tracker_service, mock_store, tmp_path):
        """Writes job logs to path when job_log_path is provided and job is CANCELING."""
        job_stats = JobStats(job_id=JOB_ID, job_run_id=JOB_RUN_ID, status=ExecutionStatus.CANCELING, node_stats={})
        mock_store.get_job_stats.return_value = job_stats
        # mock get_job so write_job_logs internal get_job doesn't fail
        mock_store.get_job_stats.side_effect = None

        log_path = str(tmp_path / "subdir" / "job.log")

        result = job_tracker_service.cancel_job_run_if_cancelling(job_run_id=JOB_RUN_ID, job_log_path=log_path)

        assert result is True
        import os

        assert os.path.exists(log_path)


class TestRequestCancelJobNotFound:
    """Test request_cancel_job raises when job not found."""

    def test_request_cancel_job_not_found(self, *, job_tracker_service, mock_store):
        """Raises JobRunNotFoundException when job not found."""
        mock_store.get_job_stats.return_value = None

        from docpipe.exceptions.docpipe_exceptions import JobRunNotFoundException

        with pytest.raises(JobRunNotFoundException):
            job_tracker_service.request_cancel_job(job_run_id=JOB_RUN_ID)


class TestIsJobRunComplete:
    """Test is_job_run_complete method."""

    def test_returns_false_when_not_found(self, *, job_tracker_service, mock_store):
        """Returns False when job not found."""
        mock_store.get_job_stats.return_value = None

        assert job_tracker_service.is_job_run_complete(job_run_id=JOB_RUN_ID) is False

    @pytest.mark.parametrize(
        "status",
        [ExecutionStatus.COMPLETED, ExecutionStatus.FAILED, ExecutionStatus.CANCELED],
    )
    def test_returns_true_for_terminal_statuses(self, *, job_tracker_service, mock_store, status):
        """Returns True for terminal statuses."""
        job_stats = JobStats(job_id=JOB_ID, job_run_id=JOB_RUN_ID, status=status)
        mock_store.get_job_stats.return_value = job_stats

        assert job_tracker_service.is_job_run_complete(job_run_id=JOB_RUN_ID) is True

    def test_returns_false_for_running(self, *, job_tracker_service, mock_store):
        """Returns False for non-terminal status."""
        job_stats = JobStats(job_id=JOB_ID, job_run_id=JOB_RUN_ID, status=ExecutionStatus.RUNNING)
        mock_store.get_job_stats.return_value = job_stats

        assert job_tracker_service.is_job_run_complete(job_run_id=JOB_RUN_ID) is False


class TestListJobRuns:
    """Test list_job_runs delegation."""

    def test_list_job_runs_delegates_to_store(self, *, job_tracker_service, mock_store):
        """list_job_runs delegates to store."""
        mock_store.list_job_runs.return_value = []

        result = job_tracker_service.list_job_runs(job_id=JOB_ID, status=ExecutionStatus.RUNNING, limit=10)

        mock_store.list_job_runs.assert_called_once_with(job_id=JOB_ID, status=ExecutionStatus.RUNNING, limit=10)
        assert result == []


class TestGetNodeStats:
    """Test get_node_stats delegation."""

    def test_get_node_stats_delegates_to_aggregator(self, *, job_tracker_service, mock_aggregator):
        """get_node_stats delegates to node_stats_aggregator."""
        mock_aggregator.get_aggregated_node_stats.return_value = {}

        result = job_tracker_service.get_node_stats(job_id=JOB_ID, job_run_id=JOB_RUN_ID)

        mock_aggregator.get_aggregated_node_stats.assert_called_once_with(job_id=JOB_ID, job_run_id=JOB_RUN_ID)
        assert result == {}


class TestWriteJobLogs:
    """Test write_job_logs method."""

    def test_write_job_logs_creates_file(self, *, job_tracker_service, tmp_path):
        """write_job_logs creates a file at the given path."""
        job_stats = JobStats(job_id=JOB_ID, job_run_id=JOB_RUN_ID, status=ExecutionStatus.COMPLETED)
        log_path = str(tmp_path / "logs" / "job.json")

        job_tracker_service.write_job_logs(job_stats=job_stats, job_log_path=log_path)

        import json
        import os

        assert os.path.exists(log_path)
        with open(log_path) as f:
            data = json.load(f)
        assert data["job_run_id"] == JOB_RUN_ID

    def test_write_job_logs_dict_input(self, *, job_tracker_service, tmp_path):
        """write_job_logs accepts a plain dict."""
        log_path = str(tmp_path / "logs" / "job.json")

        job_tracker_service.write_job_logs(
            job_stats={"job_run_id": JOB_RUN_ID, "status": "COMPLETED"},
            job_log_path=log_path,
        )

        import os

        assert os.path.exists(log_path)

    def test_write_job_logs_raises_on_write_failure(self, *, job_tracker_service):
        """write_job_logs raises OSError on write failure."""
        from unittest.mock import patch

        job_stats = JobStats(job_id=JOB_ID, job_run_id=JOB_RUN_ID)

        with patch("builtins.open", side_effect=PermissionError("denied")):
            with pytest.raises(OSError, match="Failed to write job logs"):
                job_tracker_service.write_job_logs(job_stats=job_stats, job_log_path="/some/path/job.json")


class TestGetJobRunLogs:
    """Test get_job_run_logs method."""

    def test_returns_empty_when_no_job(self, *, job_tracker_service, mock_store):
        """Returns empty list when job not found."""
        mock_store.get_job_stats.return_value = None

        result = job_tracker_service.get_job_run_logs(job_run_id=JOB_RUN_ID)

        assert result == []

    def test_returns_log_lines_sorted_by_start_time(self, *, job_tracker_service, mock_store, mock_aggregator):
        """Returns log lines sorted by start_time."""
        node_stats = {
            NODE_ID_1: NodeStats(
                node_id=NODE_ID_1,
                name="NodeA",
                start_time=100,
                end_time=110,
                time_taken=10,
                node_status=ExecutionStatus.COMPLETED.value,
                docs_completed_count=1,
                total_docs=["doc1"],
                docs_completed=["doc1"],
                col_names=["col1"],
            ),
            NODE_ID_2: NodeStats(
                node_id=NODE_ID_2,
                name="NodeB",
                start_time=200,
                end_time=220,
                time_taken=20,
                node_status=ExecutionStatus.COMPLETED.value,
                docs_completed_count=2,
                total_docs=["doc2", "doc3"],
                docs_completed=["doc2", "doc3"],
                col_names=[],
            ),
        }
        job_stats = JobStats(
            job_id=JOB_ID, job_run_id=JOB_RUN_ID, status=ExecutionStatus.COMPLETED, node_stats=node_stats
        )
        mock_store.get_job_stats.return_value = job_stats
        mock_aggregator.get_aggregated_node_stats.return_value = node_stats

        result = job_tracker_service.get_job_run_logs(job_run_id=JOB_RUN_ID)

        assert isinstance(result, list)
        assert len(result) > 0
        # NodeA lines appear before NodeB lines since start_time=100 < 200
        node_a_idx = next(i for i, line in enumerate(result) if "NodeA" in line)
        node_b_idx = next(i for i, line in enumerate(result) if "NodeB" in line)
        assert node_a_idx < node_b_idx


class TestFormatSchemaLine:
    """Test _format_schema_line static method."""

    def test_none_returns_unavailable(self, *, job_tracker_service):
        """None col_names returns unavailable string."""
        result = job_tracker_service._format_schema_line(None)
        assert result == "Schema: unavailable"

    def test_empty_list_returns_unavailable(self, *, job_tracker_service):
        """Empty col_names returns unavailable string."""
        result = job_tracker_service._format_schema_line([])
        assert result == "Schema: unavailable"

    def test_col_names_joined(self, *, job_tracker_service):
        """Non-empty col_names are joined."""
        result = job_tracker_service._format_schema_line(["col1", "col2"])
        assert "col1" in result
        assert "col2" in result


class TestCountItems:
    """Test _count_items static method."""

    def test_list_returns_len(self, *, job_tracker_service):
        assert job_tracker_service._count_items(["a", "b", "c"]) == 3

    def test_none_returns_zero(self, *, job_tracker_service):
        assert job_tracker_service._count_items(None) == 0

    def test_int_returns_int(self, *, job_tracker_service):
        assert job_tracker_service._count_items(5) == 5

    def test_non_int_non_list_returns_zero(self, *, job_tracker_service):
        assert job_tracker_service._count_items("not_a_list") == 0


class TestCalculateNodeSequence:
    """Test _calculate_node_sequence static method."""

    def test_empty_returns_empty(self, *, job_tracker_service):
        assert job_tracker_service._calculate_node_sequence(node_stats={}) == []

    def test_sorted_by_start_time(self, *, job_tracker_service):
        node_stats = {
            "node_b": NodeStats(node_id="node_b", name="B", start_time=200),
            "node_a": NodeStats(node_id="node_a", name="A", start_time=100),
        }
        result = job_tracker_service._calculate_node_sequence(node_stats=node_stats)
        assert result == ["node_a", "node_b"]

    def test_sorted_with_dict_values(self, *, job_tracker_service):
        """Works when node_stats values are plain dicts."""
        node_stats = {
            "node_b": {"start_time": 300, "end_time": 400, "name": "B"},
            "node_a": {"start_time": 100, "end_time": 200, "name": "A"},
        }
        result = job_tracker_service._calculate_node_sequence(node_stats=node_stats)
        assert result == ["node_a", "node_b"]


class TestBuildNodeMetadataArray:
    """Test _build_node_metadata_array static method."""

    def test_builds_from_node_stats_objects(self, *, job_tracker_service):
        node_stats = {
            NODE_ID_1: NodeStats(
                node_id=NODE_ID_1,
                name="MyNode",
                node_metadata={"key": "value"},
            )
        }
        result = job_tracker_service._build_node_metadata_array(node_stats=node_stats)
        assert len(result) == 1
        assert result[0]["id"] == NODE_ID_1
        assert result[0]["operator"] == "MyNode"

    def test_builds_from_dicts(self, *, job_tracker_service):
        node_stats = {
            NODE_ID_1: {"name": "DictNode", "node_metadata": {"a": 1}},
        }
        result = job_tracker_service._build_node_metadata_array(node_stats=node_stats)
        assert result[0]["id"] == NODE_ID_1
        assert result[0]["operator"] == "DictNode"


class TestFormatNodeLogString:
    """Test _format_node_log_string static method."""

    def test_format_from_node_stats_object(self, *, job_tracker_service):
        """Works with NodeStats objects."""
        node_stat = NodeStats(
            node_id=NODE_ID_1,
            name="TestNode",
            time_taken=5,
            node_status=ExecutionStatus.COMPLETED.value,
            col_names=["col1"],
        )
        result = job_tracker_service._format_node_log_string(node_id=NODE_ID_1, node_stat=node_stat)
        assert "TestNode" in result
        assert "Starting execution" in result

    def test_format_from_dict(self, *, job_tracker_service):
        """Works with dict input."""
        node_stat = {
            "name": "DictNode",
            "time_taken": 3,
            "node_status": ExecutionStatus.FAILED.value,
            "col_names": [],
            "node_metadata": None,
            "error": "some error",
        }
        result = job_tracker_service._format_node_log_string(node_id=NODE_ID_1, node_stat=node_stat)
        assert "DictNode" in result
        assert "some error" in result

    def test_format_skipped_status(self, *, job_tracker_service):
        """SKIPPED status produces skipped log line."""
        node_stat = NodeStats(
            node_id=NODE_ID_1,
            name="SkippedNode",
            time_taken=0,
            node_status=ExecutionStatus.SKIPPED.value,
        )
        result = job_tracker_service._format_node_log_string(node_id=NODE_ID_1, node_stat=node_stat)
        assert "Skipped" in result

    def test_format_with_metadata(self, *, job_tracker_service):
        """Metadata is included in log when present."""
        node_stat = NodeStats(
            node_id=NODE_ID_1,
            name="MetaNode",
            time_taken=1,
            node_status=ExecutionStatus.COMPLETED.value,
            node_metadata={"processed": 5},
        )
        result = job_tracker_service._format_node_log_string(node_id=NODE_ID_1, node_stat=node_stat)
        assert "Operator Metadata" in result


class TestCreatePendingBatchNodeStats:
    """Test create_pending_batch_node_stats method."""

    def test_creates_pending_records(self, *, job_tracker_service, mock_store):
        """Creates N_batches x N_nodes pending records."""
        job_tracker_service.create_pending_batch_node_stats(
            job_run_id=JOB_RUN_ID,
            batch_ids=["b1", "b2"],
            batch_nums=[0, 1],
            downstream_node_ids=[NODE_ID_1, NODE_ID_2],
            downstream_node_names=["NodeA", "NodeB"],
        )

        mock_store.bulk_store_node_stats.assert_called_once()
        call_kwargs = mock_store.bulk_store_node_stats.call_args[1]
        pending_list = call_kwargs["node_stats_list"]
        assert len(pending_list) == 4  # 2 batches x 2 nodes
        assert all(ns.node_status == ExecutionStatus.PENDING.value for ns in pending_list)

    def test_raises_on_batch_length_mismatch(self, *, job_tracker_service, mock_store):
        """Raises ValueError when batch_ids and batch_nums lengths differ."""
        with pytest.raises(ValueError, match="batch_ids and batch_nums"):
            job_tracker_service.create_pending_batch_node_stats(
                job_run_id=JOB_RUN_ID,
                batch_ids=["b1", "b2"],
                batch_nums=[0],
                downstream_node_ids=[NODE_ID_1],
                downstream_node_names=["NodeA"],
            )

    def test_raises_on_node_length_mismatch(self, *, job_tracker_service, mock_store):
        """Raises ValueError when node_ids and node_names lengths differ."""
        with pytest.raises(ValueError, match="downstream_node_ids and downstream_node_names"):
            job_tracker_service.create_pending_batch_node_stats(
                job_run_id=JOB_RUN_ID,
                batch_ids=["b1"],
                batch_nums=[0],
                downstream_node_ids=[NODE_ID_1, NODE_ID_2],
                downstream_node_names=["NodeA"],
            )

    def test_empty_batch_ids_skips_bulk_store(self, *, job_tracker_service, mock_store):
        """Empty batch_ids results in no bulk_store call."""
        job_tracker_service.create_pending_batch_node_stats(
            job_run_id=JOB_RUN_ID,
            batch_ids=[],
            batch_nums=[],
            downstream_node_ids=[NODE_ID_1],
            downstream_node_names=["NodeA"],
        )

        mock_store.bulk_store_node_stats.assert_not_called()


class TestMarkSkippedDocumentsEdgeCases:
    """Test _mark_skipped_documents edge cases."""

    def test_no_ingest_node_skips_gracefully(self, *, job_tracker_service):
        """No warning-panic when ingest_node_id is None."""
        job_stats = JobStats(job_id=JOB_ID, job_run_id=JOB_RUN_ID, node_stats={})
        final_docs_status: dict = {}

        # Should not raise
        job_tracker_service._mark_skipped_documents(
            job_stats=job_stats, ingest_node_id=None, final_docs_status=final_docs_status
        )
        assert final_docs_status == {}

    def test_missing_ingest_node_in_stats(self, *, job_tracker_service):
        """Handles ingest_node_id not present in node_stats."""
        job_stats = JobStats(job_id=JOB_ID, job_run_id=JOB_RUN_ID, node_stats={})
        final_docs_status: dict = {}

        job_tracker_service._mark_skipped_documents(
            job_stats=job_stats, ingest_node_id="missing-node", final_docs_status=final_docs_status
        )
        assert final_docs_status == {}


class TestUpdateJobStatsCountsWarning:
    """Test _update_job_stats_counts reconciliation warning path."""

    def test_warns_on_count_mismatch(self, *, job_tracker_service):
        """Warning log path executes when total_docs != classified count."""
        job_stats = JobStats(
            job_id=JOB_ID,
            job_run_id=JOB_RUN_ID,
            total_docs=10,  # intentionally different from classified
        )
        final_docs_status = {f"doc{i}": "COMPLETED" for i in range(3)}  # only 3 classified

        # Should not raise - the warning logging path should execute
        job_tracker_service._update_job_stats_counts(job_stats=job_stats, final_docs_status=final_docs_status)

        assert job_stats.completed_docs == 3
        assert job_stats.processed_docs == 3


class TestCompleteNodeExecutionWithRawMetadata:
    """Test complete_node_execution wraps raw metadata in proper structure."""

    def test_raw_metadata_wrapped_in_structure(self, *, job_tracker_service, mock_store):
        """Raw metadata (without id/operator/node_metadata keys) gets wrapped."""
        import time

        current_time = int(time.time())
        existing_node = NodeStats(
            node_id=NODE_ID_1,
            name="MyNode",
            start_time=current_time - 5,
            total_docs=["doc1"],
            node_status=ExecutionStatus.RUNNING.value,
        )
        mock_store.get_node_stats_by_batch_and_node.return_value = existing_node

        job_tracker_service.complete_node_execution(
            job_run_id=JOB_RUN_ID,
            node_id=NODE_ID_1,
            node_name="MyNode",
            docs_completed=["doc1"],
            failed_docs=[],
            skipped_docs=[],
            col_names=["col1"],
            node_status=ExecutionStatus.COMPLETED.value,
            node_metadata={"custom_key": "custom_value"},  # raw, not pre-structured
        )

        stored = mock_store.store_node_stats.call_args[1]["node_stats"]
        # Raw metadata should be wrapped in NodeMetadataItem structure
        assert "id" in stored.node_metadata
        assert "operator" in stored.node_metadata
        assert stored.node_metadata["node_metadata"]["custom_key"] == "custom_value"

    def test_pre_structured_metadata_passed_through(self, *, job_tracker_service, mock_store):
        """Pre-structured metadata with id/operator/node_metadata is not re-wrapped."""
        import time

        current_time = int(time.time())
        existing_node = NodeStats(
            node_id=NODE_ID_1,
            name="MyNode",
            start_time=current_time - 5,
            total_docs=["doc1"],
            node_status=ExecutionStatus.RUNNING.value,
        )
        mock_store.get_node_stats_by_batch_and_node.return_value = existing_node

        pre_structured = {
            "id": NODE_ID_1,
            "operator": "MyNode",
            "node_metadata": {"some_field": 42},
        }

        job_tracker_service.complete_node_execution(
            job_run_id=JOB_RUN_ID,
            node_id=NODE_ID_1,
            node_name="MyNode",
            docs_completed=["doc1"],
            failed_docs=[],
            skipped_docs=[],
            col_names=[],
            node_status=ExecutionStatus.COMPLETED.value,
            node_metadata=pre_structured,
        )

        stored = mock_store.store_node_stats.call_args[1]["node_stats"]
        assert stored.node_metadata["node_metadata"]["some_field"] == 42


class TestCompleteNodeExecutionWithSkips:
    """Test complete_node_execution error string for skipped docs."""

    def test_skipped_docs_adds_error_field(self, *, job_tracker_service, mock_store):
        """Skipped docs causes error field to be set."""
        import time

        current_time = int(time.time())
        existing_node = NodeStats(
            node_id=NODE_ID_1,
            name="MyNode",
            start_time=current_time - 5,
            total_docs=["doc1", "doc2", "doc3"],
            node_status=ExecutionStatus.RUNNING.value,
        )
        mock_store.get_node_stats_by_batch_and_node.return_value = existing_node

        job_tracker_service.complete_node_execution(
            job_run_id=JOB_RUN_ID,
            node_id=NODE_ID_1,
            node_name="MyNode",
            docs_completed=["doc1"],
            failed_docs=[],
            skipped_docs=["doc2", "doc3"],
            col_names=[],
            node_status=ExecutionStatus.COMPLETED.value,
        )

        stored = mock_store.store_node_stats.call_args[1]["node_stats"]
        assert "skipped" in stored.error

    def test_both_failed_and_skipped_in_error(self, *, job_tracker_service, mock_store):
        """Both failed and skipped docs appear in error field."""
        import time

        current_time = int(time.time())
        existing_node = NodeStats(
            node_id=NODE_ID_1,
            name="MyNode",
            start_time=current_time - 5,
            total_docs=["doc1", "doc2", "doc3"],
            node_status=ExecutionStatus.RUNNING.value,
        )
        mock_store.get_node_stats_by_batch_and_node.return_value = existing_node

        job_tracker_service.complete_node_execution(
            job_run_id=JOB_RUN_ID,
            node_id=NODE_ID_1,
            node_name="MyNode",
            docs_completed=[],
            failed_docs=["doc1"],
            skipped_docs=["doc2", "doc3"],
            col_names=[],
            node_status=ExecutionStatus.COMPLETED_WITH_ERRORS.value,
        )

        stored = mock_store.store_node_stats.call_args[1]["node_stats"]
        assert "failed" in stored.error
        assert "skipped" in stored.error


class TestFailNodeExecutionNoExistingNode:
    """Test fail_node_execution when no existing node is found."""

    def test_uses_end_time_as_start_when_no_existing(self, *, job_tracker_service, mock_store):
        """When existing_node is None, start_time falls back to end_time."""
        mock_store.get_node_stats_by_batch_and_node.return_value = None

        job_tracker_service.fail_node_execution(
            job_run_id=JOB_RUN_ID,
            node_id=NODE_ID_1,
            node_name="MyNode",
            error="oops",
        )

        stored = mock_store.store_node_stats.call_args[1]["node_stats"]
        # time_taken should be 0 since start_time == end_time
        assert stored.time_taken == 0

    def test_empty_exception_str_uses_class_name(self, *, job_tracker_service, mock_store):
        """Exception with empty str() uses class name as error message."""
        mock_store.get_node_stats_by_batch_and_node.return_value = None

        class SilentError(Exception):
            def __str__(self):
                return ""

        job_tracker_service.fail_node_execution(
            job_run_id=JOB_RUN_ID,
            node_id=NODE_ID_1,
            node_name="MyNode",
            exception=SilentError(),
        )

        stored = mock_store.store_node_stats.call_args[1]["node_stats"]
        assert stored.error == "SilentError"


class TestAbortCancelSkipNoExistingNode:
    """Test abort/cancel/skip when existing_node is None."""

    def test_abort_no_existing_node(self, *, job_tracker_service, mock_store):
        """abort_node_execution works when no previous record exists."""
        mock_store.get_node_stats_by_batch_and_node.return_value = None

        job_tracker_service.abort_node_execution(
            job_run_id=JOB_RUN_ID,
            node_id=NODE_ID_1,
            node_name="MyNode",
            reason="pipeline abort",
        )

        stored = mock_store.store_node_stats.call_args[1]["node_stats"]
        assert stored.node_status == ExecutionStatus.ABORTED.value
        assert stored.total_docs == []

    def test_cancel_no_existing_node(self, *, job_tracker_service, mock_store):
        """cancel_node_execution works when no previous record exists."""
        mock_store.get_node_stats_by_batch_and_node.return_value = None

        job_tracker_service.cancel_node_execution(
            job_run_id=JOB_RUN_ID,
            node_id=NODE_ID_1,
            node_name="MyNode",
        )

        stored = mock_store.store_node_stats.call_args[1]["node_stats"]
        assert stored.node_status == ExecutionStatus.CANCELED.value

    def test_skip_no_existing_node(self, *, job_tracker_service, mock_store):
        """skip_node_execution works when no previous record exists."""
        mock_store.get_node_stats_by_batch_and_node.return_value = None

        job_tracker_service.skip_node_execution(
            job_run_id=JOB_RUN_ID,
            node_id=NODE_ID_1,
            node_name="MyNode",
            reason="no data",
            col_names=[],
        )

        stored = mock_store.store_node_stats.call_args[1]["node_stats"]
        assert stored.node_status == ExecutionStatus.SKIPPED.value
        assert stored.total_docs == []
