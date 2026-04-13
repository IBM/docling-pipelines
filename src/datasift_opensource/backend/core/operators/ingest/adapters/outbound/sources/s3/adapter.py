"""S3 source adapter using boto3."""

import fnmatch
import os
from datetime import datetime
from typing import Any, AsyncGenerator

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from common.util.infrastructure.logging import get_logger
from core.operators.ingest.adapters.outbound.sources.factories.source_factory import (
    register_source_adapter,
)
from core.operators.ingest.adapters.outbound.sources.s3.config import S3SourceConfig
from core.operators.ingest.domain.models import Document
from core.operators.ingest.ports.outbound.document_source import DocumentSourcePort

logger = get_logger(__name__)


@register_source_adapter
class S3SourceAdapter(DocumentSourcePort):
    """
    Adapter for ingesting documents from Amazon S3 or S3-compatible storage.

    This adapter uses boto3 to interact with S3 and supports:
    - AWS S3
    - S3-compatible storage (IBM COS, MinIO, etc.)
    - Recursive prefix traversal
    - File filtering by extension and patterns
    - Hidden file exclusion
    - Size-based filtering

    Features:
    - Direct binary content download (no temporary files)
    - Efficient pagination for large buckets
    - Metadata preservation (modified time, size, content type)
    - Error handling with detailed logging
    - Support for custom S3 endpoints

    Authentication:
    - AWS access key and secret key
    - Optional custom endpoint URL for S3-compatible storage
    """

    # Metadata for connector discovery
    SOURCE_NAME = "s3"
    SOURCE_DISPLAY_NAME = "Amazon S3"
    SOURCE_DESCRIPTION = "Ingest documents from Amazon S3 or S3-compatible storage"
    SOURCE_VERSION = "1.0.0"

    async def fetch_documents(self, config: S3SourceConfig) -> AsyncGenerator[Document, None]:
        """
        Fetch documents from S3 bucket.

        Args:
            config: Validated S3 configuration

        Yields:
            Document: Domain documents from S3

        Raises:
            ClientError: If S3 API calls fail
            BotoCoreError: If boto3 encounters errors
            ValueError: If bucket or credentials are invalid
        """
        try:
            # Create S3 client
            s3_client = self._create_s3_client(config)

            # List and filter objects
            s3_objects = self._list_s3_objects(s3_client, config)

            logger.info(f"Found {len(s3_objects)} objects in S3 bucket '{config.bucket}' with prefix '{config.prefix}'")

            # Download and yield documents
            for s3_obj in s3_objects:
                try:
                    document = await self._download_s3_object(s3_client, config, s3_obj)
                    if document:
                        yield document
                except Exception as e:
                    logger.error(f"Failed to download S3 object {s3_obj['Key']}: {e}", exc_info=True)
                    continue

        except (ClientError, BotoCoreError) as e:
            logger.error(f"S3 error while fetching documents: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Unexpected error while fetching documents from S3: {e}", exc_info=True)
            raise

    async def test_connection(self, config: S3SourceConfig) -> tuple[bool, str]:
        """
        Test connection to S3 bucket.

        Args:
            config: Validated S3 configuration

        Returns:
            Tuple[bool, str]: (success, message)
        """
        try:
            s3_client = self._create_s3_client(config)

            # Test bucket access by listing objects (limit to 1)
            response = s3_client.list_objects_v2(Bucket=config.bucket, Prefix=config.prefix, MaxKeys=1)

            # Check if we have access
            if "Contents" in response or "KeyCount" in response:
                object_count = response.get("KeyCount", 0)
                return (
                    True,
                    f"Successfully connected to S3 bucket '{config.bucket}'. Found {object_count} object(s) with prefix '{config.prefix}'.",
                )
            else:
                return (True, f"Successfully connected to S3 bucket '{config.bucket}', but no objects found.")

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))

            if error_code == "NoSuchBucket":
                return (False, f"Bucket '{config.bucket}' does not exist.")
            elif error_code == "AccessDenied":
                return (False, f"Access denied to bucket '{config.bucket}'. Check credentials and permissions.")
            elif error_code == "InvalidAccessKeyId":
                return (False, "Invalid access key ID. Check your credentials.")
            elif error_code == "SignatureDoesNotMatch":
                return (False, "Invalid secret key. Check your credentials.")
            else:
                return (False, f"S3 error ({error_code}): {error_message}")

        except BotoCoreError as e:
            return (False, f"Boto3 error: {e}")
        except Exception as e:
            return (False, f"Unexpected error: {e}")

    def get_config_schema(self) -> type[S3SourceConfig]:
        """Get the Pydantic configuration model for S3 source."""
        return S3SourceConfig

    def build_config_from_operator_params(
        self,
        connection_params: dict,
        credentials: dict,
        included_extensions: list[str] | None = None,
    ) -> S3SourceConfig:
        """
        Build S3 configuration from operator parameters.

        Args:
            connection_params: Connection parameters from operator config
            credentials: Credentials from operator config
            included_extensions: File extensions to include (optional)

        Returns:
            S3SourceConfig: Validated configuration object

        Raises:
            ValueError: If required parameters are missing or invalid
        """
        # Extract required parameters
        access_key = credentials.get("access_key")
        secret_key = credentials.get("secret_key")
        bucket = connection_params.get("bucket")

        if not access_key:
            raise ValueError("Missing required credential: 'access_key'")
        if not secret_key:
            raise ValueError("Missing required credential: 'secret_key'")
        if not bucket:
            raise ValueError("Missing required connection parameter: 'bucket'")

        # Build configuration
        config_dict = {
            "access_key": access_key,
            "secret_key": secret_key,
            "bucket": bucket,
            "prefix": connection_params.get("prefix", ""),
            "endpoint_url": connection_params.get("endpoint_url"),
            "region": connection_params.get("region"),
            "recursive": connection_params.get("recursive", True),
            "file_extensions": included_extensions or [],
            "exclude_patterns": connection_params.get("exclude_patterns", []),
            "max_file_size_mb": connection_params.get("max_file_size_mb"),
            "skip_hidden_files": connection_params.get("skip_hidden_files", True),
            "skip_empty_files": connection_params.get("skip_empty_files", True),
            "max_concurrent_downloads": connection_params.get("max_concurrent_downloads", 5),
            "download_timeout_seconds": connection_params.get("download_timeout_seconds", 300),
        }

        return S3SourceConfig(**config_dict)

    def _create_s3_client(self, config: S3SourceConfig) -> Any:
        """
        Create boto3 S3 client with configuration.

        Args:
            config: S3 configuration

        Returns:
            boto3 S3 client
        """
        client_kwargs: dict[str, Any] = {
            "aws_access_key_id": config.access_key,
            "aws_secret_access_key": config.secret_key,
        }

        # Add endpoint URL for S3-compatible storage
        if config.endpoint_url:
            client_kwargs["endpoint_url"] = config.endpoint_url

        # Add region if specified
        if config.region:
            client_kwargs["region_name"] = config.region

        return boto3.client("s3", **client_kwargs)

    def _list_s3_objects(self, s3_client: Any, config: S3SourceConfig) -> list[dict[str, Any]]:
        """
        List and filter S3 objects based on configuration.

        Args:
            s3_client: boto3 S3 client
            config: S3 configuration

        Returns:
            List of S3 object metadata dictionaries
        """
        objects = []

        # Use paginator for large buckets
        paginator = s3_client.get_paginator("list_objects_v2")
        pages = paginator.paginate(Bucket=config.bucket, Prefix=config.prefix)

        for page in pages:
            if "Contents" not in page:
                continue

            for obj in page["Contents"]:
                # Apply filters
                if self._should_skip_object(obj, config):
                    continue

                objects.append(obj)

        return objects

    def _should_skip_object(self, obj: dict[str, Any], config: S3SourceConfig) -> bool:
        """
        Check if S3 object should be skipped based on filters.

        Args:
            obj: S3 object metadata
            config: S3 configuration

        Returns:
            True if object should be skipped, False otherwise
        """
        key = obj["Key"]
        size = obj.get("Size", 0)

        # Skip directory markers (keys ending with /)
        if key.endswith("/"):
            return True

        # Skip empty files
        if config.skip_empty_files and size == 0:
            return True

        # Skip files exceeding max size
        max_size_bytes = config.get_max_file_size_bytes()
        if max_size_bytes and size > max_size_bytes:
            logger.debug(f"Skipping {key}: size {size} exceeds max {max_size_bytes} bytes")
            return True

        # Skip hidden files/directories
        if config.skip_hidden_files and self._is_hidden_path(key):
            return True

        # Apply file extension filter
        if config.file_extensions:
            file_ext = os.path.splitext(key)[1].lower()
            if file_ext not in config.file_extensions:
                return True

        # Apply exclude patterns
        if config.exclude_patterns:
            filename = os.path.basename(key)
            for pattern in config.exclude_patterns:
                if fnmatch.fnmatch(filename, pattern) or fnmatch.fnmatch(key, pattern):
                    logger.debug(f"Skipping {key}: matches exclude pattern '{pattern}'")
                    return True

        return False

    def _is_hidden_path(self, key: str) -> bool:
        """
        Check if any path component is hidden (starts with .).

        Args:
            key: S3 object key

        Returns:
            True if path contains hidden components
        """
        path_parts = key.split("/")
        return any(part.startswith(".") and part not in [".", ".."] for part in path_parts)

    async def _download_s3_object(
        self, s3_client: Any, config: S3SourceConfig, s3_obj: dict[str, Any]
    ) -> Document | None:
        """
        Download S3 object and create domain Document.

        Args:
            s3_client: boto3 S3 client
            config: S3 configuration
            s3_obj: S3 object metadata

        Returns:
            Document or None if download fails
        """
        key = s3_obj["Key"]

        try:
            # Download object
            response = s3_client.get_object(Bucket=config.bucket, Key=key)
            binary_content = response["Body"].read()

            # Extract metadata
            last_modified = s3_obj.get("LastModified")
            if isinstance(last_modified, datetime):
                modified_time = last_modified
            else:
                modified_time = None

            size = s3_obj.get("Size", len(binary_content))
            content_type = response.get("ContentType", "application/octet-stream")

            # Build S3 URL
            if config.endpoint_url:
                # S3-compatible storage
                source_url = f"{config.endpoint_url}/{config.bucket}/{key}"
            else:
                # AWS S3
                region = config.region or "us-east-1"
                source_url = f"https://{config.bucket}.s3.{region}.amazonaws.com/{key}"

            # Create domain document
            document = Document(
                id=key,
                name=os.path.basename(key),
                content=binary_content,
                source_url=source_url,
                modified_time=modified_time,
                mimetype=content_type,
                size=size,
                metadata={
                    "bucket": config.bucket,
                    "key": key,
                    "etag": s3_obj.get("ETag", "").strip('"'),
                    "storage_class": s3_obj.get("StorageClass", "STANDARD"),
                    "content_type": content_type,
                },
            )

            logger.debug(f"Downloaded S3 object: {key} ({size} bytes)")
            return document

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            logger.error(f"Failed to download {key}: S3 error ({error_code}): {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to download {key}: {e}", exc_info=True)
            return None


# Made with Bob
