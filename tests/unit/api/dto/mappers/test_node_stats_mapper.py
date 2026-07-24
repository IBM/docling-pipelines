"""
Unit tests for NodeStatsMapper.

Tests cover:
- Conversion from NodeStats domain model to NodeStatsDto
- Conversion to NodeMetadataItem
- Log string formatting for different node states
- Handling of optional fields
"""

import pytest

from docpipe.api.dto.mappers.node_stats_mapper import NodeStatsMapper
from docpipe.core.constants.constants import ExecutionStatus
from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.job_management.domain.models import NodeStats


@pytest.fixture
def sample_node_stats():
    """Sample node stats with all fields populated."""
    return NodeStats(
        node_id="12345678-1234-1234-1234-123456789abc",
        name="TestOperator",
        node_status=ExecutionStatus.COMPLETED.value,
        start_time=1704067200,
        end_time=1704067260,
        time_taken=60,
        col_names=["doc_id", "content", "metadata"],
        total_docs=["doc1", "doc2", "doc3"],
        docs_completed=["doc1", "doc2", "doc3"],
        docs_completed_count=3,
        failed_docs=[],
        skipped_docs=[],
        node_metadata={
            "id": "12345678-1234-1234-1234-123456789abc",
            "operator": "TestOperator",
            OperatorConstants.Metadata.NODE_METADATA: {"processed": 3, "format": "pdf"},
        },
        batch_id="b2345678-1234-1234-1234-123456789abc",
        batch_num=0,
    )


class TestToDtoConversion:
    """Test conversion from NodeStats to NodeStatsDto."""

    def test_to_dto_all_fields(self, sample_node_stats):
        """Should convert all fields correctly."""
        dto = NodeStatsMapper.to_dto(sample_node_stats)

        assert dto.node_id == "12345678-1234-1234-1234-123456789abc"
        assert dto.name == "TestOperator"
        assert dto.node_status == ExecutionStatus.COMPLETED.value
        assert dto.start_time == 1704067200
        assert dto.end_time == 1704067260
        assert dto.time_taken == 60
        assert dto.col_names == ["doc_id", "content", "metadata"]
        assert dto.batch_id == "b2345678-1234-1234-1234-123456789abc"
        assert dto.batch_num == 0

    def test_to_dto_document_counts(self, sample_node_stats):
        """Should convert document lists to counts."""
        dto = NodeStatsMapper.to_dto(sample_node_stats)

        assert dto.total_docs == 3
        assert dto.docs_completed == 3
        assert dto.failed_docs == 0
        assert dto.skipped_docs == 0
        assert dto.docs_completed_count == 3

    def test_to_dto_with_error(self):
        """Should include error field when present."""
        node_stats = NodeStats(
            node_id="12345678-1234-1234-1234-123456789abc",
            name="FailedNode",
            node_status=ExecutionStatus.FAILED.value,
            error="Connection timeout",
            start_time=1704067200,
        )

        dto = NodeStatsMapper.to_dto(node_stats)
        assert dto.error == "Connection timeout"

    def test_to_dto_minimal_fields(self):
        """Should handle minimal node stats with defaults."""
        node_stats = NodeStats(
            node_id="12345678-1234-1234-1234-123456789abc",
            name="MinimalNode",
            node_status=ExecutionStatus.RUNNING.value,
            start_time=1704067200,
        )

        dto = NodeStatsMapper.to_dto(node_stats)

        assert dto.node_id == "12345678-1234-1234-1234-123456789abc"
        assert dto.name == "MinimalNode"
        assert dto.time_taken == 0  # Default
        assert dto.col_names == []  # Default
        assert dto.total_docs == 0  # Empty list count
        assert dto.failed_docs == 0
        assert dto.skipped_docs == 0

    def test_to_dto_empty_lists(self):
        """Should handle empty lists correctly."""
        node_stats = NodeStats(
            node_id="12345678-1234-1234-1234-123456789abc",
            name="TestNode",
            node_status=ExecutionStatus.COMPLETED.value,
            start_time=1704067200,
            col_names=[],
            total_docs=[],
            failed_docs=[],
            skipped_docs=[],
            docs_completed=[],
        )

        dto = NodeStatsMapper.to_dto(node_stats)

        assert dto.col_names == []
        assert dto.total_docs == 0
        assert dto.failed_docs == 0
        assert dto.skipped_docs == 0
        assert dto.docs_completed == 0

    def test_to_dto_preserves_metadata(self, sample_node_stats):
        """Should preserve node_metadata structure."""
        dto = NodeStatsMapper.to_dto(sample_node_stats)

        assert dto.node_metadata is not None
        assert dto.node_metadata["id"] == "12345678-1234-1234-1234-123456789abc"
        assert dto.node_metadata["operator"] == "TestOperator"
        assert OperatorConstants.Metadata.NODE_METADATA in dto.node_metadata


class TestToNodeMetadataItem:
    """Test conversion to NodeMetadataItem."""

    def test_to_node_metadata_item_with_metadata(self, sample_node_stats):
        """Should extract metadata correctly."""
        item = NodeStatsMapper.to_node_metadata_item("12345678-1234-1234-1234-123456789abc", sample_node_stats)

        assert item.id == "12345678-1234-1234-1234-123456789abc"
        assert item.operator == "TestOperator"
        assert item.node_metadata == {"processed": 3, "format": "pdf"}

    def test_to_node_metadata_item_without_metadata(self):
        """Should handle missing node_metadata."""
        node_stats = NodeStats(
            node_id="12345678-1234-1234-1234-123456789abc",
            name="TestNode",
            node_status=ExecutionStatus.COMPLETED.value,
            start_time=1704067200,
            node_metadata=None,
        )

        item = NodeStatsMapper.to_node_metadata_item("12345678-1234-1234-1234-123456789abc", node_stats)

        assert item.id == "12345678-1234-1234-1234-123456789abc"
        assert item.operator == "TestNode"
        assert item.node_metadata is None

    def test_to_node_metadata_item_empty_metadata(self):
        """Should handle empty node_metadata dict."""
        node_stats = NodeStats(
            node_id="12345678-1234-1234-1234-123456789abc",
            name="TestNode",
            node_status=ExecutionStatus.COMPLETED.value,
            start_time=1704067200,
            node_metadata={},
        )

        item = NodeStatsMapper.to_node_metadata_item("12345678-1234-1234-1234-123456789abc", node_stats)

        assert item.id == "12345678-1234-1234-1234-123456789abc"
        assert item.operator == "TestNode"
        assert item.node_metadata is None


class TestToLogString:
    """Test log string formatting."""

    def test_to_log_string_completed_node(self, sample_node_stats):
        """Should format completed node log correctly."""
        log_str = NodeStatsMapper.to_log_string(
            node_id="12345678-1234-1234-1234-123456789abc", node_stat=sample_node_stats
        )

        assert "Starting execution: Step Name: TestOperator" in log_str
        assert "Schema:" in log_str
        assert "doc_id: string" in log_str
        assert "content: string" in log_str
        assert "metadata: string" in log_str
        assert "Operator Metadata:" in log_str
        assert "Completed execution: TestOperator, time= 60.00 seconds" in log_str

    def test_to_log_string_failed_node(self):
        """Should format failed node log correctly."""
        node_stats = NodeStats(
            node_id="12345678-1234-1234-1234-123456789abc",
            name="FailedNode",
            node_status=ExecutionStatus.FAILED.value,
            error="Connection timeout after 30s",
            start_time=1704067200,
            end_time=1704067230,
            time_taken=30,
        )

        log_str = NodeStatsMapper.to_log_string(node_id="12345678-1234-1234-1234-123456789abc", node_stat=node_stats)

        assert "Starting execution: Step Name: FailedNode" in log_str
        assert "Failed execution: FailedNode, time= 30.00 seconds" in log_str
        assert "Error Details:" in log_str
        assert "Connection timeout after 30s" in log_str

    def test_to_log_string_skipped_node(self):
        """Should format skipped node log correctly."""
        node_stats = NodeStats(
            node_id="12345678-1234-1234-1234-123456789abc",
            name="SkippedNode",
            node_status=ExecutionStatus.SKIPPED.value,
            start_time=1704067200,
            end_time=1704067205,
            time_taken=5,
        )

        log_str = NodeStatsMapper.to_log_string(node_id="12345678-1234-1234-1234-123456789abc", node_stat=node_stats)

        assert "Starting execution: Step Name: SkippedNode" in log_str
        assert "Skipped execution: SkippedNode, time= 5.00 seconds" in log_str

    def test_to_log_string_running_node(self):
        """Should not include completion status for running node."""
        node_stats = NodeStats(
            node_id="12345678-1234-1234-1234-123456789abc",
            name="RunningNode",
            node_status=ExecutionStatus.RUNNING.value,
            start_time=1704067200,
        )

        log_str = NodeStatsMapper.to_log_string(node_id="12345678-1234-1234-1234-123456789abc", node_stat=node_stats)

        assert "Starting execution: Step Name: RunningNode" in log_str
        assert "Completed execution" not in log_str
        assert "Failed execution" not in log_str

    def test_to_log_string_without_schema(self):
        """Should handle empty col_names."""
        node_stats = NodeStats(
            node_id="12345678-1234-1234-1234-123456789abc",
            name="NoSchemaNode",
            node_status=ExecutionStatus.COMPLETED.value,
            start_time=1704067200,
            end_time=1704067260,
            time_taken=60,
            col_names=[],
        )

        log_str = NodeStatsMapper.to_log_string(node_id="12345678-1234-1234-1234-123456789abc", node_stat=node_stats)

        assert "Starting execution: Step Name: NoSchemaNode" in log_str
        assert "Schema:" not in log_str
        assert "Completed execution: NoSchemaNode" in log_str

    def test_to_log_string_without_metadata(self):
        """Should handle missing node_metadata."""
        node_stats = NodeStats(
            node_id="12345678-1234-1234-1234-123456789abc",
            name="NoMetadataNode",
            node_status=ExecutionStatus.COMPLETED.value,
            start_time=1704067200,
            end_time=1704067260,
            time_taken=60,
            node_metadata=None,
        )

        log_str = NodeStatsMapper.to_log_string(node_id="12345678-1234-1234-1234-123456789abc", node_stat=node_stats)

        assert "Starting execution: Step Name: NoMetadataNode" in log_str
        assert "Operator Metadata:" not in log_str
        assert "Completed execution: NoMetadataNode" in log_str

    def test_to_log_string_with_metadata_json_formatting(self, sample_node_stats):
        """Should format metadata as JSON."""
        log_str = NodeStatsMapper.to_log_string(
            node_id="12345678-1234-1234-1234-123456789abc", node_stat=sample_node_stats
        )

        assert "Operator Metadata:" in log_str
        # Check JSON structure is present
        assert '"id": "12345678-1234-1234-1234-123456789abc"' in log_str
        assert '"operator": "TestOperator"' in log_str

    def test_to_log_string_zero_time_taken(self):
        """Should handle zero time_taken."""
        node_stats = NodeStats(
            node_id="12345678-1234-1234-1234-123456789abc",
            name="QuickNode",
            node_status=ExecutionStatus.COMPLETED.value,
            start_time=1704067200,
            end_time=1704067200,
            time_taken=0,
        )

        log_str = NodeStatsMapper.to_log_string(node_id="12345678-1234-1234-1234-123456789abc", node_stat=node_stats)

        assert "Completed execution: QuickNode, time= 0.00 seconds" in log_str

    def test_to_log_string_missing_time_taken(self):
        """Should handle missing time_taken field."""
        node_stats = NodeStats(
            node_id="12345678-1234-1234-1234-123456789abc",
            name="TestNode",
            node_status=ExecutionStatus.COMPLETED.value,
            start_time=1704067200,
            end_time=1704067200,
            time_taken=0,
        )

        log_str = NodeStatsMapper.to_log_string(node_id="12345678-1234-1234-1234-123456789abc", node_stat=node_stats)

        assert "Completed execution: TestNode, time= 0.00 seconds" in log_str

    def test_to_log_string_canceled_node(self):
        """Should format canceled node as completed (not in FAILED/SKIPPED)."""
        node_stats = NodeStats(
            node_id="12345678-1234-1234-1234-123456789abc",
            name="CanceledNode",
            node_status=ExecutionStatus.CANCELED.value,
            start_time=1704067200,
            end_time=1704067210,
            time_taken=10,
        )

        log_str = NodeStatsMapper.to_log_string(node_id="12345678-1234-1234-1234-123456789abc", node_stat=node_stats)

        assert "Starting execution: Step Name: CanceledNode" in log_str
        # CANCELED is terminal but not FAILED or SKIPPED, so shows as "Completed"
        assert "Completed execution: CanceledNode, time= 10.00 seconds" in log_str

    def test_to_log_string_with_enum_status(self):
        """Should handle ExecutionStatus enum values."""
        node_stats = NodeStats(
            node_id="12345678-1234-1234-1234-123456789abc",
            name="EnumNode",
            node_status=ExecutionStatus.COMPLETED,  # Enum instead of string
            start_time=1704067200,
            end_time=1704067260,
            time_taken=60,
        )

        log_str = NodeStatsMapper.to_log_string(node_id="12345678-1234-1234-1234-123456789abc", node_stat=node_stats)

        assert "Completed execution: EnumNode, time= 60.00 seconds" in log_str
