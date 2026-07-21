"""Tests for StorageOutputOperator — processed_content mode."""

from unittest.mock import patch

import pyarrow as pa
import pytest

from docpipe.core.operators.storage.storage_output_operator import StorageOutputOperator


def _make_table(rows: list[dict]) -> pa.Table:
    return pa.Table.from_pylist(rows)


def _base_config(tmp_path, overrides: dict | None = None) -> dict:
    config = {
        "name": "storage_output",
        "id": "node_1",
        "mode": "processed_content",
        "destination_config": {
            "provider": "filesystem",
            "connection_params": {
                "root_path": str(tmp_path),
                "create_dirs": True,
                "overwrite_existing": True,
            },
            "credentials": {},
        },
        "output_format": {
            "content_format": "md",
        },
        "output_structure": {
            "path_template": "{doc_id}.{ext}",
        },
    }
    if overrides:
        config.update(overrides)
    return config


class TestStorageOutputOperatorValidation:
    def test_missing_mode_raises_on_transform(self, tmp_path):
        config = _base_config(tmp_path)
        config.pop("mode")
        op = StorageOutputOperator(config)
        with pytest.raises(ValueError, match="mode"):
            op.transform(
                _make_table(
                    [{"id": "1", "name": "a", "content": "x", "path": "/p", "metadata": "{}", "document_format": "pdf"}]
                )
            )

    def test_missing_destination_config_raises_on_transform(self, tmp_path):
        config = _base_config(tmp_path)
        config.pop("destination_config")
        op = StorageOutputOperator(config)
        with pytest.raises(ValueError, match="destination_config"):
            op.transform(
                _make_table(
                    [{"id": "1", "name": "a", "content": "x", "path": "/p", "metadata": "{}", "document_format": "pdf"}]
                )
            )

    def test_validate_method_reports_missing_content_column(self, tmp_path):
        op = StorageOutputOperator(_base_config(tmp_path))
        errors: list[str] = []
        warnings: list[str] = []
        op.validate(errors, warnings, available_features=["id", "name", "path", "metadata", "document_format"])
        assert any("content" in e for e in errors)


class TestStorageOutputOperatorProcessedContent:
    def test_writes_md_files_to_disk(self, tmp_path):
        op = StorageOutputOperator(_base_config(tmp_path))
        table = _make_table(
            [
                {
                    "id": "doc1",
                    "name": "file1.pdf",
                    "content": "# Hello",
                    "path": "/src/file1.pdf",
                    "metadata": "{}",
                    "document_format": "pdf",
                },
                {
                    "id": "doc2",
                    "name": "file2.pdf",
                    "content": "# World",
                    "path": "/src/file2.pdf",
                    "metadata": "{}",
                    "document_format": "pdf",
                },
            ]
        )

        _output_tables, _metadata = op.transform(table)

        assert (tmp_path / "doc1.content.md").exists()
        assert (tmp_path / "doc2.content.md").exists()
        assert (tmp_path / "doc1.content.md").read_text() == "# Hello"

    def test_output_table_has_write_result_columns(self, tmp_path):
        op = StorageOutputOperator(_base_config(tmp_path))
        table = _make_table(
            [
                {
                    "id": "doc1",
                    "name": "file1.pdf",
                    "content": "Hello",
                    "path": "/src/file1.pdf",
                    "metadata": "{}",
                    "document_format": "pdf",
                },
            ]
        )

        output_tables, _ = op.transform(table)
        out = output_tables[0]

        assert "write_status" in out.schema.names
        assert "destination_path" in out.schema.names
        assert "bytes_written" in out.schema.names
        assert "write_error" in out.schema.names

    def test_output_table_passes_through_input_columns(self, tmp_path):
        op = StorageOutputOperator(_base_config(tmp_path))
        table = _make_table(
            [
                {
                    "id": "doc1",
                    "name": "file1.pdf",
                    "content": "Hello",
                    "path": "/src/file1.pdf",
                    "metadata": "{}",
                    "document_format": "pdf",
                },
            ]
        )

        output_tables, _ = op.transform(table)
        out = output_tables[0]

        for col in ["id", "name", "content", "path", "metadata", "document_format"]:
            assert col in out.schema.names

    def test_metadata_counts_are_correct(self, tmp_path):
        op = StorageOutputOperator(_base_config(tmp_path))
        table = _make_table(
            [
                {
                    "id": "doc1",
                    "name": "f1.pdf",
                    "content": "A",
                    "path": "/p1",
                    "metadata": "{}",
                    "document_format": "pdf",
                },
                {
                    "id": "doc2",
                    "name": "f2.pdf",
                    "content": "B",
                    "path": "/p2",
                    "metadata": "{}",
                    "document_format": "pdf",
                },
            ]
        )

        _, metadata = op.transform(table)

        assert metadata["total_docs_count"] == 2
        assert metadata["processed_docs"] == 2
        assert metadata["failed_docs_count"] == 0

    def test_write_failure_recorded_in_output_and_metadata(self, tmp_path):
        op = StorageOutputOperator(_base_config(tmp_path))
        table = _make_table(
            [
                {
                    "id": "doc1",
                    "name": "f1.pdf",
                    "content": "A",
                    "path": "/p",
                    "metadata": "{}",
                    "document_format": "pdf",
                },
            ]
        )

        with patch(
            "docpipe.core.operators.storage.adapters.outbound.destinations.filesystem.adapter.FilesystemDestinationAdapter.write_document",
            side_effect=PermissionError("denied"),
        ):
            output_tables, metadata = op.transform(table)

        out = output_tables[0]
        assert out["write_status"][0].as_py() == "failed"
        assert metadata["failed_docs_count"] == 1
        assert metadata["processed_docs"] == 0

    def test_writes_txt_format(self, tmp_path):
        config = _base_config(tmp_path, {"output_format": {"content_format": "txt"}})
        op = StorageOutputOperator(config)
        table = _make_table(
            [
                {
                    "id": "doc1",
                    "name": "f.pdf",
                    "content": "plain text",
                    "path": "/p",
                    "metadata": "{}",
                    "document_format": "pdf",
                },
            ]
        )

        op.transform(table)

        assert (tmp_path / "doc1.content.txt").exists()

    def test_writes_json_format(self, tmp_path):
        config = _base_config(tmp_path, {"output_format": {"content_format": "json"}})
        op = StorageOutputOperator(config)
        table = _make_table(
            [
                {
                    "id": "doc1",
                    "name": "f.pdf",
                    "content": "some content",
                    "path": "/p",
                    "metadata": '{"key": "val"}',
                    "document_format": "pdf",
                },
            ]
        )

        op.transform(table)

        import json

        written = json.loads((tmp_path / "doc1.content.json").read_text())
        assert written["content"] == "some content"

    def test_empty_table_returns_empty_output(self, tmp_path):
        op = StorageOutputOperator(_base_config(tmp_path))
        schema = pa.schema(
            [
                ("id", pa.string()),
                ("name", pa.string()),
                ("content", pa.string()),
                ("path", pa.string()),
                ("metadata", pa.string()),
                ("document_format", pa.string()),
            ]
        )
        table = pa.table({col: [] for col in schema.names}, schema=schema)

        output_tables, metadata = op.transform(table)

        assert output_tables[0].num_rows == 0
        assert metadata["total_docs_count"] == 0


# ---------------------------------------------------------------------------
# Tests for refetch_original mode
# ---------------------------------------------------------------------------


def _refetch_config(tmp_path, overrides: dict | None = None) -> dict:
    config = {
        "name": "storage_output",
        "id": "node_1",
        "mode": "refetch_original",
        "ingest_source": {
            "provider": "filesystem",
            "connection_params": {"root_path": "/src"},
            "credentials": {},
        },
        "destination_config": {
            "provider": "filesystem",
            "connection_params": {
                "root_path": str(tmp_path),
                "create_dirs": True,
                "overwrite_existing": True,
            },
            "credentials": {},
        },
        "output_structure": {
            "path_template": "{doc_id}.{ext}",
        },
    }
    if overrides:
        config.update(overrides)
    return config


def _comprehensive_config(tmp_path, overrides: dict | None = None) -> dict:
    config = {
        "name": "storage_output",
        "id": "node_1",
        "mode": "comprehensive_export",
        "ingest_source": {
            "provider": "filesystem",
            "connection_params": {"root_path": "/src"},
            "credentials": {},
        },
        "destination_config": {
            "provider": "filesystem",
            "connection_params": {
                "root_path": str(tmp_path),
                "create_dirs": True,
                "overwrite_existing": True,
            },
            "credentials": {},
        },
        "output_format": {
            "content_format": "md",
            "include_metadata_sidecar": True,
        },
        "output_structure": {
            "path_template": "{doc_id}/{name}.{ext}",
        },
    }
    if overrides:
        config.update(overrides)
    return config


_FULL_ROW = {
    "id": "doc1",
    "name": "report.pdf",
    "content": "# Extracted",
    "path": "file:///src/report.pdf",
    "metadata": '{"author": "Alice"}',
    "document_format": "pdf",
}


class TestStorageOutputOperatorRefetchOriginal:
    def test_writes_binary_to_disk(self, tmp_path):
        op = StorageOutputOperator(_refetch_config(tmp_path))
        table = _make_table([_FULL_ROW])

        with patch("docpipe.core.operators.storage.storage_output_operator.get_binary_content") as mock_fetch:
            mock_fetch.return_value = b"%PDF binary"
            _output_tables, _metadata = op.transform(table)

        assert (tmp_path / "doc1.pdf").exists()
        assert (tmp_path / "doc1.pdf").read_bytes() == b"%PDF binary"

    def test_fetch_binary_content_called_with_path(self, tmp_path):
        op = StorageOutputOperator(_refetch_config(tmp_path))
        table = _make_table([_FULL_ROW])

        with patch("docpipe.core.operators.storage.storage_output_operator.get_binary_content") as mock_fetch:
            mock_fetch.return_value = b"data"
            op.transform(table)

        mock_fetch.assert_called_once_with(
            doc_metadata={"path": "file:///src/report.pdf", "name": "report.pdf"},
            global_config={
                "ingest_source": {
                    "provider": "filesystem",
                    "connection_params": {"root_path": "/src"},
                    "credentials": {},
                }
            },
        )

    def test_requires_ingest_source(self, tmp_path):
        config = _refetch_config(tmp_path)
        config.pop("ingest_source")
        op = StorageOutputOperator(config)
        with pytest.raises(ValueError, match="ingest_source"):
            op.transform(_make_table([_FULL_ROW]))

    def test_validate_reports_missing_ingest_source(self, tmp_path):
        config = _refetch_config(tmp_path)
        config.pop("ingest_source")
        op = StorageOutputOperator(config)
        errors: list[str] = []
        warnings: list[str] = []
        op.validate(
            errors,
            warnings,
            available_features=["id", "name", "path", "content", "metadata", "document_format"],
        )
        assert any("ingest_source" in e for e in errors)

    def test_ingest_source_in_config_is_sufficient(self, tmp_path):
        op = StorageOutputOperator(_refetch_config(tmp_path))
        errors: list[str] = []
        warnings: list[str] = []
        op.validate(
            errors,
            warnings,
            available_features=["id", "name", "path", "content", "metadata", "document_format"],
        )
        assert not any("ingest_source" in e for e in errors)

    def test_failed_fetch_recorded_as_failure(self, tmp_path):
        op = StorageOutputOperator(_refetch_config(tmp_path))
        table = _make_table([_FULL_ROW])

        with patch("docpipe.core.operators.storage.storage_output_operator.get_binary_content") as mock_fetch:
            mock_fetch.return_value = None  # source not found
            output_tables, metadata = op.transform(table)

        out = output_tables[0]
        assert out["write_status"][0].as_py() == "failed"
        assert metadata["failed_docs_count"] == 1

    def test_output_table_has_write_result_columns(self, tmp_path):
        op = StorageOutputOperator(_refetch_config(tmp_path))
        table = _make_table([_FULL_ROW])

        with patch("docpipe.core.operators.storage.storage_output_operator.get_binary_content") as mock_fetch:
            mock_fetch.return_value = b"data"
            output_tables, _ = op.transform(table)

        out = output_tables[0]
        for col in ["write_status", "destination_path", "bytes_written", "write_error"]:
            assert col in out.schema.names

    def test_metadata_counts_correct(self, tmp_path):
        op = StorageOutputOperator(_refetch_config(tmp_path))
        table = _make_table([_FULL_ROW])

        with patch("docpipe.core.operators.storage.storage_output_operator.get_binary_content") as mock_fetch:
            mock_fetch.return_value = b"data"
            _, metadata = op.transform(table)

        assert metadata["processed_docs"] == 1
        assert metadata["failed_docs_count"] == 0


class TestStorageOutputOperatorComprehensiveExport:
    def test_writes_three_files_per_document(self, tmp_path):
        op = StorageOutputOperator(_comprehensive_config(tmp_path))
        table = _make_table([_FULL_ROW])

        with patch("docpipe.core.operators.storage.storage_output_operator.get_binary_content") as mock_fetch:
            mock_fetch.return_value = b"%PDF"
            op.transform(table)

        # original binary
        assert (tmp_path / "doc1" / "report.pdf").exists()
        # extracted content
        assert (tmp_path / "doc1" / "report.content.md").exists()
        # metadata sidecar
        assert (tmp_path / "doc1" / "report.meta.json").exists()

    def test_sidecar_not_written_when_disabled(self, tmp_path):
        config = _comprehensive_config(
            tmp_path,
            {"output_format": {"content_format": "md", "include_metadata_sidecar": False}},
        )
        op = StorageOutputOperator(config)
        table = _make_table([_FULL_ROW])

        with patch("docpipe.core.operators.storage.storage_output_operator.get_binary_content") as mock_fetch:
            mock_fetch.return_value = b"%PDF"
            op.transform(table)

        assert not (tmp_path / "doc1" / "report.meta.json").exists()
        assert (tmp_path / "doc1" / "report.pdf").exists()
        assert (tmp_path / "doc1" / "report.content.md").exists()

    def test_sidecar_contains_metadata(self, tmp_path):
        op = StorageOutputOperator(_comprehensive_config(tmp_path))
        table = _make_table([_FULL_ROW])

        with patch("docpipe.core.operators.storage.storage_output_operator.get_binary_content") as mock_fetch:
            mock_fetch.return_value = b"%PDF"
            op.transform(table)

        import json as _json

        sidecar = _json.loads((tmp_path / "doc1" / "report.meta.json").read_text())
        assert sidecar["id"] == "doc1"
        assert sidecar["name"] == "report.pdf"
        assert "author" in sidecar["metadata"]

    def test_original_binary_content_is_verbatim(self, tmp_path):
        op = StorageOutputOperator(_comprehensive_config(tmp_path))
        table = _make_table([_FULL_ROW])
        original_bytes = b"%PDF-1.4 binary content"

        with patch("docpipe.core.operators.storage.storage_output_operator.get_binary_content") as mock_fetch:
            mock_fetch.return_value = original_bytes
            op.transform(table)

        assert (tmp_path / "doc1" / "report.pdf").read_bytes() == original_bytes

    def test_requires_ingest_source(self, tmp_path):
        config = _comprehensive_config(tmp_path)
        config.pop("ingest_source")
        op = StorageOutputOperator(config)
        with pytest.raises(ValueError, match="ingest_source"):
            op.transform(_make_table([_FULL_ROW]))

    def test_metadata_counts_correct(self, tmp_path):
        op = StorageOutputOperator(_comprehensive_config(tmp_path))
        table = _make_table([_FULL_ROW])

        with patch("docpipe.core.operators.storage.storage_output_operator.get_binary_content") as mock_fetch:
            mock_fetch.return_value = b"data"
            _, metadata = op.transform(table)

        assert metadata["processed_docs"] == 1
        assert metadata["failed_docs_count"] == 0

    def test_failed_fetch_recorded_as_failure(self, tmp_path):
        op = StorageOutputOperator(_comprehensive_config(tmp_path))
        table = _make_table([_FULL_ROW])

        with patch("docpipe.core.operators.storage.storage_output_operator.get_binary_content") as mock_fetch:
            mock_fetch.return_value = None
            output_tables, metadata = op.transform(table)

        out = output_tables[0]
        assert out["write_status"][0].as_py() == "failed"
        assert metadata["failed_docs_count"] == 1
