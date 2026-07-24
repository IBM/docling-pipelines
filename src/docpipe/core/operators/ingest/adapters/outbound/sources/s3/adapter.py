"""S3 source adapter using boto3."""

import asyncio
import fnmatch
import mimetypes
import os
from datetime import datetime
from typing import Any, AsyncGenerator

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from docpipe.core.operators.ingest.adapters.outbound.sources.factories.source_factory import (
    register_source_adapter,
)
from docpipe.core.operators.ingest.adapters.outbound.sources.s3.config import S3SourceConfig
from docpipe.core.operators.ingest.domain.models import Document
from docpipe.core.operators.ingest.ports.outbound.document_source import DocumentSourcePort
from docpipe.core.operators.operator_utils import resolve_env_var
from docpipe.utils.infrastructure.logging import get_logger

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
    - Parallel downloads with bounded concurrency

    Features:
    - Lazy loading: Documents contain metadata only, no binary content
    - Binary content loaded on-demand by downstream operators
    - Efficient pagination for large buckets
    - Parallel processing with configurable concurrency (default: 20)
    - Metadata preservation (modified time, size, content type)
    - Error handling with detailed logging
    - Support for custom S3 endpoints
    - Cached AWS account ID for security verification

    Authentication:
    - AWS access key and secret key
    - Optional custom endpoint URL for S3-compatible storage
    """

    # Metadata for connector discovery
    SOURCE_NAME = "s3"
    SOURCE_DISPLAY_NAME = "Amazon S3"
    SOURCE_DESCRIPTION = "Ingest documents from Amazon S3 or S3-compatible storage"
    SOURCE_VERSION = "1.0.0"

    def __init__(self):
        """Initialize adapter with cached AWS account ID."""
        self._cached_account_id: str | None = None

    async def fetch_documents(self, config: S3SourceConfig) -> AsyncGenerator[Document, None]:  # type: ignore[override]
        """
        Fetch documents from S3 bucket with batched parallel downloads.

        This method processes S3 objects in batches with bounded concurrency,
        streaming results as they complete. Memory-efficient for large buckets.

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

            # Cache AWS account ID once for all operations
            self._cached_account_id = self._get_aws_account_id(config)

            logger.info(f"Streaming S3 objects from bucket '{config.bucket}' with prefix '{config.prefix}' ")

            # Process in batches to avoid loading all objects into memory
            batch_size = config.max_concurrent_downloads * 5  # Process 5x concurrency at a time
            semaphore = asyncio.Semaphore(config.max_concurrent_downloads)

            async def download_with_semaphore(s3_obj: dict[str, Any]) -> Document | None:
                """Download S3 object with semaphore-bounded concurrency."""
                async with semaphore:
                    try:
                        return await self._download_s3_object(s3_client, config, s3_obj)
                    except Exception as e:
                        logger.error(f"Failed to download S3 object {s3_obj['Key']}: {e}", exc_info=True)
                        return None

            fetched_count = 0
            total_listed = 0
            batch = []

            # Stream objects and process in batches
            for s3_obj in self._list_s3_objects_sync(s3_client, config):
                batch.append(s3_obj)
                total_listed += 1

                # Process batch when it reaches batch_size
                if len(batch) >= batch_size:
                    logger.info(f"Processing batch of {len(batch)} objects (total listed: {total_listed})")

                    # Create tasks for this batch
                    tasks = [download_with_semaphore(obj) for obj in batch]

                    # Gather results in order to maintain deterministic ordering
                    documents = await asyncio.gather(*tasks)
                    for document in documents:
                        if document:
                            fetched_count += 1
                            yield document

                    # Clear batch for next iteration
                    batch.clear()

            # Process remaining objects in final batch
            if batch:
                logger.info(f"Processing final batch of {len(batch)} objects (total listed: {total_listed})")
                tasks = [download_with_semaphore(obj) for obj in batch]

                # Gather results in order to maintain deterministic ordering
                documents = await asyncio.gather(*tasks)
                for document in documents:
                    if document:
                        fetched_count += 1
                        yield document

            logger.info(
                f"Completed streaming from S3 bucket '{config.bucket}': "
                f"listed {total_listed} objects, fetched {fetched_count} documents"
            )

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

            # Resolve bucket owner for security verification (AWS S3 only)
            account_id = self._get_aws_account_id(config)

            list_kwargs: dict[str, Any] = {"Bucket": config.bucket, "Prefix": config.prefix, "MaxKeys": 1}
            if account_id:
                list_kwargs["ExpectedBucketOwner"] = account_id

            # Test bucket access by listing objects (limit to 1)
            response = s3_client.list_objects_v2(**list_kwargs)

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
        *,
        connection_params: dict,
        credentials: dict,
        included_extensions: list[str] | None = None,
        max_files: int | None = None,
    ) -> S3SourceConfig:
        """
        Build S3 configuration from operator parameters.

        Args:
            connection_params: Connection parameters from operator config
            credentials: Credentials from operator config
            included_extensions: File extensions to include (optional)
            max_files: Maximum number of files to fetch while listing/downloading (optional)

        Returns:
            S3SourceConfig: Validated configuration object

        Raises:
            ValueError: If required parameters are missing or invalid
        """
        # Extract required parameters
        access_key = resolve_env_var(credentials.get("access_key"))
        secret_key = resolve_env_var(value=credentials.get("secret_key"))
        bucket = resolve_env_var(value=connection_params.get("bucket"))
        prefix = resolve_env_var(value=connection_params.get("prefix", ""))

        if not access_key:
            raise ValueError("Missing required credential: 'access_key'")
        if not secret_key:
            raise ValueError("Missing required credential: 'secret_key'")
        if not bucket:
            raise ValueError("Missing required connection parameter: 'bucket'")
        # prefix is optional - empty string means scan entire bucket

        # Build configuration
        config_dict = {
            "access_key": access_key,
            "secret_key": secret_key,
            "bucket": bucket,
            "prefix": prefix,
            "endpoint_url": connection_params.get("endpoint_url"),
            "region": connection_params.get("region"),
            "recursive": connection_params.get("recursive", True),
            "file_extensions": included_extensions or [],
            "exclude_patterns": connection_params.get("exclude_patterns", []),
            "max_file_size_mb": connection_params.get("max_file_size_mb"),
            "skip_hidden_files": connection_params.get("skip_hidden_files", True),
            "skip_empty_files": connection_params.get("skip_empty_files", True),
            "max_concurrent_downloads": connection_params.get("max_concurrent_downloads", 20),
            "download_timeout_seconds": connection_params.get("download_timeout_seconds", 300),
            "max_files": max_files,
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

    def _get_aws_account_id(self, config: S3SourceConfig) -> str | None:
        """
        Retrieve the AWS account ID for the configured credentials via STS GetCallerIdentity.

        This is used to populate ExpectedBucketOwner on S3 API calls, preventing
        confused-deputy / bucket-hijacking attacks (SonarQube security finding).

        Only attempted for real AWS S3 (i.e. no custom endpoint_url). Returns None
        gracefully for S3-compatible storage, invalid credentials, or insufficient
        STS permissions so callers can skip the parameter rather than fail hard.

        Args:
            config: S3 configuration

        Returns:
            AWS account ID string (e.g. "123456789012"), or None if unavailable
        """
        return self._resolve_aws_account_id(
            access_key=config.access_key,
            secret_key=config.secret_key,
            region=config.region,
            endpoint_url=config.endpoint_url,
        )

    def _resolve_aws_account_id(
        self,
        *,
        access_key: str,
        secret_key: str,
        region: str | None,
        endpoint_url: str | None,
    ) -> str | None:
        """
        Resolve AWS account ID from credentials via STS GetCallerIdentity.

        Skipped automatically for S3-compatible storage (endpoint_url present).
        Degrades gracefully to None on any failure so S3 operations still proceed.

        Args:
            access_key: AWS access key ID
            secret_key: AWS secret access key
            region: Optional AWS region
            endpoint_url: Custom S3 endpoint (non-None means S3-compatible, skip STS)

        Returns:
            AWS account ID string (e.g. "123456789012"), or None if unavailable
        """
        if endpoint_url:
            # S3-compatible storage (IBM COS, MinIO, etc.) - STS not applicable
            return None

        try:
            sts_kwargs: dict[str, Any] = {
                "aws_access_key_id": access_key,
                "aws_secret_access_key": secret_key,
            }
            if region:
                sts_kwargs["region_name"] = region

            sts_client = boto3.client("sts", **sts_kwargs)
            identity = sts_client.get_caller_identity()
            account_id: str = identity["Account"]
            logger.debug("Resolved AWS account ID for ExpectedBucketOwner: %s", account_id)
            return account_id
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            logger.warning(
                "STS GetCallerIdentity failed (%s); S3 calls will proceed without ExpectedBucketOwner", error_code
            )
            return None
        except Exception as e:
            logger.warning(
                "Unable to resolve AWS account ID via STS; S3 calls will proceed without ExpectedBucketOwner: %s", e
            )
            return None

    def _list_s3_objects_sync(self, s3_client: Any, config: S3SourceConfig):
        """
        List S3 objects synchronously with pagination and filtering.

        This method yields S3 object metadata one at a time as pages are received
        from S3, enabling true streaming behavior without loading all into memory.

        Args:
            s3_client: boto3 S3 client
            config: S3 configuration

        Yields:
            S3 object metadata dictionaries (filtered)
        """
        logger.info(f"Listing S3 objects from bucket '{config.bucket}' with prefix '{config.prefix}'")

        paginator = s3_client.get_paginator("list_objects_v2")
        pages = paginator.paginate(Bucket=config.bucket, Prefix=config.prefix)

        total_listed = 0
        total_yielded = 0

        for page_number, page in enumerate(pages, start=1):
            page_contents = page.get("Contents", [])
            total_listed += len(page_contents)

            logger.debug(
                f"Received S3 page {page_number} with {len(page_contents)} object(s) "
                f"(total listed: {total_listed}, yielded: {total_yielded})"
            )

            if not page_contents:
                continue

            for obj in page_contents:
                if self._should_skip_object(obj, config):
                    continue

                total_yielded += 1
                yield obj

        logger.info(
            f"Completed listing S3 bucket '{config.bucket}': "
            f"listed {total_listed} objects, yielded {total_yielded} after filtering"
        )

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
        Create domain Document from S3 object metadata (lazy loading - no binary download).

        Args:
            s3_client: boto3 S3 client
            config: S3 configuration
            s3_obj: S3 object metadata

        Returns:
            Document with metadata only, or None if processing fails
        """
        key = s3_obj["Key"]

        try:
            # Extract metadata
            last_modified = s3_obj.get("LastModified")
            if isinstance(last_modified, datetime):
                modified_time = last_modified
            else:
                modified_time = None

            size = s3_obj.get("Size", 0)

            # Determine content type from file extension (avoid expensive head_object call)
            content_type = mimetypes.guess_type(key)[0] or "application/octet-stream"

            # Build S3 URI
            s3_uri = f"s3://{config.bucket}/{key}"

            # Build HTTP URL for reference
            if config.endpoint_url:
                # S3-compatible storage
                http_url = f"{config.endpoint_url}/{config.bucket}/{key}"
            else:
                # AWS S3
                region = config.region or "us-east-1"
                http_url = f"https://{config.bucket}.s3.{region}.amazonaws.com/{key}"

            # Determine file extension
            extension = os.path.splitext(key)[1].lower()

            # Create domain document WITHOUT binary content (lazy loading)
            document = Document(
                id=key,
                name=os.path.basename(key),
                content=b"",  # Empty - binary loaded on-demand by downstream operators
                source_url=s3_uri,
                modified_time=modified_time,
                mimetype=content_type,
                size=size,
                extension=extension,
                metadata={
                    "bucket": config.bucket,
                    "key": key,
                    "endpoint_url": config.endpoint_url,
                    "region": config.region,
                    "etag": s3_obj.get("ETag", "").strip('"'),
                    "storage_class": s3_obj.get("StorageClass", "STANDARD"),
                    "content_type": content_type,
                    "http_url": http_url,
                },
            )

            logger.debug(f"Created document metadata for S3 object: {key} ({size} bytes)")
            return document

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            logger.error(f"Failed to get metadata for {key}: S3 error ({error_code}): {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to process {key}: {e}", exc_info=True)
            return None

    def fetch_binary_content(
        self,
        *,
        source_id: str,
        connection_params: dict[str, Any],
        credentials: dict[str, Any],
    ) -> bytes | None:
        """
        Fetch binary content for a specific S3 object on-demand.

        Args:
            source_id: S3 URI (s3://bucket/key) or S3 key
            connection_params: S3 connection parameters (bucket, endpoint_url, region)
            credentials: S3 credentials (access_key, secret_key)

        Returns:
            bytes | None: Binary content of the S3 object, or None if not found or error occurred
        """
        try:
            # Resolve environment variables in credentials
            access_key = resolve_env_var(credentials.get("access_key"))
            secret_key = resolve_env_var(credentials.get("secret_key"))

            if not access_key or not secret_key:
                logger.error(f"Missing S3 credentials for fetching {source_id}")
                return None

            # Parse S3 URI to extract bucket and key
            if source_id.startswith("s3://"):
                # Format: s3://bucket/key
                parts = source_id[5:].split("/", 1)
                bucket = parts[0]
                key = parts[1] if len(parts) > 1 else ""
            else:
                # Assume it's just the key, get bucket from connection_params
                bucket_value = resolve_env_var(connection_params.get("bucket"))
                if not bucket_value:
                    logger.error("Cannot determine S3 bucket from source_id or connection_params")
                    return None
                bucket = str(bucket_value)
                key = source_id

            # Create S3 client
            client_kwargs: dict[str, Any] = {
                "aws_access_key_id": access_key,
                "aws_secret_access_key": secret_key,
            }

            # Add endpoint URL for S3-compatible storage
            endpoint_url = resolve_env_var(connection_params.get("endpoint_url"))
            if endpoint_url:
                client_kwargs["endpoint_url"] = endpoint_url

            # Add region if specified
            region = resolve_env_var(connection_params.get("region"))
            if region:
                client_kwargs["region_name"] = region

            s3_client = boto3.client("s3", **client_kwargs)

            # Resolve bucket owner for security verification (AWS S3 only)
            account_id = self._resolve_aws_account_id(
                access_key=access_key,
                secret_key=secret_key,
                region=region,
                endpoint_url=endpoint_url,
            )

            get_kwargs: dict[str, Any] = {"Bucket": bucket, "Key": key}
            if account_id:
                get_kwargs["ExpectedBucketOwner"] = account_id

            # Download binary content
            logger.info(f"Downloading binary content from S3: bucket={bucket}, key={key}")
            response = s3_client.get_object(**get_kwargs)
            content = response["Body"].read()

            logger.info(f"Successfully downloaded {len(content)} bytes from S3: {source_id}")
            return content

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            logger.error(f"S3 ClientError ({error_code}) fetching {source_id}: {e}")
            return None
        except BotoCoreError as e:
            logger.error(f"S3 BotoCoreError fetching {source_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching binary content from S3 {source_id}: {e}", exc_info=True)
            return None
