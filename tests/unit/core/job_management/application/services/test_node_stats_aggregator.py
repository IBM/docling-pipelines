"""
Unit tests for NodeStatsAggregator - read-side aggregation tests

Tests cover:
- Pure non-batch aggregation
- Pure batch aggregation
- Mixed batch + non-batch aggregation
- Edge cases and error handling
"""

from docpipe.core.job_management.application.services.node_stats_aggregator import (
    NodeStatsAggregator,
)
from docpipe.core.job_management.domain.models import NodeStats

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


class TestStageBasedProgressAggregation:
    """Test aggregation of stage-based progress for extraction and classification operators."""

    def test_extraction_stage_progress_aggregation(self):
        """Extraction operator with stage-based progress should aggregate correctly."""
        store = MockJobStatsStore()
        store.node_stats_data = [
            NodeStats(
                node_id=NODE_1_ID,
                name="Extract",
                node_status="Completed",
                batch_id=BATCH_1_ID,
                batch_num=0,
                total_docs=["doc1", "doc2", "doc3"],
                docs_completed=["doc1", "doc2", "doc3"],
                failed_docs=[],
                node_metadata={
                    "node_metadata": {
                        "extraction_stage_progress": {
                            "text_extraction": {
                                "stage_status": "completed",
                                "documents_total": 3,
                                "documents_completed": 3,
                                "documents_failed": 0,
                                "progress_percentage": 100.0,
                            },
                            "entity_extraction": {
                                "stage_status": "completed",
                                "documents_total": 3,
                                "documents_completed": 3,
                                "documents_failed": 0,
                                "progress_percentage": 100.0,
                            },
                        }
                    }
                },
            ),
            NodeStats(
                node_id=NODE_1_ID,
                name="Extract",
                node_status="Completed",
                batch_id=BATCH_2_ID,
                batch_num=1,
                total_docs=["doc4", "doc5"],
                docs_completed=["doc4", "doc5"],
                failed_docs=[],
                node_metadata={
                    "node_metadata": {
                        "extraction_stage_progress": {
                            "text_extraction": {
                                "stage_status": "completed",
                                "documents_total": 2,
                                "documents_completed": 2,
                                "documents_failed": 0,
                                "progress_percentage": 100.0,
                            },
                            "entity_extraction": {
                                "stage_status": "completed",
                                "documents_total": 2,
                                "documents_completed": 2,
                                "documents_failed": 0,
                                "progress_percentage": 100.0,
                            },
                        }
                    }
                },
            ),
        ]

        aggregator = NodeStatsAggregator(job_stats_store=store)
        result = aggregator.get_aggregated_node_stats(job_id=JOB_ID, job_run_id=RUN_ID)

        assert len(result) == 1
        aggregated = result[NODE_1_ID]

        # Check that stage progress is converted to user-friendly fields
        metadata = aggregated.node_metadata["node_metadata"]

        # Should have user-friendly extraction fields
        assert "Text Extracted" in metadata
        assert "Entities Extracted" in metadata

        # Both stages completed (5 of 5)
        assert "5 of 5" in metadata["Text Extracted"]
        assert "5 of 5" in metadata["Entities Extracted"]

        # Should also have core document fields
        assert metadata["total_docs_count"] == 5
        assert metadata["processed_docs"] == 5

    def test_extraction_stage_progress_uses_started_batches_only_for_stage_totals(self):
        """Stage totals should accumulate only started batches, while document totals still include queued work."""
        store = MockJobStatsStore()
        store.node_stats_data = [
            NodeStats(
                node_id=NODE_1_ID,
                name="Extract",
                node_status="Completed",
                batch_id=BATCH_1_ID,
                batch_num=0,
                total_docs=["doc1", "doc2", "doc3"],
                docs_completed=["doc1", "doc2", "doc3"],
                failed_docs=[],
                node_metadata={
                    "node_metadata": {
                        "extraction_stage_progress": {
                            "text_extraction": {
                                "stage_status": "completed",
                                "documents_total": 3,
                                "documents_completed": 3,
                                "documents_failed": 0,
                                "progress_percentage": 100.0,
                            },
                            "entity_extraction": {
                                "stage_status": "completed",
                                "documents_total": 3,
                                "documents_completed": 3,
                                "documents_failed": 0,
                                "progress_percentage": 100.0,
                            },
                        }
                    }
                },
            ),
            NodeStats(
                node_id=NODE_1_ID,
                name="Extract",
                node_status="Completed",
                batch_id=BATCH_2_ID,
                batch_num=1,
                total_docs=["doc4", "doc5", "doc6"],
                docs_completed=["doc4", "doc5", "doc6"],
                failed_docs=[],
                node_metadata={
                    "node_metadata": {
                        "extraction_stage_progress": {
                            "text_extraction": {
                                "stage_status": "completed",
                                "documents_total": 3,
                                "documents_completed": 3,
                                "documents_failed": 0,
                                "progress_percentage": 100.0,
                            },
                            "entity_extraction": {
                                "stage_status": "running",
                                "documents_total": 3,
                                "documents_completed": 1,
                                "documents_failed": 0,
                                "progress_percentage": 33.33,
                            },
                        }
                    }
                },
            ),
            NodeStats(
                node_id=NODE_1_ID,
                name="Extract",
                node_status="Pending",
                batch_id="b3234567-1234-1234-1234-123456789abc",
                batch_num=2,
                total_docs=["doc7", "doc8", "doc9", "doc10"],
                docs_completed=[],
                failed_docs=[],
                node_metadata={"node_metadata": {}},
            ),
        ]

        aggregator = NodeStatsAggregator(job_stats_store=store)
        result = aggregator.get_aggregated_node_stats(job_id=JOB_ID, job_run_id=RUN_ID)

        aggregated = result[NODE_1_ID]
        metadata = aggregated.node_metadata["node_metadata"]

        # Overall document counts include all batches, including pending.
        assert metadata["total_docs_count"] == 10
        assert metadata["processed_docs"] == 6
        assert aggregated.docs_completed_count == 6

        # Stage progress counts only started batches with stage metadata.
        assert metadata["Text Extracted"] == "6 of 6 (more in queue)"
        assert metadata["Entities Extracted"] == "4 of 6 (more in queue)"
        assert metadata["Progress"] == "2 of 3 batches (66.67%) | Completed: 2"

    def test_classification_progress_aggregation(self):
        """Classification operator with progress tracking should aggregate correctly."""
        store = MockJobStatsStore()
        store.node_stats_data = [
            NodeStats(
                node_id=NODE_1_ID,
                name="Classifier",
                node_status="Completed",
                batch_id=BATCH_1_ID,
                batch_num=0,
                total_docs=["doc1", "doc2", "doc3"],
                docs_completed=["doc1", "doc2", "doc3"],
                failed_docs=[],
                node_metadata={
                    "node_metadata": {
                        "classification_running": 3,
                        "classification_completed": 3,
                        "progress_percentage": "100.00%",
                    }
                },
            ),
            NodeStats(
                node_id=NODE_1_ID,
                name="Classifier",
                node_status="Running",
                batch_id=BATCH_2_ID,
                batch_num=1,
                total_docs=["doc4", "doc5"],
                docs_completed=["doc4"],
                failed_docs=[],
                node_metadata={
                    "node_metadata": {
                        "classification_running": 2,
                        "classification_completed": 1,
                        "progress_percentage": "50.00%",
                    }
                },
            ),
        ]

        aggregator = NodeStatsAggregator(job_stats_store=store)
        result = aggregator.get_aggregated_node_stats(job_id=JOB_ID, job_run_id=RUN_ID)

        assert len(result) == 1
        aggregated = result[NODE_1_ID]

        # Check that transient fields are removed and persistent fields are present
        metadata = aggregated.node_metadata["node_metadata"]
        assert "classification_running" not in metadata
        assert "classification_completed" not in metadata
        assert "progress_percentage" not in metadata

        # Check aggregated persistent fields (4 completed out of 5 total)
        assert metadata["total_docs_count"] == 5
        assert metadata["processed_docs"] == 4

        # Should have Documents Classified field showing progress
        assert "Documents Classified" in metadata
        assert "4 of 5" in metadata["Documents Classified"]

    def test_mixed_extraction_and_classification_progress(self):
        """Flow with both extraction and classification operators should aggregate correctly."""
        store = MockJobStatsStore()
        store.node_stats_data = [
            # Extraction node with stage progress
            NodeStats(
                node_id=NODE_1_ID,
                name="Extract",
                node_status="Completed",
                batch_id=BATCH_1_ID,
                batch_num=0,
                total_docs=["doc1", "doc2", "doc3"],
                docs_completed=["doc1", "doc2", "doc3"],
                failed_docs=[],
                node_metadata={
                    "node_metadata": {
                        "extraction_stage_progress": {
                            "text_extraction": {
                                "stage_status": "completed",
                                "documents_total": 3,
                                "documents_completed": 3,
                                "documents_failed": 0,
                                "progress_percentage": 100.0,
                            }
                        }
                    }
                },
            ),
            # Classification node with progress
            NodeStats(
                node_id=NODE_2_ID,
                name="Classifier",
                node_status="Running",
                batch_id=BATCH_1_ID,
                batch_num=0,
                total_docs=["doc1", "doc2", "doc3"],
                docs_completed=["doc1", "doc2"],
                failed_docs=[],
                node_metadata={
                    "node_metadata": {
                        "classification_running": 3,
                        "classification_completed": 2,
                        "progress_percentage": "66.67%",
                    }
                },
            ),
        ]

        aggregator = NodeStatsAggregator(job_stats_store=store)
        result = aggregator.get_aggregated_node_stats(job_id=JOB_ID, job_run_id=RUN_ID)

        assert len(result) == 2

        # Extraction node should have user-friendly fields
        extract_metadata = result[NODE_1_ID].node_metadata["node_metadata"]
        assert "Text Extracted" in extract_metadata
        assert "3 of 3" in extract_metadata["Text Extracted"]

        # Classification node should have aggregated progress
        classify_metadata = result[NODE_2_ID].node_metadata["node_metadata"]
        assert "classification_running" not in classify_metadata
        assert classify_metadata["total_docs_count"] == 3
        assert classify_metadata["processed_docs"] == 2
        assert "Documents Classified" in classify_metadata
        assert "2 of 3" in classify_metadata["Documents Classified"]
