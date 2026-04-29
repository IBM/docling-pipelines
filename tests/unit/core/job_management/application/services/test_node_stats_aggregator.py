"""
Unit tests for NodeStatsAggregator - read-side aggregation tests

Tests cover:
- Pure non-batch aggregation
- Pure batch aggregation
- Mixed batch + non-batch aggregation
- Edge cases and error handling
"""

from datasift.core.job_management.application.services.node_stats_aggregator import (
    NodeStatsAggregator,
)
from datasift.core.job_management.domain.models import NodeStats

# Valid UUIDs for testing
NODE_1_ID = "12345678-1234-1234-1234-123456789abc"
NODE_2_ID = "22345678-1234-1234-1234-123456789abc"
NODE_3_ID = "32345678-1234-1234-1234-123456789abc"
BATCH_1_ID = "b1234567-1234-1234-1234-123456789abc"
BATCH_2_ID = "b2234567-1234-1234-1234-123456789abc"
JOB_ID = "j1234567-1234-1234-1234-123456789abc"
RUN_ID = "r1234567-1234-1234-1234-123456789abc"


class MockJobStatsStore:
    """Mock store for testing aggregator in isolation."""

    def __init__(self):
        self.node_stats_data = []
        self.batch_node_stats_data = {}

    def get_node_stats(self, *, job_run_id: str):
        """Return all node stats (batch and non-batch)."""
        return self.node_stats_data

    def get_batch_node_stats(self, *, job_run_id: str):
        """Return batch node stats grouped by node_id and batch_id."""
        return self.batch_node_stats_data


class TestNonBatchAggregation:
    """Test aggregation of non-batch node stats."""

    def test_single_non_batch_node(self):
        """Single non-batch node should be returned as-is."""
        store = MockJobStatsStore()
        node_stats = NodeStats(
            node_id=NODE_1_ID,
            name="Ingest",
            node_status="Completed",
            docs_completed=["doc1", "doc2"],
            docs_completed_count=2,
        )
        store.node_stats_data = [node_stats]

        aggregator = NodeStatsAggregator(job_stats_store=store)
        result = aggregator.get_aggregated_node_stats(job_id=JOB_ID, job_run_id=RUN_ID)

        assert len(result) == 1
        assert NODE_1_ID in result
        assert result[NODE_1_ID].node_status == "Completed"
        assert result[NODE_1_ID].docs_completed_count == 2

    def test_multiple_non_batch_nodes(self):
        """Multiple non-batch nodes should all be returned."""
        store = MockJobStatsStore()
        store.node_stats_data = [
            NodeStats(
                node_id=NODE_1_ID,
                name="Ingest",
                node_status="Completed",
                docs_completed_count=10,
            ),
            NodeStats(
                node_id=NODE_2_ID,
                name="Extract",
                node_status="Completed",
                docs_completed_count=10,
            ),
        ]

        aggregator = NodeStatsAggregator(job_stats_store=store)
        result = aggregator.get_aggregated_node_stats(job_id=JOB_ID, job_run_id=RUN_ID)

        assert len(result) == 2
        assert NODE_1_ID in result
        assert NODE_2_ID in result


class TestBatchAggregation:
    """Test aggregation of batch node stats."""

    def test_single_node_multiple_batches_completed(self):
        """Single node with multiple completed batches should aggregate correctly."""
        store = MockJobStatsStore()
        store.node_stats_data = [
            NodeStats(
                node_id=NODE_1_ID,
                name="Transform",
                node_status="Completed",
                batch_id=BATCH_1_ID,
                batch_num=0,
                docs_completed=["doc1", "doc2"],
                docs_completed_count=2,
                start_time=1000,
                end_time=1100,
                time_taken=100,
            ),
            NodeStats(
                node_id=NODE_1_ID,
                name="Transform",
                node_status="Completed",
                batch_id=BATCH_2_ID,
                batch_num=1,
                docs_completed=["doc3", "doc4"],
                docs_completed_count=2,
                start_time=1100,
                end_time=1200,
                time_taken=100,
            ),
        ]

        aggregator = NodeStatsAggregator(job_stats_store=store)
        result = aggregator.get_aggregated_node_stats(job_id=JOB_ID, job_run_id=RUN_ID)

        assert len(result) == 1
        assert NODE_1_ID in result

        aggregated = result[NODE_1_ID]
        assert aggregated.node_status == "Completed"
        assert aggregated.docs_completed_count == 4
        assert set(aggregated.docs_completed) == {"doc1", "doc2", "doc3", "doc4"}
        assert aggregated.start_time == 1000  # MIN
        assert aggregated.end_time == 1200  # MAX
        assert aggregated.batch_id is None  # Cleared for aggregated view
        assert aggregated.batch_num is None  # Cleared for aggregated view

    def test_single_node_mixed_batch_statuses(self):
        """Node with mixed batch statuses should aggregate to RUNNING."""
        store = MockJobStatsStore()
        store.node_stats_data = [
            NodeStats(
                node_id=NODE_1_ID,
                name="Transform",
                node_status="Completed",
                batch_id=BATCH_1_ID,
                batch_num=0,
                docs_completed=["doc1"],
                docs_completed_count=1,
            ),
            NodeStats(
                node_id=NODE_1_ID,
                name="Transform",
                node_status="Running",
                batch_id=BATCH_2_ID,
                batch_num=1,
                docs_completed=[],
                docs_completed_count=0,
            ),
        ]

        aggregator = NodeStatsAggregator(job_stats_store=store)
        result = aggregator.get_aggregated_node_stats(job_id=JOB_ID, job_run_id=RUN_ID)

        assert len(result) == 1
        aggregated = result[NODE_1_ID]
        # Should be RUNNING because one batch is still running
        assert aggregated.node_status == "Running"

    def test_single_node_all_batches_pending(self):
        """Node with all batches PENDING should be skipped."""
        store = MockJobStatsStore()
        store.node_stats_data = [
            NodeStats(
                node_id=NODE_1_ID,
                name="Transform",
                node_status="Pending",
                batch_id=BATCH_1_ID,
                batch_num=0,
            ),
            NodeStats(
                node_id=NODE_1_ID,
                name="Transform",
                node_status="Queued",
                batch_id=BATCH_2_ID,
                batch_num=1,
            ),
        ]

        aggregator = NodeStatsAggregator(job_stats_store=store)
        result = aggregator.get_aggregated_node_stats(job_id=JOB_ID, job_run_id=RUN_ID)

        # Should be empty because all batches are pending/queued
        assert len(result) == 0


class TestMixedBatchAndNonBatchAggregation:
    """Test aggregation with both batch and non-batch nodes."""

    def test_mixed_execution(self):
        """Flow with both batch and non-batch nodes should aggregate correctly."""
        store = MockJobStatsStore()
        store.node_stats_data = [
            # Non-batch node (e.g., Ingest)
            NodeStats(
                node_id=NODE_1_ID,
                name="Ingest",
                node_status="Completed",
                docs_completed=["doc1", "doc2", "doc3"],
                docs_completed_count=3,
            ),
            # Batch node with 2 batches (e.g., Transform)
            NodeStats(
                node_id=NODE_2_ID,
                name="Transform",
                node_status="Completed",
                batch_id=BATCH_1_ID,
                batch_num=0,
                docs_completed=["doc1"],
                docs_completed_count=1,
            ),
            NodeStats(
                node_id=NODE_2_ID,
                name="Transform",
                node_status="Completed",
                batch_id=BATCH_2_ID,
                batch_num=1,
                docs_completed=["doc2", "doc3"],
                docs_completed_count=2,
            ),
            # Another non-batch node (e.g., VectorDB)
            NodeStats(
                node_id=NODE_3_ID,
                name="VectorDB",
                node_status="Completed",
                docs_completed=["doc1", "doc2", "doc3"],
                docs_completed_count=3,
            ),
        ]

        aggregator = NodeStatsAggregator(job_stats_store=store)
        result = aggregator.get_aggregated_node_stats(job_id=JOB_ID, job_run_id=RUN_ID)

        assert len(result) == 3

        # Non-batch node should be unchanged
        assert result[NODE_1_ID].node_status == "Completed"
        assert result[NODE_1_ID].docs_completed_count == 3
        assert result[NODE_1_ID].batch_id is None

        # Batch node should be aggregated
        assert result[NODE_2_ID].node_status == "Completed"
        assert result[NODE_2_ID].docs_completed_count == 3
        assert result[NODE_2_ID].batch_id is None  # Cleared
        assert result[NODE_2_ID].batch_num is None  # Cleared

        # Another non-batch node
        assert result[NODE_3_ID].node_status == "Completed"
        assert result[NODE_3_ID].docs_completed_count == 3


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_node_stats(self):
        """Empty node stats should return empty dict."""
        store = MockJobStatsStore()
        store.node_stats_data = []

        aggregator = NodeStatsAggregator(job_stats_store=store)
        result = aggregator.get_aggregated_node_stats(job_id=JOB_ID, job_run_id=RUN_ID)

        assert result == {}

    def test_get_batch_node_stats_passthrough(self):
        """get_batch_node_stats should pass through to store."""
        store = MockJobStatsStore()
        store.batch_node_stats_data = {
            NODE_1_ID: {BATCH_1_ID: NodeStats(node_id=NODE_1_ID, name="Test", batch_id=BATCH_1_ID, batch_num=0)}
        }

        aggregator = NodeStatsAggregator(job_stats_store=store)
        result = aggregator.get_batch_node_stats(job_id=JOB_ID, job_run_id=RUN_ID)

        assert NODE_1_ID in result
        assert BATCH_1_ID in result[NODE_1_ID]


class TestDocumentListAggregation:
    """Test document list aggregation (UNION strategy)."""

    def test_document_list_deduplication(self):
        """Document lists should be deduplicated across batches."""
        store = MockJobStatsStore()
        store.node_stats_data = [
            NodeStats(
                node_id=NODE_1_ID,
                name="Transform",
                node_status="Completed",
                batch_id=BATCH_1_ID,
                batch_num=0,
                total_docs=["doc1", "doc2"],
                docs_completed=["doc1"],
                failed_docs=["doc2"],
            ),
            NodeStats(
                node_id=NODE_1_ID,
                name="Transform",
                node_status="Completed",
                batch_id=BATCH_2_ID,
                batch_num=1,
                total_docs=["doc2", "doc3"],  # doc2 overlaps
                docs_completed=["doc2", "doc3"],
                failed_docs=[],
            ),
        ]

        aggregator = NodeStatsAggregator(job_stats_store=store)
        result = aggregator.get_aggregated_node_stats(job_id=JOB_ID, job_run_id=RUN_ID)

        aggregated = result[NODE_1_ID]
        # Should deduplicate: doc1, doc2, doc3
        assert set(aggregated.total_docs) == {"doc1", "doc2", "doc3"}
        assert set(aggregated.docs_completed) == {"doc1", "doc2", "doc3"}
        assert set(aggregated.failed_docs) == {"doc2"}
