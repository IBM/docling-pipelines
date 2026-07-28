"""
Integration tests for StorageOutputOperator.

These tests use real temporary directories and verify actual files land on disk
with correct content across all three operating modes.
"""

import json

import pyarrow as pa
import pytest

from docpipe.core.operators.storage.storage_output_operator import StorageOutputOperator

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_table(rows: list[dict]) -> pa.Table:
    return pa.Table.from_pylist(rows)


def _doc_row(
    *,
    doc_id: str = "abc123",
    name: str = "report.pdf",
    content: str = "# Report Content\n\nSome extracted text.",
    document_format: str = "pdf",
    path: str | None = None,
    metadata: dict | None = None,
) -> dict:
    return {
        "id": doc_id,
        "name": name,
        "content": content,
        "document_format": document_format,
        "path": path or f"file:///src/{name}",
        "metadata": json.dumps(metadata or {"author": "Alice", "year": 2026}),
    }


# ---------------------------------------------------------------------------
# Integration: processed_content
# ---------------------------------------------------------------------------


class TestProcessedContentIntegration:
    def test_writes_markdown_file(self, tmp_path):
        op = StorageOutputOperator(
            {
                "name": "storage_output",
                "id": "n1",
                "mode": "processed_content",
                "destination_config": {
                    "provider": "filesystem",
                    "provider_config": {"root_path": str(tmp_path)},
                    "credentials": {},
                },
                "output_format": {"content_format": "md"},
                "output_structure": {"path_template": "{doc_id}.{ext}"},
            }
        )
        row = _doc_row(doc_id="doc1", content="# Hello Integration")
        _tables, metadata = op.transform(_make_table([row]))

        out_file = tmp_path / "doc1.md"
        assert out_file.exists()
        assert out_file.read_text() == "# Hello Integration"
        assert metadata["processed_docs"] == 1

    def test_writes_txt_file(self, tmp_path):
        op = StorageOutputOperator(
            {
                "name": "storage_output",
                "id": "n1",
                "mode": "processed_content",
                "destination_config": {
                    "provider": "filesystem",
                    "provider_config": {"root_path": str(tmp_path)},
                    "credentials": {},
                },
                "output_format": {"content_format": "txt"},
                "output_structure": {"path_template": "{doc_id}.{ext}"},
            }
        )
        row = _doc_row(doc_id="doc2", content="plain text content")
        op.transform(_make_table([row]))

        assert (tmp_path / "doc2.txt").read_text() == "plain text content"

    def test_writes_json_file_with_content_and_metadata(self, tmp_path):
        op = StorageOutputOperator(
            {
                "name": "storage_output",
                "id": "n1",
                "mode": "processed_content",
                "destination_config": {
                    "provider": "filesystem",
                    "provider_config": {"root_path": str(tmp_path)},
                    "credentials": {},
                },
                "output_format": {"content_format": "json"},
                "output_structure": {"path_template": "{doc_id}.{ext}"},
            }
        )
        row = _doc_row(doc_id="doc3", content="text", metadata={"key": "value"})
        op.transform(_make_table([row]))

        written = json.loads((tmp_path / "doc3.json").read_text())
        assert written["content"] == "text"
        assert written["id"] == "doc3"

    def test_hierarchical_output_structure(self, tmp_path):
        op = StorageOutputOperator(
            {
                "name": "storage_output",
                "id": "n1",
                "mode": "processed_content",
                "destination_config": {
                    "provider": "filesystem",
                    "provider_config": {"root_path": str(tmp_path)},
                    "credentials": {},
                },
                "output_format": {"content_format": "md"},
                "output_structure": {"path_template": "2026/06/{doc_id}.{ext}"},
            }
        )
        row = _doc_row(doc_id="xyz789")
        op.transform(_make_table([row]))

        assert (tmp_path / "2026" / "06" / "xyz789.md").exists()

    def test_multiple_documents(self, tmp_path):
        op = StorageOutputOperator(
            {
                "name": "storage_output",
                "id": "n1",
                "mode": "processed_content",
                "destination_config": {
                    "provider": "filesystem",
                    "provider_config": {"root_path": str(tmp_path)},
                    "credentials": {},
                },
                "output_format": {"content_format": "md"},
                "output_structure": {"path_template": "{doc_id}.{ext}"},
            }
        )
        rows = [_doc_row(doc_id=f"doc{i}", content=f"content {i}") for i in range(5)]
        _tables, metadata = op.transform(_make_table(rows))

        for i in range(5):
            assert (tmp_path / f"doc{i}.md").read_text() == f"content {i}"
        assert metadata["processed_docs"] == 5
        assert metadata["failed_docs_count"] == 0

    def test_overwrite_false_skips_existing(self, tmp_path):
        existing = tmp_path / "doc1.md"
        existing.write_text("original")

        op = StorageOutputOperator(
            {
                "name": "storage_output",
                "id": "n1",
                "mode": "processed_content",
                "destination_config": {
                    "provider": "filesystem",
                    "provider_config": {"root_path": str(tmp_path)},
                    "credentials": {},
                },
                "output_format": {"content_format": "md"},
                "output_structure": {
                    "path_template": "{doc_id}.{ext}",
                    "overwrite_existing": False,
                },
            }
        )
        row = _doc_row(doc_id="doc1", content="new content")
        tables, _metadata = op.transform(_make_table([row]))

        assert existing.read_text() == "original"
        out = tables[0]
        assert out["write_status"][0].as_py() == "skipped"

    def test_output_table_schema(self, tmp_path):
        op = StorageOutputOperator(
            {
                "name": "storage_output",
                "id": "n1",
                "mode": "processed_content",
                "destination_config": {
                    "provider": "filesystem",
                    "provider_config": {"root_path": str(tmp_path)},
                    "credentials": {},
                },
                "output_format": {"content_format": "md"},
                "output_structure": {"path_template": "{doc_id}.{ext}"},
            }
        )
        tables, _ = op.transform(_make_table([_doc_row()]))
        out = tables[0]

        expected_cols = {
            "id",
            "name",
            "path",
            "content",
            "metadata",
            "document_format",
            "write_status",
            "destination_path",
            "bytes_written",
            "write_error",
        }
        assert expected_cols.issubset(set(out.schema.names))


# ---------------------------------------------------------------------------
# Integration: refetch_original
# ---------------------------------------------------------------------------


class TestRefetchOriginalIntegration:
    @pytest.fixture
    def source_dir(self, tmp_path):
        """Create a source directory with a real binary file."""
        src = tmp_path / "source"
        src.mkdir()
        (src / "report.pdf").write_bytes(b"%PDF-1.4 real binary content")
        return src

    @pytest.fixture
    def dest_dir(self, tmp_path):
        return tmp_path / "dest"

    def test_copies_binary_file_verbatim(self, source_dir, dest_dir):
        dest_dir.mkdir()
        source_file = source_dir / "report.pdf"
        op = StorageOutputOperator(
            {
                "name": "storage_output",
                "id": "n1",
                "mode": "refetch_original",
                "ingest_source": {
                    "provider": "filesystem",
                    "provider_config": {"root_path": str(source_dir)},
                    "credentials": {},
                },
                "destination_config": {
                    "provider": "filesystem",
                    "provider_config": {"root_path": str(dest_dir)},
                    "credentials": {},
                },
                "output_structure": {"path_template": "{doc_id}.{ext}"},
            }
        )
        row = _doc_row(
            doc_id="doc1",
            name="report.pdf",
            document_format="pdf",
            path=source_file.as_uri(),
        )
        _tables, metadata = op.transform(_make_table([row]))

        assert (dest_dir / "doc1.pdf").exists()
        assert (dest_dir / "doc1.pdf").read_bytes() == b"%PDF-1.4 real binary content"
        assert metadata["processed_docs"] == 1

    def test_missing_source_file_records_failure(self, source_dir, dest_dir):
        dest_dir.mkdir()
        op = StorageOutputOperator(
            {
                "name": "storage_output",
                "id": "n1",
                "mode": "refetch_original",
                "ingest_source": {
                    "provider": "filesystem",
                    "provider_config": {"root_path": str(source_dir)},
                    "credentials": {},
                },
                "destination_config": {
                    "provider": "filesystem",
                    "provider_config": {"root_path": str(dest_dir)},
                    "credentials": {},
                },
                "output_structure": {"path_template": "{doc_id}.{ext}"},
            }
        )
        row = _doc_row(
            doc_id="missing",
            name="nonexistent.pdf",
            path="file:///does/not/exist.pdf",
        )
        tables, metadata = op.transform(_make_table([row]))

        assert not (dest_dir / "missing.pdf").exists()
        assert tables[0]["write_status"][0].as_py() == "failed"
        assert metadata["failed_docs_count"] == 1


# ---------------------------------------------------------------------------
# Integration: comprehensive_export
# ---------------------------------------------------------------------------


class TestComprehensiveExportIntegration:
    @pytest.fixture
    def source_dir(self, tmp_path):
        src = tmp_path / "source"
        src.mkdir()
        (src / "contract.pdf").write_bytes(b"%PDF contract binary")
        return src

    @pytest.fixture
    def dest_dir(self, tmp_path):
        d = tmp_path / "dest"
        d.mkdir()
        return d

    def test_writes_three_files(self, source_dir, dest_dir):
        source_file = source_dir / "contract.pdf"
        op = StorageOutputOperator(
            {
                "name": "storage_output",
                "id": "n1",
                "mode": "comprehensive_export",
                "ingest_source": {
                    "provider": "filesystem",
                    "provider_config": {"root_path": str(source_dir)},
                    "credentials": {},
                },
                "destination_config": {
                    "provider": "filesystem",
                    "provider_config": {"root_path": str(dest_dir)},
                    "credentials": {},
                },
                "output_format": {"content_format": "md", "include_metadata_sidecar": True},
                "output_structure": {"path_template": "{doc_id}/{name}.{ext}"},
            }
        )
        row = _doc_row(
            doc_id="c1",
            name="contract.pdf",
            content="# Contract\n\nAgreement text.",
            document_format="pdf",
            path=source_file.as_uri(),
            metadata={"parties": ["Alice", "Bob"]},
        )
        _tables, metadata = op.transform(_make_table([row]))

        assert (dest_dir / "c1" / "contract.pdf").exists()
        assert (dest_dir / "c1" / "contract.md").exists()
        assert (dest_dir / "c1" / "contract.json").exists()
        assert metadata["processed_docs"] == 1

    def test_original_binary_is_verbatim(self, source_dir, dest_dir):
        source_file = source_dir / "contract.pdf"
        op = StorageOutputOperator(
            {
                "name": "storage_output",
                "id": "n1",
                "mode": "comprehensive_export",
                "ingest_source": {
                    "provider": "filesystem",
                    "provider_config": {"root_path": str(source_dir)},
                    "credentials": {},
                },
                "destination_config": {
                    "provider": "filesystem",
                    "provider_config": {"root_path": str(dest_dir)},
                    "credentials": {},
                },
                "output_format": {"content_format": "md", "include_metadata_sidecar": True},
                "output_structure": {"path_template": "{doc_id}/{name}.{ext}"},
            }
        )
        row = _doc_row(doc_id="c1", name="contract.pdf", path=source_file.as_uri())
        op.transform(_make_table([row]))

        assert (dest_dir / "c1" / "contract.pdf").read_bytes() == b"%PDF contract binary"

    def test_content_file_matches_content_column(self, source_dir, dest_dir):
        source_file = source_dir / "contract.pdf"
        op = StorageOutputOperator(
            {
                "name": "storage_output",
                "id": "n1",
                "mode": "comprehensive_export",
                "ingest_source": {
                    "provider": "filesystem",
                    "provider_config": {"root_path": str(source_dir)},
                    "credentials": {},
                },
                "destination_config": {
                    "provider": "filesystem",
                    "provider_config": {"root_path": str(dest_dir)},
                    "credentials": {},
                },
                "output_format": {"content_format": "md", "include_metadata_sidecar": True},
                "output_structure": {"path_template": "{doc_id}/{name}.{ext}"},
            }
        )
        row = _doc_row(
            doc_id="c1",
            name="contract.pdf",
            content="# Extracted Text",
            path=source_file.as_uri(),
        )
        op.transform(_make_table([row]))

        assert (dest_dir / "c1" / "contract.md").read_text() == "# Extracted Text"

    def test_sidecar_json_structure(self, source_dir, dest_dir):
        source_file = source_dir / "contract.pdf"
        op = StorageOutputOperator(
            {
                "name": "storage_output",
                "id": "n1",
                "mode": "comprehensive_export",
                "ingest_source": {
                    "provider": "filesystem",
                    "provider_config": {"root_path": str(source_dir)},
                    "credentials": {},
                },
                "destination_config": {
                    "provider": "filesystem",
                    "provider_config": {"root_path": str(dest_dir)},
                    "credentials": {},
                },
                "output_format": {"content_format": "md", "include_metadata_sidecar": True},
                "output_structure": {"path_template": "{doc_id}/{name}.{ext}"},
            }
        )
        row = _doc_row(
            doc_id="c1",
            name="contract.pdf",
            path=source_file.as_uri(),
            metadata={"parties": ["Alice", "Bob"]},
        )
        op.transform(_make_table([row]))

        sidecar = json.loads((dest_dir / "c1" / "contract.json").read_text())
        assert sidecar["id"] == "c1"
        assert sidecar["name"] == "contract.pdf"
        assert sidecar["document_format"] == "pdf"
        assert sidecar["metadata"]["parties"] == ["Alice", "Bob"]

    def test_no_sidecar_when_disabled(self, source_dir, dest_dir):
        source_file = source_dir / "contract.pdf"
        op = StorageOutputOperator(
            {
                "name": "storage_output",
                "id": "n1",
                "mode": "comprehensive_export",
                "ingest_source": {
                    "provider": "filesystem",
                    "provider_config": {"root_path": str(source_dir)},
                    "credentials": {},
                },
                "destination_config": {
                    "provider": "filesystem",
                    "provider_config": {"root_path": str(dest_dir)},
                    "credentials": {},
                },
                "output_format": {"content_format": "md", "include_metadata_sidecar": False},
                "output_structure": {"path_template": "{doc_id}/{name}.{ext}"},
            }
        )
        row = _doc_row(doc_id="c1", name="contract.pdf", path=source_file.as_uri())
        op.transform(_make_table([row]))

        assert not (dest_dir / "c1" / "contract.json").exists()
        assert (dest_dir / "c1" / "contract.pdf").exists()
        assert (dest_dir / "c1" / "contract.md").exists()
