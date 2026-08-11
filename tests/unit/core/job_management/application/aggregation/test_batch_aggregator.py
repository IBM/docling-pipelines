"""
Unit tests for batch aggregation logic.

Tests cover:
- Status determination with PENDING/QUEUED batches
- Status determination with SKIPPED batches
- Proper handling of mixed batch statuses
"""

from docpipe.core.constants.constants import ExecutionStatus
from docpipe.core.job_management.application.aggregation.batch_aggregator import (
    _determine_aggregated_status,
    count_batches_by_status,
)
from docpipe.core.job_management.domain.models.node_stats import NodeStats


class TestDetermineAggregatedStatus:
    """Test _determine_aggregated_status function."""

    def test_all_pending_returns_running(self):
        """Test that all PENDING batches result in RUNNING status."""
        status_counts = {
            ExecutionStatus.COMPLETED.value: 0,
            ExecutionStatus.FAILED.value: 0,
            ExecutionStatus.SKIPPED.value: 0,
            ExecutionStatus.RUNNING.value: 0,
            ExecutionStatus.PENDING.value: 5,
            ExecutionStatus.QUEUED.value: 0,
            ExecutionStatus.CANCELING.value: 0,
            ExecutionStatus.CANCELED.value: 0,
            ExecutionStatus.COMPLETED_WITH_ERRORS.value: 0,
            ExecutionStatus.COMPLETED_WITH_WARNINGS.value: 0,
        }

        result = _determine_aggregated_status(status_counts=status_counts, total_batches=5)

        assert result == ExecutionStatus.RUNNING.value

    def test_all_skipped_returns_skipped(self):
        """Test that all SKIPPED batches result in SKIPPED status."""
        status_counts = {
            ExecutionStatus.COMPLETED.value: 0,
            ExecutionStatus.FAILED.value: 0,
            ExecutionStatus.SKIPPED.value: 5,
            ExecutionStatus.RUNNING.value: 0,
            ExecutionStatus.PENDING.value: 0,
            ExecutionStatus.QUEUED.value: 0,
            ExecutionStatus.CANCELING.value: 0,
            ExecutionStatus.CANCELED.value: 0,
            ExecutionStatus.COMPLETED_WITH_ERRORS.value: 0,
            ExecutionStatus.COMPLETED_WITH_WARNINGS.value: 0,
        }

        result = _determine_aggregated_status(status_counts=status_counts, total_batches=5)

        assert result == ExecutionStatus.SKIPPED.value

    def test_completed_and_skipped_returns_completed(self):
        """Test that mix of COMPLETED and SKIPPED returns COMPLETED."""
        status_counts = {
            ExecutionStatus.COMPLETED.value: 3,
            ExecutionStatus.FAILED.value: 0,
            ExecutionStatus.SKIPPED.value: 2,
            ExecutionStatus.RUNNING.value: 0,
            ExecutionStatus.PENDING.value: 0,
            ExecutionStatus.QUEUED.value: 0,
            ExecutionStatus.CANCELING.value: 0,
            ExecutionStatus.CANCELED.value: 0,
            ExecutionStatus.COMPLETED_WITH_ERRORS.value: 0,
            ExecutionStatus.COMPLETED_WITH_WARNINGS.value: 0,
        }

        result = _determine_aggregated_status(status_counts=status_counts, total_batches=5)

        assert result == ExecutionStatus.COMPLETED.value

    def test_completed_failed_skipped_returns_completed_with_errors(self):
        """Test that mix of COMPLETED, FAILED, and SKIPPED returns COMPLETED_WITH_ERRORS."""
        status_counts = {
            ExecutionStatus.COMPLETED.value: 2,
            ExecutionStatus.FAILED.value: 1,
            ExecutionStatus.SKIPPED.value: 2,
            ExecutionStatus.RUNNING.value: 0,
            ExecutionStatus.PENDING.value: 0,
            ExecutionStatus.QUEUED.value: 0,
            ExecutionStatus.CANCELING.value: 0,
            ExecutionStatus.CANCELED.value: 0,
            ExecutionStatus.COMPLETED_WITH_ERRORS.value: 0,
            ExecutionStatus.COMPLETED_WITH_WARNINGS.value: 0,
        }

        result = _determine_aggregated_status(status_counts=status_counts, total_batches=5)

        # Should be CompletedWithErrors (mix of completed and failed)
        # NOT Running (because skipped batches don't cause running status)
        assert result == ExecutionStatus.COMPLETED_WITH_ERRORS.value

    def test_all_failed_returns_failed(self):
        """Test that all FAILED batches result in FAILED status."""
        status_counts = {
            ExecutionStatus.COMPLETED.value: 0,
            ExecutionStatus.FAILED.value: 5,
            ExecutionStatus.SKIPPED.value: 0,
            ExecutionStatus.RUNNING.value: 0,
            ExecutionStatus.PENDING.value: 0,
            ExecutionStatus.QUEUED.value: 0,
            ExecutionStatus.CANCELING.value: 0,
            ExecutionStatus.CANCELED.value: 0,
            ExecutionStatus.COMPLETED_WITH_ERRORS.value: 0,
            ExecutionStatus.COMPLETED_WITH_WARNINGS.value: 0,
        }

        result = _determine_aggregated_status(status_counts=status_counts, total_batches=5)

        assert result == ExecutionStatus.FAILED.value

    def test_pending_with_completed_returns_running(self):
        """Test that any PENDING batches result in RUNNING status even with completed batches."""
        status_counts = {
            ExecutionStatus.COMPLETED.value: 3,
            ExecutionStatus.FAILED.value: 0,
            ExecutionStatus.SKIPPED.value: 0,
            ExecutionStatus.RUNNING.value: 0,
            ExecutionStatus.PENDING.value: 2,  # Still pending
            ExecutionStatus.QUEUED.value: 0,
            ExecutionStatus.CANCELING.value: 0,
            ExecutionStatus.CANCELED.value: 0,
            ExecutionStatus.COMPLETED_WITH_ERRORS.value: 0,
            ExecutionStatus.COMPLETED_WITH_WARNINGS.value: 0,
        }

        result = _determine_aggregated_status(status_counts=status_counts, total_batches=5)

        # Should be RUNNING because there are still pending batches
        assert result == ExecutionStatus.RUNNING.value

    def test_no_pending_after_skip_returns_terminal_status(self):
        """Test that after marking pending as skipped, proper terminal status is returned."""
        # Scenario: After fail-fast, pending batches are marked as skipped
        status_counts = {
            ExecutionStatus.COMPLETED.value: 2,
            ExecutionStatus.FAILED.value: 1,
            ExecutionStatus.SKIPPED.value: 2,  # Previously pending, now skipped
            ExecutionStatus.RUNNING.value: 0,
            ExecutionStatus.PENDING.value: 0,  # No more pending
            ExecutionStatus.QUEUED.value: 0,
            ExecutionStatus.CANCELING.value: 0,
            ExecutionStatus.CANCELED.value: 0,
            ExecutionStatus.COMPLETED_WITH_ERRORS.value: 0,
            ExecutionStatus.COMPLETED_WITH_WARNINGS.value: 0,
        }

        result = _determine_aggregated_status(status_counts=status_counts, total_batches=5)

        # Should be CompletedWithErrors (mix of completed and failed)
        # NOT Running (because no pending batches remain)
        assert result == ExecutionStatus.COMPLETED_WITH_ERRORS.value

    def _make_counts(self, **kwargs: int) -> dict[str, int]:
        """Helper: build a zero-initialised status_counts dict with overrides."""
        base = {s.value: 0 for s in ExecutionStatus}
        for key, val in kwargs.items():
            base[key] = val
        return base

    def test_canceled_and_skipped_returns_skipped(self):
        """Canceled + Skipped only (screenshot case) must resolve to Skipped."""
        counts = self._make_counts(Canceled=10, Skipped=10)
        result = _determine_aggregated_status(status_counts=counts, total_batches=20)
        assert result == ExecutionStatus.SKIPPED.value

    def test_all_canceled_returns_canceled(self):
        """All-Canceled batches must resolve to Canceled."""
        counts = self._make_counts(Canceled=5)
        result = _determine_aggregated_status(status_counts=counts, total_batches=5)
        assert result == ExecutionStatus.CANCELED.value

    def test_canceled_and_completed_returns_completed_with_warnings(self):
        """Canceled + Completed mixture must resolve to CompletedWithWarnings."""
        counts = self._make_counts(Canceled=5, Completed=15)
        result = _determine_aggregated_status(status_counts=counts, total_batches=20)
        assert result == ExecutionStatus.COMPLETED_WITH_WARNINGS.value

    def test_canceled_skipped_and_completed_returns_completed_with_warnings(self):
        """Canceled + Skipped + Completed mixture must resolve to CompletedWithWarnings."""
        counts = self._make_counts(Canceled=5, Skipped=5, Completed=10)
        result = _determine_aggregated_status(status_counts=counts, total_batches=20)
        assert result == ExecutionStatus.COMPLETED_WITH_WARNINGS.value

    def test_canceled_failed_and_skipped_returns_failed(self):
        """Canceled + Failed + Skipped (no completed) must resolve to Failed."""
        counts = self._make_counts(Canceled=3, Failed=3, Skipped=4)
        result = _determine_aggregated_status(status_counts=counts, total_batches=10)
        assert result == ExecutionStatus.FAILED.value


class TestCountBatchesByStatus:
    """Test count_batches_by_status function."""

    def test_count_mixed_statuses(self):
        """Test counting batches with mixed statuses."""
        batch_records = [
            NodeStats(
                id="node1",
                name="extract",
                node_status=ExecutionStatus.COMPLETED.value,
                batch_id="batch-1",
                total_docs=[],
                docs_completed=[],
                failed_docs=[],
                skipped_docs=[],
                col_names=[],
            ),
            NodeStats(
                id="node1",
                name="extract",
                node_status=ExecutionStatus.FAILED.value,
                batch_id="batch-2",
                total_docs=[],
                docs_completed=[],
                failed_docs=[],
                skipped_docs=[],
                col_names=[],
            ),
            NodeStats(
                id="node1",
                name="extract",
                node_status=ExecutionStatus.SKIPPED.value,
                batch_id="batch-3",
                total_docs=[],
                docs_completed=[],
                failed_docs=[],
                skipped_docs=[],
                col_names=[],
            ),
            NodeStats(
                id="node1",
                name="extract",
                node_status=ExecutionStatus.PENDING.value,
                batch_id="batch-4",
                total_docs=[],
                docs_completed=[],
                failed_docs=[],
                skipped_docs=[],
                col_names=[],
            ),
        ]

        result = count_batches_by_status(batch_records=batch_records)

        assert result[ExecutionStatus.COMPLETED.value] == 1
        assert result[ExecutionStatus.FAILED.value] == 1
        assert result[ExecutionStatus.SKIPPED.value] == 1
        assert result[ExecutionStatus.PENDING.value] == 1
        assert result[ExecutionStatus.RUNNING.value] == 0

    def test_count_all_pending(self):
        """Test counting when all batches are pending."""
        batch_records = [
            NodeStats(
                id="node1",
                name="extract",
                node_status=ExecutionStatus.PENDING.value,
                batch_id=f"batch-{i}",
                total_docs=[],
                docs_completed=[],
                failed_docs=[],
                skipped_docs=[],
                col_names=[],
            )
            for i in range(5)
        ]

        result = count_batches_by_status(batch_records=batch_records)

        assert result[ExecutionStatus.PENDING.value] == 5
        assert result[ExecutionStatus.COMPLETED.value] == 0
        assert result[ExecutionStatus.FAILED.value] == 0
