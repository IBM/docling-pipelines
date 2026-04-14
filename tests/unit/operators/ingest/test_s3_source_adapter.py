#!/usr/bin/env python3

from datetime import datetime
from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import ClientError
from pydantic import ValidationError

from core.operators.ingest.adapters.outbound.sources.s3.adapter import S3SourceAdapter
from core.operators.ingest.adapters.outbound.sources.s3.config import S3SourceConfig

# Configure pytest-asyncio
pytestmark = pytest.mark.asyncio


async def collect_async(async_gen):
    """Helper to collect async generator results."""
    return [item async for item in async_gen]


class TestS3SourceConfig:
    """Test S3SourceConfig validation and normalization."""

    def test_strips_credentials_and_normalizes_fields(self):
        """Test that credentials are stripped and fields are normalized."""
        config = S3SourceConfig(
            access_key=" AKIAIOSFODNN7EXAMPLE ",
            secret_key=" wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY ",  # pragma: allowlist secret
            bucket=" my-bucket ",
            prefix="/documents/",
            endpoint_url=" https://s3.example.com/ ",
            region="us-east-1",
            recursive=True,
            file_extensions=["pdf", ".txt", ".DOCX"],
            max_file_size_mb=100,
        )
        assert config.access_key == "AKIAIOSFODNN7EXAMPLE"
        assert config.secret_key == "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"  # pragma: allowlist secret
        assert config.bucket == "my-bucket"
        assert config.prefix == "documents/"  # Leading slash removed, trailing slash added
        assert config.endpoint_url == "https://s3.example.com"  # Trailing slash removed
        assert config.file_extensions == [".pdf", ".txt", ".docx"]  # Normalized to lowercase with dots

    def test_rejects_empty_credentials(self):
        """Test that empty credentials are rejected."""
        with pytest.raises(ValidationError, match="access_key cannot be empty"):
            S3SourceConfig(
                access_key=" ",
                secret_key="secret",  # pragma: allowlist secret
                bucket="bucket",
            )

    def test_rejects_empty_bucket(self):
        """Test that empty bucket name is rejected."""
        with pytest.raises(ValidationError, match="bucket cannot be empty"):
            S3SourceConfig(
                access_key="key",
                secret_key="secret",  # pragma: allowlist secret
                bucket=" ",
            )

    def test_rejects_invalid_endpoint_url(self):
        """Test that invalid endpoint URL is rejected."""
        with pytest.raises(ValidationError, match="endpoint_url must start with"):
            S3SourceConfig(
                access_key="key",
                secret_key="secret",  # pragma: allowlist secret
                bucket="bucket",
                endpoint_url="ftp://invalid.com",
            )

    def test_rejects_negative_max_file_size(self):
        """Test that negative max file size is rejected."""
        with pytest.raises(ValidationError, match="max_file_size_mb must be positive"):
            S3SourceConfig(
                access_key="key",
                secret_key="secret",  # pragma: allowlist secret
                bucket="bucket",
                max_file_size_mb=-1,
            )

    def test_is_s3_compatible(self):
        """Test is_s3_compatible method."""
        # AWS S3
        config_aws = S3SourceConfig(
            access_key="key",
            secret_key="secret",  # pragma: allowlist secret
            bucket="bucket",
        )
        assert not config_aws.is_s3_compatible()

        # S3-compatible storage
        config_compatible = S3SourceConfig(
            access_key="key",
            secret_key="secret",  # pragma: allowlist secret
            bucket="bucket",
            endpoint_url="https://s3.example.com",
        )
        assert config_compatible.is_s3_compatible()

    def test_get_max_file_size_bytes(self):
        """Test get_max_file_size_bytes method."""
        config = S3SourceConfig(
            access_key="key",
            secret_key="secret",  # pragma: allowlist secret
            bucket="bucket",
            max_file_size_mb=10,
        )
        assert config.get_max_file_size_bytes() == 10 * 1024 * 1024

        config_no_limit = S3SourceConfig(
            access_key="key",
            secret_key="secret",  # pragma: allowlist secret
            bucket="bucket",
        )
        assert config_no_limit.get_max_file_size_bytes() is None


class TestS3SourceAdapter:
    """Test S3SourceAdapter functionality."""

    @pytest.fixture
    def adapter(self):
        """Create S3SourceAdapter instance."""
        return S3SourceAdapter()

    @pytest.fixture
    def config(self):
        """Create test S3SourceConfig."""
        return S3SourceConfig(
            access_key="AKIAIOSFODNN7EXAMPLE",
            secret_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",  # pragma: allowlist secret
            bucket="test-bucket",
            prefix="documents/",
            recursive=True,
            file_extensions=[".pdf", ".txt"],
            skip_hidden_files=True,
            skip_empty_files=True,
        )

    def test_adapter_metadata(self, adapter):
        """Test adapter metadata."""
        assert adapter.SOURCE_NAME == "s3"
        assert adapter.SOURCE_DISPLAY_NAME == "Amazon S3"
        assert "S3" in adapter.SOURCE_DESCRIPTION

    def test_get_config_schema(self, adapter):
        """Test get_config_schema returns correct type."""
        schema = adapter.get_config_schema()
        # Check class name and module to avoid import identity issues in CI
        assert schema.__name__ == "S3SourceConfig"
        assert schema.__module__ == "core.operators.ingest.adapters.outbound.sources.s3.config"

    def test_build_config_from_operator_params(self, adapter):
        """Test building config from operator parameters."""
        connection_params = {
            "bucket": "my-bucket",
            "prefix": "docs/",
            "endpoint_url": "https://s3.example.com",
            "region": "us-west-2",
            "recursive": False,
            "max_file_size_mb": 50,
        }
        credentials = {
            "access_key": "AKIAIOSFODNN7EXAMPLE",
            "secret_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",  # pragma: allowlist secret
        }
        included_extensions = [".pdf", ".docx"]

        config = adapter.build_config_from_operator_params(
            connection_params=connection_params,
            credentials=credentials,
            included_extensions=included_extensions,
        )

        assert config.bucket == "my-bucket"
        assert config.prefix == "docs/"
        assert config.endpoint_url == "https://s3.example.com"
        assert config.region == "us-west-2"
        assert config.recursive is False
        assert config.file_extensions == [".pdf", ".docx"]
        assert config.max_file_size_mb == 50

    def test_build_config_missing_credentials(self, adapter):
        """Test that missing credentials raise ValueError."""
        with pytest.raises(ValueError, match="Missing required credential: 'access_key'"):
            adapter.build_config_from_operator_params(
                connection_params={"bucket": "bucket"},
                credentials={"secret_key": "secret"},  # pragma: allowlist secret
            )

    def test_build_config_missing_bucket(self, adapter):
        """Test that missing bucket raises ValueError."""
        with pytest.raises(ValueError, match="Missing required connection parameter: 'bucket'"):
            adapter.build_config_from_operator_params(
                connection_params={},
                credentials={
                    "access_key": "key",
                    "secret_key": "secret",  # pragma: allowlist secret
                },
            )

    @pytest.mark.asyncio
    async def test_test_connection_success(self, adapter, config):
        """Test successful connection test."""
        mock_client = Mock()
        mock_client.list_objects_v2.return_value = {
            "KeyCount": 5,
            "Contents": [{"Key": "test.pdf"}],
        }

        with patch.object(adapter, "_create_s3_client", return_value=mock_client):
            success, message = await adapter.test_connection(config)

        assert success is True
        assert "Successfully connected" in message
        assert "5 object(s)" in message
        mock_client.list_objects_v2.assert_called_once_with(
            Bucket="test-bucket", Prefix="documents/", MaxKeys=1
        )

    @pytest.mark.asyncio
    async def test_test_connection_no_such_bucket(self, adapter, config):
        """Test connection test with non-existent bucket."""
        mock_client = Mock()
        error_response = {"Error": {"Code": "NoSuchBucket", "Message": "The specified bucket does not exist"}}
        mock_client.list_objects_v2.side_effect = ClientError(error_response, "ListObjectsV2")

        with patch.object(adapter, "_create_s3_client", return_value=mock_client):
            success, message = await adapter.test_connection(config)

        assert success is False
        assert "does not exist" in message

    @pytest.mark.asyncio
    async def test_test_connection_access_denied(self, adapter, config):
        """Test connection test with access denied."""
        mock_client = Mock()
        error_response = {"Error": {"Code": "AccessDenied", "Message": "Access Denied"}}
        mock_client.list_objects_v2.side_effect = ClientError(error_response, "ListObjectsV2")

        with patch.object(adapter, "_create_s3_client", return_value=mock_client):
            success, message = await adapter.test_connection(config)

        assert success is False
        assert "Access denied" in message

    def test_should_skip_object_directory_marker(self, adapter, config):
        """Test that directory markers are skipped."""
        obj = {"Key": "documents/folder/", "Size": 0}
        assert adapter._should_skip_object(obj, config) is True

    def test_should_skip_object_empty_file(self, adapter, config):
        """Test that empty files are skipped when configured."""
        obj = {"Key": "documents/empty.txt", "Size": 0}
        assert adapter._should_skip_object(obj, config) is True

    def test_should_skip_object_hidden_file(self, adapter, config):
        """Test that hidden files are skipped when configured."""
        obj = {"Key": "documents/.hidden.txt", "Size": 100}
        assert adapter._should_skip_object(obj, config) is True

    def test_should_skip_object_wrong_extension(self, adapter, config):
        """Test that files with wrong extension are skipped."""
        obj = {"Key": "documents/file.docx", "Size": 100}
        assert adapter._should_skip_object(obj, config) is True

    def test_should_skip_object_exceeds_max_size(self, adapter):
        """Test that files exceeding max size are skipped."""
        config = S3SourceConfig(
            access_key="key",
            secret_key="secret",  # pragma: allowlist secret
            bucket="bucket",
            max_file_size_mb=1,  # 1 MB limit
        )
        obj = {"Key": "large.pdf", "Size": 2 * 1024 * 1024}  # 2 MB
        assert adapter._should_skip_object(obj, config) is True

    def test_should_not_skip_valid_object(self, adapter, config):
        """Test that valid objects are not skipped."""
        obj = {"Key": "documents/report.pdf", "Size": 1024}
        assert adapter._should_skip_object(obj, config) is False

    def test_is_hidden_path(self, adapter):
        """Test hidden path detection."""
        assert adapter._is_hidden_path("documents/.hidden.txt") is True
        assert adapter._is_hidden_path(".hidden/file.txt") is True
        assert adapter._is_hidden_path("documents/folder/.DS_Store") is True
        assert adapter._is_hidden_path("documents/normal.txt") is False
        assert adapter._is_hidden_path("documents/folder/file.txt") is False

    @pytest.mark.asyncio
    async def test_fetch_documents(self, adapter, config):
        """Test fetching documents from S3."""
        # Mock S3 client
        mock_client = Mock()

        # Mock list_objects_v2 paginator
        mock_paginator = Mock()
        mock_client.get_paginator.return_value = mock_paginator

        # Mock pages with S3 objects
        mock_pages = [
            {
                "Contents": [
                    {
                        "Key": "documents/file1.pdf",
                        "Size": 1024,
                        "LastModified": datetime(2024, 1, 1, 12, 0, 0),
                        "ETag": '"abc123"',
                        "StorageClass": "STANDARD",
                    },
                    {
                        "Key": "documents/file2.txt",
                        "Size": 512,
                        "LastModified": datetime(2024, 1, 2, 12, 0, 0),
                        "ETag": '"def456"',
                        "StorageClass": "STANDARD",
                    },
                ]
            }
        ]
        mock_paginator.paginate.return_value = mock_pages

        # Mock get_object responses
        def mock_get_object(Bucket, Key):  # noqa: N803
            content = b"Mock file content"
            return {
                "Body": Mock(read=Mock(return_value=content)),
                "ContentType": "application/pdf" if Key.endswith(".pdf") else "text/plain",
            }

        mock_client.get_object.side_effect = mock_get_object

        with patch.object(adapter, "_create_s3_client", return_value=mock_client):
            documents = await collect_async(adapter.fetch_documents(config))

        assert len(documents) == 2
        # Check that all documents are Document instances by class name and module
        # (avoids import identity issues in CI)
        for doc in documents:
            assert doc.__class__.__name__ == "Document"
            assert doc.__class__.__module__ == "core.operators.ingest.domain.models"
        assert documents[0].name == "file1.pdf"
        assert documents[1].name == "file2.txt"
        assert documents[0].content == b"Mock file content"
        assert documents[0].metadata["bucket"] == "test-bucket"
        assert documents[0].metadata["key"] == "documents/file1.pdf"

# Made with Bob
