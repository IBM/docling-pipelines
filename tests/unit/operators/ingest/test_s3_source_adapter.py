#!/usr/bin/env python3

import os
from datetime import datetime
from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import ClientError
from pydantic import ValidationError

from docpipe.core.operators.ingest.adapters.outbound.sources.s3.adapter import S3SourceAdapter
from docpipe.core.operators.ingest.adapters.outbound.sources.s3.config import S3SourceConfig

# Configure pytest-asyncio
pytestmark = pytest.mark.asyncio

_TEST_ACCESS_KEY = os.environ.get("TEST_AWS_ACCESS_KEY", "test-access-key-id")
_TEST_SECRET_KEY = os.environ.get("TEST_AWS_SECRET_KEY", "test-secret-access-key")


async def collect_async(async_gen):
    """Helper to collect async generator results."""
    return [item async for item in async_gen]


class TestS3SourceConfig:
    """Test S3SourceConfig validation and normalization."""

    def test_strips_credentials_and_normalizes_fields(self):
        """Test that credentials are stripped and fields are normalized."""
        config = S3SourceConfig(
            access_key=f" {_TEST_ACCESS_KEY} ",
            secret_key=f" {_TEST_SECRET_KEY} ",
            bucket=" my-bucket ",
            prefix="/documents/",
            endpoint_url=" https://s3.example.com/ ",
            region="us-east-1",
            recursive=True,
            file_extensions=["pdf", ".txt", ".DOCX"],
            max_file_size_mb=100,
        )
        assert config.access_key == _TEST_ACCESS_KEY
        assert config.secret_key == _TEST_SECRET_KEY
        assert config.bucket == "my-bucket"
        assert config.prefix == "documents/"  # Leading slash removed, trailing slash added
        assert config.endpoint_url == "https://s3.example.com"  # Trailing slash removed
        assert config.file_extensions == [
            ".pdf",
            ".txt",
            ".docx",
        ]  # Normalized to lowercase with dots

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
            access_key=_TEST_ACCESS_KEY,
            secret_key=_TEST_SECRET_KEY,
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
        assert schema.__module__ == "docpipe.core.operators.ingest.adapters.outbound.sources.s3.config"

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
            "access_key": _TEST_ACCESS_KEY,
            "secret_key": _TEST_SECRET_KEY,
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
            with patch.object(adapter, "_get_aws_account_id", return_value=None):
                success, message = await adapter.test_connection(config)

        assert success is True
        assert "Successfully connected" in message
        assert "5 object(s)" in message
        mock_client.list_objects_v2.assert_called_once_with(Bucket="test-bucket", Prefix="documents/", MaxKeys=1)

    @pytest.mark.asyncio
    async def test_test_connection_no_such_bucket(self, adapter, config):
        """Test connection test with non-existent bucket."""
        mock_client = Mock()
        error_response = {
            "Error": {
                "Code": "NoSuchBucket",
                "Message": "The specified bucket does not exist",
            }
        }
        mock_client.list_objects_v2.side_effect = ClientError(error_response, "ListObjectsV2")

        with patch.object(adapter, "_create_s3_client", return_value=mock_client):
            with patch.object(adapter, "_get_aws_account_id", return_value=None):
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
            with patch.object(adapter, "_get_aws_account_id", return_value=None):
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
        """Test fetching documents from S3 with lazy loading (no binary download)."""
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

        # Note: head_object no longer called - content type determined from file extension
        # This is an optimization to reduce API calls

        with patch.object(adapter, "_create_s3_client", return_value=mock_client):
            with patch.object(adapter, "_get_aws_account_id", return_value=None):
                documents = await collect_async(adapter.fetch_documents(config))

        assert len(documents) == 2
        # Check that all documents are Document instances by class name and module
        # (avoids import identity issues in CI)
        for doc in documents:
            assert doc.__class__.__name__ == "Document"
            assert doc.__class__.__module__ == "docpipe.core.operators.ingest.domain.models"
        assert documents[0].name == "file1.pdf"
        assert documents[1].name == "file2.txt"
        # Verify lazy loading: content should be empty
        assert documents[0].content == b""
        assert documents[1].content == b""
        assert documents[0].metadata["bucket"] == "test-bucket"
        assert documents[0].metadata["key"] == "documents/file1.pdf"
        # Verify get_object was NOT called (lazy loading)
        mock_client.get_object.assert_not_called()


class TestResolveAwsAccountId:
    """Tests for _resolve_aws_account_id and _get_aws_account_id."""

    @pytest.fixture
    def adapter(self):
        return S3SourceAdapter()

    @pytest.fixture
    def aws_config(self):
        return S3SourceConfig(
            access_key=_TEST_ACCESS_KEY,
            secret_key=_TEST_SECRET_KEY,
            bucket="test-bucket",
            region="us-east-1",
        )

    @pytest.fixture
    def cos_config(self):
        """S3-compatible (IBM COS) config — STS must be skipped."""
        return S3SourceConfig(
            access_key=_TEST_ACCESS_KEY,
            secret_key=_TEST_SECRET_KEY,
            bucket="test-bucket",
            endpoint_url="https://s3.us-south.cloud-object-storage.appdomain.cloud",
        )

    def test_returns_account_id_for_aws(self, adapter, aws_config):
        """STS GetCallerIdentity is called and account ID is returned for real AWS."""
        mock_sts = Mock()
        mock_sts.get_caller_identity.return_value = {"Account": "123456789012"}

        with patch("boto3.client", return_value=mock_sts) as mock_boto:
            account_id = adapter._get_aws_account_id(aws_config)

        assert account_id == "123456789012"
        mock_boto.assert_called_once_with(
            "sts",
            aws_access_key_id=_TEST_ACCESS_KEY,
            aws_secret_access_key=_TEST_SECRET_KEY,
            region_name="us-east-1",
        )

    def test_skips_sts_for_s3_compatible_storage(self, adapter, cos_config):
        """No STS call is made when endpoint_url is set (S3-compatible storage)."""
        with patch("boto3.client") as mock_boto:
            account_id = adapter._get_aws_account_id(cos_config)

        assert account_id is None
        mock_boto.assert_not_called()

    def test_returns_none_on_sts_client_error(self, adapter, aws_config):
        """Gracefully returns None when STS returns a ClientError."""
        mock_sts = Mock()
        error_response = {"Error": {"Code": "AccessDenied", "Message": "Not authorized"}}
        mock_sts.get_caller_identity.side_effect = ClientError(error_response, "GetCallerIdentity")

        with patch("boto3.client", return_value=mock_sts):
            account_id = adapter._get_aws_account_id(aws_config)

        assert account_id is None

    def test_returns_none_on_unexpected_exception(self, adapter, aws_config):
        """Gracefully returns None on any unexpected error."""
        with patch("boto3.client", side_effect=RuntimeError("network error")):
            account_id = adapter._get_aws_account_id(aws_config)

        assert account_id is None

    def test_resolve_without_region(self, adapter):
        """region_name is omitted from STS kwargs when config.region is None."""
        config = S3SourceConfig(
            access_key=_TEST_ACCESS_KEY,
            secret_key=_TEST_SECRET_KEY,
            bucket="test-bucket",
        )
        mock_sts = Mock()
        mock_sts.get_caller_identity.return_value = {"Account": "999888777666"}

        with patch("boto3.client", return_value=mock_sts) as mock_boto:
            account_id = adapter._get_aws_account_id(config)

        assert account_id == "999888777666"
        mock_boto.assert_called_once_with(
            "sts",
            aws_access_key_id=_TEST_ACCESS_KEY,
            aws_secret_access_key=_TEST_SECRET_KEY,
        )


class TestExpectedBucketOwnerPropagation:
    """Tests that ExpectedBucketOwner is passed to S3 API calls when account ID is resolved."""

    @pytest.fixture
    def adapter(self):
        return S3SourceAdapter()

    @pytest.fixture
    def config(self):
        return S3SourceConfig(
            access_key=_TEST_ACCESS_KEY,
            secret_key=_TEST_SECRET_KEY,
            bucket="test-bucket",
            prefix="docs/",
        )

    @pytest.mark.asyncio
    async def test_test_connection_passes_expected_bucket_owner(self, adapter, config):
        """list_objects_v2 receives ExpectedBucketOwner when account ID is resolved."""
        mock_client = Mock()
        mock_client.list_objects_v2.return_value = {"KeyCount": 1, "Contents": [{"Key": "docs/a.pdf"}]}

        with patch.object(adapter, "_create_s3_client", return_value=mock_client):
            with patch.object(adapter, "_get_aws_account_id", return_value="123456789012"):
                await adapter.test_connection(config)

        mock_client.list_objects_v2.assert_called_once_with(
            Bucket="test-bucket", Prefix="docs/", MaxKeys=1, ExpectedBucketOwner="123456789012"
        )

    @pytest.mark.asyncio
    async def test_test_connection_omits_expected_bucket_owner_when_none(self, adapter, config):
        """list_objects_v2 does NOT receive ExpectedBucketOwner when account ID is None."""
        mock_client = Mock()
        mock_client.list_objects_v2.return_value = {"KeyCount": 0}

        with patch.object(adapter, "_create_s3_client", return_value=mock_client):
            with patch.object(adapter, "_get_aws_account_id", return_value=None):
                await adapter.test_connection(config)

        call_kwargs = mock_client.list_objects_v2.call_args[1]
        assert "ExpectedBucketOwner" not in call_kwargs

    @pytest.mark.asyncio
    async def test_fetch_documents_uses_mimetypes_for_content_type(self, adapter, config):
        """Content type is determined from file extension using mimetypes (no head_object call)."""
        mock_client = Mock()
        mock_paginator = Mock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [
            {
                "Contents": [
                    {
                        "Key": "docs/file.pdf",
                        "Size": 1024,
                        "LastModified": datetime(2024, 1, 1),
                        "ETag": '"abc"',
                        "StorageClass": "STANDARD",
                    }
                ]
            }
        ]

        with patch.object(adapter, "_create_s3_client", return_value=mock_client):
            with patch.object(adapter, "_get_aws_account_id", return_value="123456789012"):
                documents = await collect_async(adapter.fetch_documents(config))

        # Verify head_object was NOT called (optimization)
        mock_client.head_object.assert_not_called()

        # Verify content type was determined from extension
        assert len(documents) == 1
        assert documents[0].mimetype == "application/pdf"

    @pytest.mark.asyncio
    async def test_fetch_binary_content_passes_expected_bucket_owner(self, adapter):
        """get_object receives ExpectedBucketOwner when account ID is resolved."""
        mock_client = Mock()
        mock_client.get_object.return_value = {"Body": Mock(read=Mock(return_value=b"data"))}

        connection_params = {"bucket": "test-bucket", "region": "us-east-1"}
        credentials = {"access_key": _TEST_ACCESS_KEY, "secret_key": _TEST_SECRET_KEY}

        with patch("boto3.client", return_value=mock_client):
            with patch.object(adapter, "_resolve_aws_account_id", return_value="123456789012"):
                result = adapter.fetch_binary_content(
                    source_id="s3://test-bucket/docs/file.pdf",
                    connection_params=connection_params,
                    credentials=credentials,
                )

        assert result == b"data"
        mock_client.get_object.assert_called_once_with(
            Bucket="test-bucket", Key="docs/file.pdf", ExpectedBucketOwner="123456789012"
        )

    @pytest.mark.asyncio
    async def test_fetch_binary_content_omits_expected_bucket_owner_for_cos(self, adapter):
        """get_object does NOT include ExpectedBucketOwner for S3-compatible storage."""
        mock_client = Mock()
        mock_client.get_object.return_value = {"Body": Mock(read=Mock(return_value=b"data"))}

        connection_params = {
            "bucket": "test-bucket",
            "endpoint_url": "https://s3.us-south.cloud-object-storage.appdomain.cloud",
        }
        credentials = {"access_key": _TEST_ACCESS_KEY, "secret_key": _TEST_SECRET_KEY}

        with patch("boto3.client", return_value=mock_client):
            with patch.object(adapter, "_resolve_aws_account_id", return_value=None):
                result = adapter.fetch_binary_content(
                    source_id="s3://test-bucket/docs/file.pdf",
                    connection_params=connection_params,
                    credentials=credentials,
                )

        assert result == b"data"
        call_kwargs = mock_client.get_object.call_args[1]
        assert "ExpectedBucketOwner" not in call_kwargs
