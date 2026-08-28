"""
Unit tests for JobReportGenerator

Tests cover:
- Report data generation
- CSV content generation
- Node identification (ingest, destination, extract)
- Batch number extraction
- Document status determination
- Processing time calculation
- Page count extraction
- Failure/skip reason extraction
"""

import csv
import io
from unittest.mock import patch

import pytest

from docpipe.core.constants.constants import ExecutionStatus
from docpipe.core.job_management.application.services.report_generator import (
    GENERIC_FAILURE_MESSAGE,
    JobReportGenerator,
    _build_node_metadata_list,
)
from docpipe.core.job_management.domain.models import JobStats, NodeStats

# Test constants
JOB_ID = "test-job-123"
JOB_RUN_ID = "test-run-456"
INGEST_NODE_ID = "ingest-node-1"
EXTRACT_NODE_ID = "extract-node-2"
DEST_NODE_ID = "dest-node-3"


class TestJobReportGeneratorInitialization:
    """Test report generator initialization."""

    def test_init_with_minimal_params(self):
        """Initialize with only required parameters."""
        job_stats = JobStats(
            job_id=JOB_ID,
            job_run_id=JOB_RUN_ID,
            status=ExecutionStatus.COMPLETED,
            node_stats={},
        )

        generator = JobReportGenerator(job_stats=job_stats)

        assert generator.job_stats == job_stats
        assert generator.dag_nodes == []
        assert generator.node_metadata_list == []
        assert generator.node_id_to_name == {}

    def test_init_with_dag_nodes(self):
        """Initialize with DAG nodes builds node name map."""
        job_stats = JobStats(
            job_id=JOB_ID,
            job_run_id=JOB_RUN_ID,
            status=ExecutionStatus.COMPLETED,
            node_stats={},
        )

        dag_nodes = [
            {"id": INGEST_NODE_ID, "name": "IngestLocal"},
            {"id": EXTRACT_NODE_ID, "name": "Extract"},
        ]

        generator = JobReportGenerator(job_stats=job_stats, dag_nodes=dag_nodes)

        assert len(generator.node_id_to_name) == 2
        assert generator.node_id_to_name[INGEST_NODE_ID] == "IngestLocal"
        assert generator.node_id_to_name[EXTRACT_NODE_ID] == "Extract"


class TestNodeIdentification:
    """Test node identification methods."""

    def test_get_ingest_node_id_no_input_edges(self):
        """Ingest node is identified by having no input edges."""
        job_stats = JobStats(
            job_id=JOB_ID,
            job_run_id=JOB_RUN_ID,
            status=ExecutionStatus.COMPLETED,
            node_stats={},
        )

        dag_nodes = [
            {"id": INGEST_NODE_ID, "name": "Ingest", "input_edges": []},
            {"id": EXTRACT_NODE_ID, "name": "Extract", "input_edges": [INGEST_NODE_ID]},
        ]

        generator = JobReportGenerator(job_stats=job_stats, dag_nodes=dag_nodes)
        ingest_id = generator._get_ingest_node_id()

        assert ingest_id == INGEST_NODE_ID

    def test_get_destination_node_ids_no_output_edges(self):
        """Destination nodes are identified by having no output edges."""
        job_stats = JobStats(
            job_id=JOB_ID,
            job_run_id=JOB_RUN_ID,
            status=ExecutionStatus.COMPLETED,
            node_stats={},
        )

        dag_nodes = [
            {"id": INGEST_NODE_ID, "name": "Ingest", "output_edges": [EXTRACT_NODE_ID]},
            {"id": EXTRACT_NODE_ID, "name": "Extract", "output_edges": [DEST_NODE_ID]},
            {"id": DEST_NODE_ID, "name": "VectorDB", "output_edges": []},
        ]

        generator = JobReportGenerator(job_stats=job_stats, dag_nodes=dag_nodes)
        dest_ids = generator._get_destination_node_ids()

        assert dest_ids == [DEST_NODE_ID]

    def test_find_extract_operator_by_op_field(self):
        """Extract operator is found by checking 'op' field."""
        job_stats = JobStats(
            job_id=JOB_ID,
            job_run_id=JOB_RUN_ID,
            status=ExecutionStatus.COMPLETED,
            node_stats={},
        )

        dag_nodes = [
            {"id": INGEST_NODE_ID, "op": "ingest_source"},
            {"id": EXTRACT_NODE_ID, "op": "extract", "name": "ExtractOp"},
        ]

        generator = JobReportGenerator(job_stats=job_stats, dag_nodes=dag_nodes)
        extract_id, extract_name = generator._find_extract_operator()

        assert extract_id == EXTRACT_NODE_ID
        assert extract_name == "ExtractOp"

    def test_find_extract_operator_by_operator_field(self):
        """Extract operator is found by checking 'operator' field."""
        job_stats = JobStats(
            job_id=JOB_ID,
            job_run_id=JOB_RUN_ID,
            status=ExecutionStatus.COMPLETED,
            node_stats={},
        )

        dag_nodes = [
            {"id": EXTRACT_NODE_ID, "operator": "extract_cpd", "name": "Extract"},
        ]

        generator = JobReportGenerator(job_stats=job_stats, dag_nodes=dag_nodes)
        extract_id, extract_name = generator._find_extract_operator()

        assert extract_id == EXTRACT_NODE_ID
        assert extract_name == "Extract"


class TestBatchNumberExtraction:
    """Test batch number extraction from batch_node_stats."""

    def test_get_batch_nums_from_stats(self):
        """Extract batch numbers from batch_node_stats."""
        batch_stats_1 = NodeStats(
            id=EXTRACT_NODE_ID,
            name="Extract",
            batch_id="batch-1",
            batch_num=0,
        )
        batch_stats_2 = NodeStats(
            id=EXTRACT_NODE_ID,
            name="Extract",
            batch_id="batch-2",
            batch_num=1,
        )

        job_stats = JobStats(
            job_id=JOB_ID,
            job_run_id=JOB_RUN_ID,
            status=ExecutionStatus.COMPLETED,
            node_stats={},
            batch_node_stats={
                EXTRACT_NODE_ID: {
                    "batch-1": batch_stats_1,
                    "batch-2": batch_stats_2,
                }
            },
        )

        generator = JobReportGenerator(job_stats=job_stats)
        batch_nums = generator._get_actual_batch_nums(EXTRACT_NODE_ID)

        assert batch_nums == {0, 1}

    def test_get_actual_batch_nums_with_batch_stats(self):
        """Get actual batch numbers when batch_node_stats exists."""
        batch_stats = NodeStats(
            id=EXTRACT_NODE_ID,
            name="Extract",
            batch_id="batch-1",
            batch_num=0,
        )

        job_stats = JobStats(
            job_id=JOB_ID,
            job_run_id=JOB_RUN_ID,
            status=ExecutionStatus.COMPLETED,
            node_stats={},
            batch_node_stats={EXTRACT_NODE_ID: {"batch-1": batch_stats}},
        )

        generator = JobReportGenerator(job_stats=job_stats)
        batch_nums = generator._get_actual_batch_nums(EXTRACT_NODE_ID)

        assert batch_nums == {0}

    def test_get_actual_batch_nums_without_batch_stats(self):
        """Return {None} when no batch_node_stats (non-batched flow)."""
        job_stats = JobStats(
            job_id=JOB_ID,
            job_run_id=JOB_RUN_ID,
            status=ExecutionStatus.COMPLETED,
            node_stats={},
        )

        generator = JobReportGenerator(job_stats=job_stats)
        batch_nums = generator._get_actual_batch_nums(EXTRACT_NODE_ID)

        assert batch_nums == {None}


class TestDocumentStatusDetermination:
    """Test document status determination logic."""

    def test_build_status_lookup_sets(self):
        """Build lookup sets for failed, skipped, and destination completed docs."""
        node_stats_1 = NodeStats(
            id=INGEST_NODE_ID,
            name="Ingest",
            failed_docs=["doc1"],
            skipped_docs=["doc2"],
        )
        node_stats_2 = NodeStats(
            id=DEST_NODE_ID,
            name="VectorDB",
            node_status=ExecutionStatus.COMPLETED,
            docs_completed=["doc3", "doc4"],
        )

        job_stats = JobStats(
            job_id=JOB_ID,
            job_run_id=JOB_RUN_ID,
            status=ExecutionStatus.COMPLETED,
            node_stats={
                INGEST_NODE_ID: node_stats_1,
                DEST_NODE_ID: node_stats_2,
            },
        )

        dag_nodes = [
            {"id": INGEST_NODE_ID, "output_edges": [DEST_NODE_ID]},
            {"id": DEST_NODE_ID, "output_edges": []},
        ]

        generator = JobReportGenerator(job_stats=job_stats, dag_nodes=dag_nodes)
        failed, skipped, dest_completed = generator._build_status_lookup_sets()

        assert failed == {"doc1"}
        assert skipped == {"doc2"}
        assert dest_completed == {"doc3", "doc4"}


class TestCSVGeneration:
    """Test CSV content generation."""

    def test_generate_csv_content_empty_report(self):
        """Generate CSV with headers only when no documents."""
        job_stats = JobStats(
            job_id=JOB_ID,
            job_run_id=JOB_RUN_ID,
            status=ExecutionStatus.COMPLETED,
            node_stats={},
        )

        generator = JobReportGenerator(job_stats=job_stats)

        with patch.object(generator, "generate_report_data", return_value=[]):
            csv_content = generator.generate_csv_content()

        # Should have headers
        assert "GUID" in csv_content
        assert "File name" in csv_content
        assert "Status" in csv_content

    def test_generate_csv_content_with_data(self):
        """Generate CSV with document data."""
        job_stats = JobStats(
            job_id=JOB_ID,
            job_run_id=JOB_RUN_ID,
            status=ExecutionStatus.COMPLETED,
            node_stats={},
        )

        generator = JobReportGenerator(job_stats=job_stats)

        mock_data = [
            {
                "GUID": "doc1",
                "File name": "test.pdf",
                "Status": "Ingested",
                "Status reason": "",
                "Time stamp": "2024-01-01T00:00:00Z",
                "Pages": "10",
                "Processing time (in seconds)": "45",
            }
        ]

        with patch.object(generator, "generate_report_data", return_value=mock_data):
            csv_content = generator.generate_csv_content()

        # Parse CSV to verify content
        csv_reader = csv.DictReader(io.StringIO(csv_content))
        rows = list(csv_reader)

        assert len(rows) == 1
        assert rows[0]["GUID"] == "doc1"
        assert rows[0]["File name"] == "test.pdf"
        assert rows[0]["Status"] == "Ingested"
        assert rows[0]["Pages"] == "10"

    def test_save_report_to_file(self, tmp_path):
        """Save report delegates to the storage adapter."""
        from unittest.mock import Mock

        job_stats = JobStats(
            job_id=JOB_ID,
            job_run_id=JOB_RUN_ID,
            status=ExecutionStatus.COMPLETED,
            node_stats={},
        )

        generator = JobReportGenerator(job_stats=job_stats)

        from docpipe.core.models.session_info import create_session_info

        create_session_info(job_id=JOB_ID, job_run_id=JOB_RUN_ID)

        mock_csv = "GUID,File name,Status\ndoc1,test.pdf,Ingested\n"
        mock_adapter = Mock()
        mock_adapter.write_text.return_value = str(tmp_path / "job_report.csv")

        with (
            patch.object(generator, "generate_csv_content", return_value=mock_csv),
            patch(
                "docpipe.core.job_management.adapters.config.report_storage_factory.get_report_storage",
                return_value=mock_adapter,
            ),
        ):
            saved_path = generator.save_report_to_file()

        mock_adapter.write_text.assert_called_once_with(
            collection=f"{JOB_ID}/{JOB_RUN_ID}",
            file_name=f"job_report_{JOB_RUN_ID}.csv",
            content=mock_csv,
        )
        assert saved_path == str(tmp_path / "job_report.csv")


class TestTimestampConversion:
    """Test timestamp conversion methods."""

    def test_get_timestamp_from_modified_time_integer(self):
        """Convert integer timestamp to YYYY-MM-DD:HH:MM:SS format."""
        job_stats = JobStats(
            job_id=JOB_ID,
            job_run_id=JOB_RUN_ID,
            status=ExecutionStatus.COMPLETED,
            node_stats={},
        )

        generator = JobReportGenerator(job_stats=job_stats)

        # Unix timestamp for 2024-01-01 00:00:00 UTC
        timestamp = 1704067200
        result = generator._get_timestamp_from_modified_time(timestamp, "doc1")

        # Should match the CSV format: YYYY-MM-DD:HH:MM:SS
        assert result == "2024-01-01:00:00:00"

    def test_get_timestamp_from_modified_time_epoch_ms(self):
        """Convert epoch-millisecond timestamp to YYYY-MM-DD:HH:MM:SS format."""
        job_stats = JobStats(
            job_id=JOB_ID,
            job_run_id=JOB_RUN_ID,
            status=ExecutionStatus.COMPLETED,
            node_stats={},
        )

        generator = JobReportGenerator(job_stats=job_stats)

        # Epoch-ms timestamp (≥ 1e10): 1704067200000
        # Should divide by 1000 to get seconds: 1704067200 = 2024-01-01 00:00:00 UTC
        timestamp_ms = 1704067200000
        result = generator._get_timestamp_from_modified_time(timestamp_ms, "doc1")

        # Should match the CSV format: YYYY-MM-DD:HH:MM:SS
        assert result == "2024-01-01:00:00:00"

    def test_get_timestamp_from_modified_time_string(self):
        """Return string timestamp as-is."""
        job_stats = JobStats(
            job_id=JOB_ID,
            job_run_id=JOB_RUN_ID,
            status=ExecutionStatus.COMPLETED,
            node_stats={},
        )

        generator = JobReportGenerator(job_stats=job_stats)

        timestamp_str = "2024-01-01T00:00:00Z"
        result = generator._get_timestamp_from_modified_time(timestamp_str, "doc1")

        assert result == timestamp_str

    def test_get_timestamp_from_modified_time_none(self):
        """Return empty string for None timestamp."""
        job_stats = JobStats(
            job_id=JOB_ID,
            job_run_id=JOB_RUN_ID,
            status=ExecutionStatus.COMPLETED,
            node_stats={},
        )

        generator = JobReportGenerator(job_stats=job_stats)

        result = generator._get_timestamp_from_modified_time(None, "doc1")

        assert result == ""


class TestBatchAttributeAccess:
    """Test _get_batch_attr helper for dict/object compatibility."""

    def test_get_batch_attr_from_dict(self):
        """Get attribute from dictionary batch_stats."""
        job_stats = JobStats(
            job_id=JOB_ID,
            job_run_id=JOB_RUN_ID,
            status=ExecutionStatus.COMPLETED,
            node_stats={},
        )

        generator = JobReportGenerator(job_stats=job_stats)

        batch_stats_dict = {"batch_num": 0, "name": "Extract"}
        result = generator._get_batch_attr(batch_stats_dict, "batch_num")

        assert result == 0

    def test_get_batch_attr_from_object(self):
        """Get attribute from NodeStats object."""
        job_stats = JobStats(
            job_id=JOB_ID,
            job_run_id=JOB_RUN_ID,
            status=ExecutionStatus.COMPLETED,
            node_stats={},
        )

        generator = JobReportGenerator(job_stats=job_stats)

        batch_stats_obj = NodeStats(
            id=EXTRACT_NODE_ID,
            name="Extract",
            batch_num=1,
        )
        result = generator._get_batch_attr(batch_stats_obj, "batch_num")

        assert result == 1

    def test_get_batch_attr_with_default(self):
        """Return default value when attribute not found."""
        job_stats = JobStats(
            job_id=JOB_ID,
            job_run_id=JOB_RUN_ID,
            status=ExecutionStatus.COMPLETED,
            node_stats={},
        )

        generator = JobReportGenerator(job_stats=job_stats)

        batch_stats_dict = {"name": "Extract"}
        result = generator._get_batch_attr(batch_stats_dict, "missing_attr", default="default_value")

        assert result == "default_value"


class TestReasonExtraction:
    """Test failure/skip reason extraction."""

    def test_extract_reason_from_docs_list(self):
        """Extract reason from document list with reason field."""
        job_stats = JobStats(
            job_id=JOB_ID,
            job_run_id=JOB_RUN_ID,
            status=ExecutionStatus.COMPLETED,
            node_stats={},
        )

        generator = JobReportGenerator(job_stats=job_stats)

        docs_list = [
            {"id": "doc1", "reason": "File not found"},
            {"id": "doc2", "reason": "Invalid format"},
        ]

        reason = generator._extract_reason_from_docs_list(docs_list, "doc1")

        assert reason == "File not found"

    def test_extract_reason_from_docs_list_not_found(self):
        """Return None when document not in list."""
        job_stats = JobStats(
            job_id=JOB_ID,
            job_run_id=JOB_RUN_ID,
            status=ExecutionStatus.COMPLETED,
            node_stats={},
        )

        generator = JobReportGenerator(job_stats=job_stats)

        docs_list = [{"id": "doc1", "reason": "Error"}]

        reason = generator._extract_reason_from_docs_list(docs_list, "doc2")

        assert reason is None


class TestBuildNodeMetadataList:
    """Test _build_node_metadata_list used by the on-demand report path."""

    def test_builds_list_from_node_stats_objects(self):
        """NodeStats objects: node_metadata dict is appended directly."""
        node_metadata_item = {
            "id": "uuid-1",
            "operator": "store_in_opensearch",
            "node_metadata": {
                "failed_docs": [{"id": "doc-a", "reason": "Connection timeout"}],
                "skipped_docs": [],
            },
        }
        node_stats = {
            "uuid-1": NodeStats(
                id="uuid-1",
                name="store_in_opensearch",
                node_metadata=node_metadata_item,
            )
        }

        result = _build_node_metadata_list(node_stats=node_stats)

        assert len(result) == 1
        # Entry IS the NodeMetadataItem dict; failed_docs reachable via ["node_metadata"]
        assert result[0]["node_metadata"]["failed_docs"][0]["reason"] == "Connection timeout"

    def test_builds_list_from_dict_node_stats(self):
        """Dict-style node_stats are also handled."""
        node_metadata_item = {
            "id": "uuid-1",
            "operator": "store_in_opensearch",
            "node_metadata": {
                "failed_docs": [{"id": "doc-b", "reason": "Index not found"}],
                "skipped_docs": [],
            },
        }
        node_stats = {
            "uuid-1": {
                "name": "store_in_opensearch",
                "node_metadata": node_metadata_item,
            }
        }

        result = _build_node_metadata_list(node_stats=node_stats)

        assert len(result) == 1
        assert result[0]["node_metadata"]["failed_docs"][0]["reason"] == "Index not found"

    def test_on_demand_path_retrieves_failure_reason_not_generic(self):
        """On-demand report generator retrieves the real reason, not the generic fallback."""
        failure_reason = "Failed to create index: ConnectionTimeout"

        node_metadata_item = {
            "id": "uuid-os",
            "operator": "store_in_opensearch",
            "node_metadata": {
                "failed_docs": [{"id": "doc-1", "reason": failure_reason}],
                "skipped_docs": [],
            },
        }
        node_stats = {
            "uuid-os": NodeStats(
                id="uuid-os",
                name="store_in_opensearch",
                node_metadata=node_metadata_item,
            )
        }

        node_metadata_list = _build_node_metadata_list(node_stats=node_stats)
        generator = JobReportGenerator(
            job_stats=JobStats(job_id=JOB_ID, job_run_id=JOB_RUN_ID, status=ExecutionStatus.FAILED),
            node_metadata_list=node_metadata_list,
        )

        reason = generator._find_failure_reason("doc-1")

        assert reason == failure_reason
        assert reason != GENERIC_FAILURE_MESSAGE


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
