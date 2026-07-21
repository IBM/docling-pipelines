"""Tests for storage operator domain models."""

from docpipe.core.operators.storage.domain.models import (
    ContentFormat,
    WriteMode,
    WriteResult,
)


class TestWriteMode:
    def test_all_modes_defined(self):
        assert WriteMode.PROCESSED_CONTENT == "processed_content"
        assert WriteMode.REFETCH_ORIGINAL == "refetch_original"
        assert WriteMode.COMPREHENSIVE_EXPORT == "comprehensive_export"

    def test_is_str_enum(self):
        assert isinstance(WriteMode.PROCESSED_CONTENT, str)


class TestContentFormat:
    def test_all_formats_defined(self):
        assert ContentFormat.MD == "md"
        assert ContentFormat.TXT == "txt"
        assert ContentFormat.JSON == "json"


class TestWriteResult:
    def test_success_result(self):
        result = WriteResult(
            doc_id="abc123",
            doc_name="doc.pdf",
            success=True,
            destination_path="/output/doc.md",
            bytes_written=42,
        )
        assert result.write_status == "success"
        assert result.destination_path == "/output/doc.md"
        assert result.bytes_written == 42
        assert result.error_message is None

    def test_failed_result(self):
        result = WriteResult(
            doc_id="abc123",
            doc_name="doc.pdf",
            success=False,
            error_message="Permission denied",
        )
        assert result.write_status == "failed"
        assert result.destination_path is None
        assert result.bytes_written == 0

    def test_skipped_result(self):
        result = WriteResult(
            doc_id="abc123",
            doc_name="doc.pdf",
            success=False,
            error_message="file exists, overwrite disabled",
        )
        assert result.write_status == "skipped"

    def test_defaults(self):
        result = WriteResult(doc_id="x", doc_name="y", success=True)
        assert result.bytes_written == 0
        assert result.destination_path is None
        assert result.error_message is None
