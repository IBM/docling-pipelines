"""Unit tests for empty document handling in AbstractOperatorExecutor."""

from unittest.mock import Mock, patch

import pyarrow as pa
import pytest

from docpipe.core.constants.constants import ExecutionStatus, Metrics
from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.orchestration.python.python_operator_executor import PythonOperatorExecutor


class TestEmptyDocumentHandling:
    """Test empty document handling functionality in AbstractOperatorExecutor."""

    @pytest.fixture
    def mock_operator(self):
        """Create a mock operator."""
        operator = Mock()
        operator.name = "test_operator"
        operator.doc_column = OperatorConstants.Columns.DOC_COLUMN_DEFAULT
        operator.record_skipped_document = Mock()
        return operator

    @pytest.fixture
    def executor(self, mock_operator):
        """Create a PythonOperatorExecutor instance for testing."""
        executor = PythonOperatorExecutor(
            name="test_executor",
            operator="test_operator",
            params={
                OperatorConstants.Columns.ID: "node_1",
                OperatorConstants.Columns.NAME: "test_executor",
                "job_id": "test_job",
                "job_run_id": "test_run",
            },
        )
        # Mock get_operator to return our mock operator
        executor.get_operator = Mock(return_value=mock_operator)
        return executor

    def test_add_empty_docs_to_skipped_metadata(self, executor, mock_operator):
        """Test adding empty documents to skipped metadata."""
        table = pa.table(
            {
                "id": ["doc1", "doc2", "doc3"],
                "name": ["file1.pdf", "file2.pdf", "file3.pdf"],
                "content": ["valid", "", "also valid"],
            }
        )
        metadata: dict[str, object] = {}

        executor._add_empty_docs_to_skipped_metadata(table=table, empty_doc_indices=[1], metadata=metadata)

        mock_operator.record_skipped_document.assert_called_once_with(
            metadata=metadata, doc_id="doc2", doc_name="file2.pdf", reason="Extracted content is empty"
        )

    def test_add_empty_docs_updates_node_status(self, executor, mock_operator):
        """Test that adding empty docs updates node status to COMPLETED_WITH_WARNINGS."""
        table = pa.table(
            {
                "id": ["doc1", "doc2"],
                "name": ["file1.pdf", "file2.pdf"],
                "content": ["valid", ""],
            }
        )
        metadata = {Metrics.External.NODE_STATUS: ExecutionStatus.COMPLETED.value}

        with patch("docpipe.core.orchestration.abstract_operator_executor.OperatorUtils.merge_status") as mock_merge:
            mock_merge.return_value = ExecutionStatus.COMPLETED_WITH_WARNINGS.value

            executor._add_empty_docs_to_skipped_metadata(table=table, empty_doc_indices=[1], metadata=metadata)

            mock_merge.assert_called_once_with(
                ExecutionStatus.COMPLETED.value, ExecutionStatus.COMPLETED_WITH_WARNINGS.value
            )

    def test_process_table_for_empty_docs_no_doc_column(self, executor):
        """Test processing table when doc_column doesn't exist."""
        table = pa.table(
            {
                "id": ["doc1", "doc2"],
                "other_column": ["data1", "data2"],
            }
        )
        metadata: dict[str, object] = {}

        result = executor._process_table_for_empty_docs(table=table, doc_column="content", metadata=metadata)

        assert result == table

    def test_process_table_for_empty_docs_with_empty_docs(self, executor, mock_operator):
        """Test processing table with empty documents."""
        table = pa.table(
            {
                "id": ["doc1", "doc2", "doc3"],
                "name": ["file1.pdf", "file2.pdf", "file3.pdf"],
                "content": ["valid content", "", "more content"],
            }
        )
        metadata: dict[str, object] = {}

        with patch.object(executor, "_save_empty_docs_to_incremental_metadata"):
            result = executor._process_table_for_empty_docs(table=table, doc_column="content", metadata=metadata)

            assert result.num_rows == 2
            assert result["id"].to_pylist() == ["doc1", "doc3"]
            mock_operator.record_skipped_document.assert_called_once()

    def test_handle_empty_documents_single_table(self, executor, mock_operator):
        """Test _handle_empty_documents with a single table."""
        table = pa.table(
            {
                "id": ["doc1", "doc2", "doc3"],
                "content": ["valid", "", "also valid"],
            }
        )
        metadata: dict[str, object] = {}

        with patch.object(executor, "_save_empty_docs_to_incremental_metadata"):
            processed_tables, _updated_metadata = executor._handle_empty_documents(
                out_tables=[table], metadata=metadata
            )

            assert len(processed_tables) == 1
            assert processed_tables[0].num_rows == 2
            assert processed_tables[0]["id"].to_pylist() == ["doc1", "doc3"]

    def test_handle_empty_documents_multiple_tables(self, executor, mock_operator):
        """Test _handle_empty_documents with multiple tables."""
        table1 = pa.table(
            {
                "id": ["doc1", "doc2"],
                "content": ["valid", ""],
            }
        )
        table2 = pa.table(
            {
                "id": ["doc3", "doc4"],
                "content": ["", "valid"],
            }
        )
        metadata: dict[str, object] = {}

        with patch.object(executor, "_save_empty_docs_to_incremental_metadata"):
            processed_tables, _updated_metadata = executor._handle_empty_documents(
                out_tables=[table1, table2], metadata=metadata
            )

            assert len(processed_tables) == 2
            assert processed_tables[0].num_rows == 1
            assert processed_tables[0]["id"].to_pylist() == ["doc1"]
            assert processed_tables[1].num_rows == 1
            assert processed_tables[1]["id"].to_pylist() == ["doc4"]

    def test_handle_empty_documents_nested_lists(self, executor, mock_operator):
        """Test _handle_empty_documents with nested lists (branching operator)."""
        branch1_table = pa.table(
            {
                "id": ["doc1", "doc2"],
                "content": ["valid", ""],
            }
        )
        branch2_table = pa.table(
            {
                "id": ["doc3"],
                "content": ["valid"],
            }
        )
        metadata: dict[str, object] = {}

        with patch.object(executor, "_save_empty_docs_to_incremental_metadata"):
            processed_tables, _updated_metadata = executor._handle_empty_documents(
                out_tables=[[branch1_table, branch2_table]], metadata=metadata
            )

            assert len(processed_tables) == 1
            assert len(processed_tables[0]) == 2
            assert processed_tables[0][0].num_rows == 1
            assert processed_tables[0][0]["id"].to_pylist() == ["doc1"]
            assert processed_tables[0][1].num_rows == 1

    def test_handle_empty_documents_empty_list(self, executor):
        """Test _handle_empty_documents with empty table list."""
        metadata: dict[str, object] = {}

        processed_tables, updated_metadata = executor._handle_empty_documents(out_tables=[], metadata=metadata)

        assert processed_tables == []
        assert updated_metadata == metadata

    def test_handle_empty_documents_none_tables(self, executor):
        """Test _handle_empty_documents with None tables."""
        metadata: dict[str, object] = {}

        processed_tables, updated_metadata = executor._handle_empty_documents(out_tables=None, metadata=metadata)

        assert processed_tables is None
        assert updated_metadata == metadata

    @patch("docpipe.core.incremental_metadata.get_incremental_update_service")
    def test_save_empty_docs_to_incremental_metadata_success(self, mock_get_service, executor):
        """Test saving empty documents to incremental metadata successfully."""
        mock_service = Mock()
        mock_get_service.return_value = mock_service

        table = pa.table(
            {
                "id": ["doc1", "doc2", "doc3"],
                "content": ["valid", "", "also valid"],
            }
        )

        executor._save_empty_docs_to_incremental_metadata(table=table, empty_doc_indices=[1])

        mock_service.save_metadata_for_incremental_update.assert_called_once()
        call_args = mock_service.save_metadata_for_incremental_update.call_args
        assert call_args.kwargs["job_id"] == "test_job"
        assert call_args.kwargs["job_run_id"] == "test_run"
        assert len(call_args.kwargs["tables"]) == 1
        assert call_args.kwargs["tables"][0].num_rows == 1

    @patch("docpipe.core.incremental_metadata.get_incremental_update_service")
    def test_save_empty_docs_to_incremental_metadata_failure(self, mock_get_service, executor):
        """Test handling failure when saving to incremental metadata."""
        mock_service = Mock()
        mock_service.save_metadata_for_incremental_update.side_effect = Exception("Save failed")
        mock_get_service.return_value = mock_service

        table = pa.table(
            {
                "id": ["doc1", "doc2"],
                "content": ["valid", ""],
            }
        )

        # Should not raise exception, just log warning
        executor._save_empty_docs_to_incremental_metadata(table=table, empty_doc_indices=[1])

    def test_save_empty_docs_to_incremental_metadata_no_empty_docs(self, executor):
        """Test saving when there are no empty documents."""
        table = pa.table(
            {
                "id": ["doc1", "doc2"],
                "content": ["valid1", "valid2"],
            }
        )

        # Should return early without attempting to save
        with patch("docpipe.core.incremental_metadata.get_incremental_update_service") as mock_get_service:
            executor._save_empty_docs_to_incremental_metadata(table=table, empty_doc_indices=[])
            mock_get_service.assert_not_called()

    def test_custom_doc_column(self, mock_operator):
        """Test handling empty documents with custom doc_column."""
        mock_operator.doc_column = "custom_content"

        executor = PythonOperatorExecutor(
            name="test_executor",
            operator="test_operator",
            params={
                OperatorConstants.Columns.ID: "node_1",
                OperatorConstants.Columns.NAME: "test_executor",
                "job_id": "test_job",
                "job_run_id": "test_run",
            },
        )
        executor.get_operator = Mock(return_value=mock_operator)

        table = pa.table(
            {
                "id": ["doc1", "doc2"],
                "custom_content": ["valid", ""],
            }
        )
        metadata: dict[str, object] = {}

        with patch.object(executor, "_save_empty_docs_to_incremental_metadata"):
            processed_tables, _ = executor._handle_empty_documents(out_tables=[table], metadata=metadata)

            assert processed_tables[0].num_rows == 1
            assert processed_tables[0]["id"].to_pylist() == ["doc1"]
