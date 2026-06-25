"""Tests for IncrementalMetadataRecord domain model."""

from docpipe.core.incremental_metadata.domain.models import IncrementalMetadataRecord


class TestIncrementalMetadataRecord:
    """Test IncrementalMetadataRecord domain model."""

    def test_create_record_with_all_fields(self):
        """Test creating record with all fields populated."""
        record = IncrementalMetadataRecord(
            job_id="job-1",
            doc_id="doc-1",
            name="document.pdf",
            modified_time=1000,
            job_run_id="run-1",
            deleted=False,
        )

        assert record.job_id == "job-1"
        assert record.doc_id == "doc-1"
        assert record.name == "document.pdf"
        assert record.modified_time == 1000
        assert record.job_run_id == "run-1"
        assert record.deleted is False

    def test_create_record_with_minimal_fields(self):
        """Test creating record with only required fields."""
        record = IncrementalMetadataRecord(job_id="job-1", doc_id="doc-1")

        assert record.job_id == "job-1"
        assert record.doc_id == "doc-1"
        assert record.name is None
        assert record.modified_time is None
        assert record.job_run_id is None
        assert record.deleted is False

    def test_to_dict(self):
        """Test converting record to dictionary."""
        record = IncrementalMetadataRecord(
            job_id="job-1",
            doc_id="doc-1",
            name="document.pdf",
            modified_time=1000,
            job_run_id="run-1",
            deleted=True,
        )

        result = record.to_dict()

        assert result == {
            "job_id": "job-1",
            "doc_id": "doc-1",
            "name": "document.pdf",
            "modified_time": 1000,
            "job_run_id": "run-1",
            "deleted": True,
        }

    def test_from_dict(self):
        """Test creating record from dictionary."""
        data = {
            "job_id": "job-1",
            "doc_id": "doc-1",
            "name": "document.pdf",
            "modified_time": 1000,
            "job_run_id": "run-1",
            "deleted": True,
        }

        record = IncrementalMetadataRecord.from_dict(data)

        assert record.job_id == "job-1"
        assert record.doc_id == "doc-1"
        assert record.name == "document.pdf"
        assert record.modified_time == 1000
        assert record.job_run_id == "run-1"
        assert record.deleted is True

    def test_from_dict_with_missing_optional_fields(self):
        """Test creating record from dict with missing optional fields."""
        data = {"job_id": "job-1", "doc_id": "doc-1"}

        record = IncrementalMetadataRecord.from_dict(data)

        assert record.job_id == "job-1"
        assert record.doc_id == "doc-1"
        assert record.name is None
        assert record.modified_time is None
        assert record.job_run_id is None
        assert record.deleted is False

    def test_roundtrip_to_dict_from_dict(self):
        """Test roundtrip conversion to/from dict."""
        original = IncrementalMetadataRecord(
            job_id="job-1",
            doc_id="doc-1",
            name="document.pdf",
            modified_time=1000,
            job_run_id="run-1",
            deleted=False,
        )

        data = original.to_dict()
        restored = IncrementalMetadataRecord.from_dict(data)

        assert restored.job_id == original.job_id
        assert restored.doc_id == original.doc_id
        assert restored.name == original.name
        assert restored.modified_time == original.modified_time
        assert restored.job_run_id == original.job_run_id
        assert restored.deleted == original.deleted
