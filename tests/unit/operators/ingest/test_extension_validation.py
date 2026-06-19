"""Tests for file extension validation in ingestion operators."""

import pytest

from datasift.core.operators.ingest.ingest_local import IngestLocalOperator
from datasift.core.operators.ingest.ingest_source import IngestSourceOperator


class TestIngestLocalExtensionValidation:
    """Test extension validation for IngestLocalOperator."""

    def test_unsupported_include_extension_raises_error(self, tmp_path):
        """Test that unsupported extensions in include_filter raise ValueError."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        config = {
            "paths": [str(tmp_path)],
            "include_filter": ".xyz,.abc",  # Unsupported extensions
        }

        with pytest.raises(ValueError, match="Unsupported file extensions in include_filter"):
            IngestLocalOperator(config)

    def test_unsupported_exclude_extension_raises_error(self, tmp_path):
        """Test that unsupported extensions in exclude_filter raise ValueError."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        config = {
            "paths": [str(tmp_path)],
            "exclude_filter": ".xyz,.abc",  # Unsupported extensions
        }

        with pytest.raises(ValueError, match="Unsupported file extensions in exclude_filter"):
            IngestLocalOperator(config)

    def test_supported_extensions_accepted(self, tmp_path):
        """Test that supported extensions are accepted."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        config = {
            "paths": [str(tmp_path)],
            "include_filter": ".pdf,.docx,.txt",  # Supported extensions
        }

        # Should not raise
        operator = IngestLocalOperator(config)
        assert operator.included_extensions == [".pdf", ".docx", ".txt"]

    def test_no_include_filter_defaults_to_supported(self, tmp_path):
        """Test that no include_filter defaults to all supported extensions."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        config = {
            "paths": [str(tmp_path)],
        }

        operator = IngestLocalOperator(config)
        # Should default to supported extensions
        assert operator.included_extensions is not None
        assert ".pdf" in operator.included_extensions
        assert ".docx" in operator.included_extensions


class TestIngestSourceExtensionValidation:
    """Test extension validation for IngestSourceOperator."""

    def test_unsupported_include_extension_raises_error(self):
        """Test that unsupported extensions in include_filter raise ValueError."""
        config = {
            "provider": "s3",
            "connection_params": {"bucket": "test-bucket"},
            "credentials": {"access_key": "", "secret_key": ""},
            "include_filter": ".xyz,.abc",  # Unsupported extensions
        }

        with pytest.raises(ValueError, match="Unsupported file extensions in include_filter"):
            IngestSourceOperator(config)

    def test_unsupported_exclude_extension_raises_error(self):
        """Test that unsupported extensions in exclude_filter raise ValueError."""
        config = {
            "provider": "s3",
            "connection_params": {"bucket": "test-bucket"},
            "credentials": {"access_key": "", "secret_key": ""},
            "exclude_filter": ".xyz,.abc",  # Unsupported extensions
        }

        with pytest.raises(ValueError, match="Unsupported file extensions in exclude_filter"):
            IngestSourceOperator(config)

    def test_supported_extensions_accepted(self):
        """Test that supported extensions are accepted."""
        config = {
            "provider": "s3",
            "connection_params": {"bucket": "test-bucket"},
            "credentials": {"access_key": "", "secret_key": ""},
            "include_filter": ".pdf,.docx,.txt",  # Supported extensions
        }

        # Should not raise
        operator = IngestSourceOperator(config)
        assert operator.included_extensions == [".pdf", ".docx", ".txt"]

    def test_no_include_filter_defaults_to_supported(self):
        """Test that no include_filter defaults to all supported extensions."""
        config = {
            "provider": "s3",
            "connection_params": {"bucket": "test-bucket"},
            "credentials": {"access_key": "", "secret_key": ""},
        }

        operator = IngestSourceOperator(config)
        # Should default to supported extensions
        assert operator.included_extensions is not None
        assert ".pdf" in operator.included_extensions
        assert ".docx" in operator.included_extensions

    def test_mixed_supported_and_unsupported_raises_error(self):
        """Test that mixing supported and unsupported extensions raises error."""
        config = {
            "provider": "s3",
            "connection_params": {"bucket": "test-bucket"},
            "credentials": {"access_key": "", "secret_key": ""},
            "include_filter": ".pdf,.xyz",  # Mix of supported and unsupported
        }

        with pytest.raises(ValueError, match="Unsupported file extensions"):
            IngestSourceOperator(config)
