import asyncio
import hashlib
import importlib
import json
from typing import Any, ClassVar, Iterator
import boto3
import pyarrow as pa

# Import standard LangChain loaders
from langchain_community.document_loaders import (
    S3FileLoader,
)
from langchain_core.document_loaders import BaseLoader
from langchain_core.documents import Document

# Import adapters to trigger registration via @register_source_adapter decorator
# These imports are necessary for the factory to discover available adapters
# Note: Google Drive adapter import moved to lazy loading in _get_loader() to avoid
# requiring google_auth_oauthlib dependency unless actually using Google Drive
from common.constants.constants import (
    AttributeDataTypes,
    DatasiftConstants,
    ExecutionStatus,
    Metrics,
)
from common.constants.operator_constants import OperatorConstants
from common.util.data.incremental_update import IncrementalUpdateUtil
from common.util.infrastructure.logging import get_logger
from core.operators.abstract_operator import AbstractOperator, OperatorCategory
from core.operators.ingest.adapters.outbound.sources.factories.source_factory import (
    SourceAdapterFactory,
)
from core.operators.ingest.ingest_utils import (
    filter_based_on_extension,
    get_filter_extensions,
    is_doc_previously_processed,
)

# Microsoft Graph API Constants
MICROSOFT_LOGIN_URL = "https://login.microsoftonline.com"
MICROSOFT_GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"
MICROSOFT_GRAPH_SCOPE = "https://graph.microsoft.com/.default"
MICROSOFT_OAUTH_TOKEN_PATH = "/oauth2/v2.0/token"


class MicrosoftGraphLoader(BaseLoader):
    """
    Custom LangChain-compatible loader for Microsoft SharePoint and OneDrive
    using the Microsoft Graph API with app-only (client credentials) authentication.

    This bypasses LangChain's O365-based loaders which require delegated (user) auth
    and call /me/drives/ endpoints that are incompatible with app-only tokens.
    """

    # Supported text-extractable file extensions
    TEXT_EXTENSIONS: ClassVar[set[str]] = {
        ".pdf",
        ".docx",
        ".doc",
        ".ppt",
        ".bmp",
        ".gif",
        ".jfif",
        ".jpg",
        ".jpeg",
        ".png",
        ".tiff",
        ".tif",
        ".html",
        ".xlsx",
        ".md",
        ".txt",
    }

    def __init__(
        self,
        drive_id: str,
        client_id: str,
        client_secret: str,
        tenant_id: str,
        folder_path: str | None = None,
        recursive: bool = True,
    ):
        self.drive_id = drive_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.tenant_id = tenant_id
        self.folder_path = folder_path
        self.recursive = recursive
        self._token = None

    def _get_token(self) -> str:
        """Acquire an app-only access token via MSAL client credentials flow."""
        if self._token:
            return self._token
        try:
            import msal
        except ImportError:
            raise ImportError("msal package not found. Install with: pip install msal") from None
        app = msal.ConfidentialClientApplication(
            self.client_id,
            authority=f"{MICROSOFT_LOGIN_URL}/{self.tenant_id}",
            client_credential=self.client_secret,
        )
        result = app.acquire_token_for_client(scopes=[MICROSOFT_GRAPH_SCOPE])
        if "access_token" not in result:
            raise ValueError(
                f"Failed to acquire Microsoft Graph token: {result.get('error')} - {result.get('error_description')}"
            )
        self._token = result["access_token"]
        return self._token

    def _list_files(self, folder_item_id: str | None = None) -> list[dict]:
        """Recursively list all files in the drive (or a specific folder)."""
        import requests

        token = self._get_token()
        headers = {"Authorization": f"Bearer {token}"}

        if folder_item_id:
            url = f"{MICROSOFT_GRAPH_API_BASE}/drives/{self.drive_id}/items/{folder_item_id}/children"
        else:
            url = f"{MICROSOFT_GRAPH_API_BASE}/drives/{self.drive_id}/root/children"

        files = []
        while url:
            r = requests.get(url, headers=headers)
            r.raise_for_status()
            data = r.json()
            for item in data.get("value", []):
                if "folder" in item:
                    if self.recursive:
                        files.extend(self._list_files(folder_item_id=item["id"]))
                else:
                    files.append(item)
            url = data.get("@odata.nextLink")
        return files

    def _download_file(self, item: dict) -> bytes:
        """Download file content from Graph API."""
        import requests

        token = self._get_token()
        headers = {"Authorization": f"Bearer {token}"}
        download_url = item.get("@microsoft.graph.downloadUrl")
        if not download_url:
            # Fallback: get download URL via API
            r = requests.get(
                f"{MICROSOFT_GRAPH_API_BASE}/drives/{self.drive_id}/items/{item['id']}/content",
                headers=headers,
                allow_redirects=True,
            )
            r.raise_for_status()
            return r.content
        r = requests.get(download_url)
        r.raise_for_status()
        return r.content

    def lazy_load(self) -> Iterator[Document]:
        """Lazily load documents from the Microsoft Graph API drive."""
        # Resolve folder path to an item ID if specified
        folder_item_id = None
        if self.folder_path:
            import requests

            token = self._get_token()
            headers = {"Authorization": f"Bearer {token}"}
            # Normalize path
            path = self.folder_path.strip("/")
            r = requests.get(f"{MICROSOFT_GRAPH_API_BASE}/drives/{self.drive_id}/root:/{path}", headers=headers)
            if r.status_code == 200:
                folder_item_id = r.json().get("id")
            else:
                raise ValueError(
                    f"Folder path '{self.folder_path}' not found in drive '{self.drive_id}': {r.status_code} {r.text}"
                )

        files = self._list_files(folder_item_id=folder_item_id)
        for item in files:
            try:
                # Download binary content immediately
                binary_content = self._download_file(item)
                
                metadata = {
                    "source": item.get("name", ""),
                    "drive_id": self.drive_id,
                    "item_id": item.get("id", ""),
                    "size": item.get("size", 0),
                    "last_modified": item.get("lastModifiedDateTime", ""),
                    "web_url": item.get("webUrl", ""),
                    "mime_type": item.get("file", {}).get("mimeType", ""),
                    "has_binary_content": True,
                }
                
                # Create Document and attach binary content
                doc = Document(page_content="", metadata=metadata)
                doc._binary_content = binary_content
                yield doc
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Failed to download file {item.get('name', '')}: {str(e)}", exc_info=True)
                yield Document(
                    page_content="",
                    metadata={
                        "source": item.get("name", ""),
                        "error": str(e),
                        "drive_id": self.drive_id,
                        "item_id": item.get("id", ""),
                    },
                )

    def load(self) -> list[Document]:
        return list(self.lazy_load())


# Aliases for backward compatibility with tests
SharePointLoader = MicrosoftGraphLoader
OneDriveLoader = MicrosoftGraphLoader


# Configuration keys
PROVIDER_KEY: str = "provider"
CONNECTION_PARAMS_KEY: str = "connection_params"
CREDENTIALS_KEY: str = "credentials"
MAX_FILES_KEY: str = "max_files"
MAX_FILES_DEFAULT_VALUE: int = 100
INCLUDE_FILTER_KEY: str = "include_filter"
EXCLUDE_FILTER_KEY: str = "exclude_filter"

logger = get_logger()


class IngestSourceOperator(AbstractOperator):
    """
    Ingest operator for loading documents using LangChain loaders.

    This operator provides a unified interface for ingesting documents from various sources
    including S3, IBM COS, SharePoint, OneDrive, Google Drive, and custom loaders.

    Supports:
    - Multiple cloud storage providers (S3, IBM COS, Google Drive, OneDrive, SharePoint)
    - Custom loader integration via dynamic import
    - File filtering by extension (include/exclude)
    - File count limits
    - Incremental updates (skip previously processed files)
    - Proper metadata tracking and error handling
    """

    short_name: str = "ingest_source"
    category: OperatorCategory = OperatorCategory.Ingest

    def __init__(self, config: dict[str, Any]) -> None:
        """
        Initialize the LangChain-based ingest operator.

        Expected parameters:
        - provider: The storage provider (s3, ibm_cos, sharepoint, onedrive, google_drive, custom)
        - connection_params: Provider-specific connection parameters
        - credentials: Authentication credentials
        - max_files: Maximum number of files to ingest
        - include_filter: Comma-separated list of file extensions to include
        - ignore_hidden_files: Skip files starting with '.' (default: True)
        - exclude_filter: Comma-separated list of file extensions to exclude
        - force_ingest: Force re-ingestion of previously processed documents
        """
        super().__init__(config)
        self.provider: str = config.get(PROVIDER_KEY, "").lower()
        self.connection_params: dict[str, Any] = config.get(CONNECTION_PARAMS_KEY, {})
        self.credentials: dict[str, Any] = config.get(CREDENTIALS_KEY, {})
        self.max_files: int = config.get(MAX_FILES_KEY, MAX_FILES_DEFAULT_VALUE)
        self.included_extensions: list[str] | None = get_filter_extensions(config.get(INCLUDE_FILTER_KEY))
        self.excluded_extensions: list[str] | None = get_filter_extensions(config.get(EXCLUDE_FILTER_KEY))
        self.force_ingest: bool = config.get(DatasiftConstants.FORCE_INGEST, False)
        self.doc_id_hash: str = config.get(
            OperatorConstants.Columns.DOC_ID_HASH, OperatorConstants.Columns.DOC_ID_HASH_DEFAULT
        )
        self.ignore_hidden_files: bool = config.get("ignore_hidden_files", True)
        self.common_log_arguments: dict[str, Any] = {
            DatasiftConstants.JOB_ID: self.job_id,
            DatasiftConstants.JOB_RUN_ID: self.job_run_id,
        }
        self.previously_processed_docs_dict: dict[str, Any] | None = None

    def transform(self, table: pa.Table | None) -> tuple[list[pa.Table], dict[str, Any]]:
        """
        Operator-specific logic to load documents using LangChain loaders.

        Args:
            table: Input PyArrow table (can be None for initial ingestion)

        Returns:
            Tuple of (list of output tables, metadata dictionary)
        """

        # Initialize incremental update utility
        incremental_update_util: IncrementalUpdateUtil = IncrementalUpdateUtil()
        job_id_for_tracking: str = ""
        if self.context_id:
            job_id_for_tracking = self.context_id
        else:
            if self.job_id:
                job_id_for_tracking = self.job_id
            else:
                job_id_for_tracking = ""

        self.previously_processed_docs_dict = (
            None if self.force_ingest else incremental_update_util.get_all_processed_docs(job_id=job_id_for_tracking)
        )

        # Initialize metadata
        metadata: dict[str, Any] = self.create_base_metadata(total_docs_count=0)

        # Process documents
        doc_data: list[dict[str, Any]] = self.process_documents(metadata)

        # Create output table
        output_table: pa.Table
        if doc_data:
            output_table = pa.Table.from_pylist(doc_data)
        else:
            # Create empty table with expected schema (matches IngestLocalOperator output)
            output_table = pa.Table.from_pydict(
                {
                    "id": [],
                    "name": [],
                    "metadata": [],
                    "source_id": [],
                    "path": [],
                    "binary_content": [],
                    "modified_time": [],
                },
                schema=pa.schema(
                    [
                        ("id", pa.string()),
                        ("name", pa.string()),
                        ("metadata", pa.string()),
                        ("source_id", pa.string()),
                        ("path", pa.string()),
                        ("binary_content", pa.binary()),
                        ("modified_time", pa.int64()),
                    ]
                ),
            )

        # Update metadata
        metadata[Metrics.External.TOTAL_DOCS] = (
            len(doc_data) + metadata[Metrics.External.SKIPPED_DOCS_COUNT] + metadata[Metrics.External.FAILED_DOCS_COUNT]
        )
        metadata[Metrics.External.PROCESSED_DOCS] = len(doc_data)

        # Determine node status
        node_status: str = ExecutionStatus.COMPLETED.value
        if metadata[Metrics.External.FAILED_DOCS_COUNT] > 0:
            node_status = ExecutionStatus.COMPLETED_WITH_ERRORS.value
        elif metadata[Metrics.External.SKIPPED_DOCS_COUNT] > 0:
            node_status = ExecutionStatus.COMPLETED_WITH_WARNINGS.value
        metadata[Metrics.External.NODE_STATUS] = node_status

        return [output_table], metadata

    def process_documents(self, metadata: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Process documents from the configured LangChain loader or new adapter.

        Args:
            metadata: Metadata dictionary for tracking

        Returns:
            List of document dictionaries
        """
        doc_data: list[dict[str, Any]] = []
        processed_count: int = 0

        try:
            logger.info(
                f"Loading documents from {self.provider}",
                extra=self.common_log_arguments,
            )

            # Try to use new adapter architecture first
            if SourceAdapterFactory.is_registered(self.provider):
                documents: list[Document] = self._load_documents_via_adapter()
            # Special handling for S3 to filter hidden files before loading
            elif self.provider in ["s3", "ibm_cos"]:
                documents: list[Document] = self._load_s3_documents()
            else:
                loader: BaseLoader = self._get_loader()
                documents: list[Document] = loader.load()

            logger.info(
                f"Loaded {len(documents)} documents from {self.provider}",
                extra=self.common_log_arguments,
            )

            for idx, doc in enumerate(documents):
                if processed_count >= self.max_files:
                    logger.info(
                        f"Reached max files limit: {self.max_files}",
                        extra=self.common_log_arguments,
                    )
                    break

                # Process individual document
                processed_doc: dict[str, Any] | None = self.process_document(doc, idx, metadata)
                if processed_doc:
                    doc_data.append(processed_doc)
                    processed_count += 1

        except Exception as e:
            logger.error(
                f"Error loading documents from {self.provider}: {e!s}",
                extra=self.common_log_arguments,
            )
            self.record_failed_document(
                metadata=metadata,
                doc_id="loader_error",
                doc_name=self.provider,
                reason=f"Failed to load documents: {e!s}",
            )

        return doc_data

    def _load_documents_via_adapter(self) -> list[Document]:
        """
        Load documents using the adapter architecture with automatic provider selection.

        This method uses the SourceAdapterFactory to automatically select and instantiate
        the correct adapter based on the provider name. It eliminates the need for
        provider-specific if-else conditions and delegates configuration building to
        provider-specific config builders.

        Returns:
            List of LangChain Document objects

        Raises:
            ValueError: If provider is not registered or configuration is invalid
        """
        # Get the adapter class for this provider
        adapter_class = SourceAdapterFactory.get_adapter_class(self.provider)
        if not adapter_class:
            raise ValueError(
                f"No adapter registered for provider '{self.provider}'. "
                f"Available providers: {', '.join(SourceAdapterFactory.get_registered_names())}"
            )

        # Build provider-specific configuration
        config = self._build_adapter_config(self.provider)

        # Create adapter instance
        adapter = SourceAdapterFactory.create(self.provider)

        # Run async fetch in sync context and convert to LangChain Documents
        async def fetch_all():
            langchain_docs = []
            async for domain_doc in adapter.fetch_documents(config):
                # Convert domain Document to LangChain Document
                # LangChain Document expects page_content (str) and metadata (dict)
                # Note: We store binary content as a special attribute, not in metadata
                # to avoid JSON serialization issues
                langchain_doc = Document(
                    page_content="",  # Will be populated by extract_content
                    metadata={
                        "source": domain_doc.source_url,
                        "name": domain_doc.name,
                        "id": domain_doc.id,
                        "last_modified": domain_doc.modified_time.isoformat() if domain_doc.modified_time else None,
                        "size": domain_doc.size,
                        "mimetype": domain_doc.mimetype,
                        "extension": domain_doc.extension,
                        # Mark that binary content is available
                        "has_binary_content": True,
                        **domain_doc.metadata,
                    },
                )
                # Store binary content as a private attribute to avoid JSON serialization
                # This will be accessed by extract_content method
                langchain_doc._binary_content = domain_doc.content
                langchain_docs.append(langchain_doc)
            return langchain_docs

        documents = asyncio.run(fetch_all())
        return documents

    def _build_adapter_config(self, provider: str):
        """
        Build provider-specific configuration from operator parameters.

        This method delegates configuration building to the appropriate adapter,
        following the Open/Closed Principle. Each adapter knows how to construct
        its own configuration from operator parameters.

        Args:
            provider: The provider name (e.g., "filesystem", "google_drive")

        Returns:
            Provider-specific configuration object (Pydantic model)

        Raises:
            ValueError: If provider is not supported or configuration is invalid
        """
        # Create adapter instance to access its config builder
        adapter = SourceAdapterFactory.create(provider)

        # Delegate configuration building to the adapter
        return adapter.build_config_from_operator_params(
            connection_params=self.connection_params,
            credentials=self.credentials,
            included_extensions=self.included_extensions,
        )

    def process_document(self, doc: Document, idx: int, metadata: dict[str, Any]) -> dict[str, Any] | None:
        """
        Process a single LangChain document.

        Args:
            doc: LangChain Document object
            idx: Document index
            metadata: Metadata dictionary for tracking

        Returns:
            Processed document dictionary or None if skipped/failed
        """
        try:
            # Extract source information
            source: str = doc.metadata.get("source", f"unknown_{idx}")

            # Check file extension filter
            if filter_based_on_extension(source, self.excluded_extensions, self.included_extensions):
                logger.info(
                    f"Skipping document based on filter: {source}",
                    extra=self.common_log_arguments,
                )
                self.record_skipped_document(
                    metadata=metadata,
                    doc_id=source,
                    doc_name=source,
                    reason="File extension filtered out",
                )
                return None

            # Generate document ID (use source hash for consistency)
            doc_id: str = hashlib.md5(source.encode()).hexdigest()

            # Check if document was previously processed
            # For cloud sources, we use the source path as a proxy for modification time
            modified_time: int | str = doc.metadata.get("last_modified", 0)
            if isinstance(modified_time, str):
                # Try to parse timestamp if it's a string
                try:
                    from dateutil import parser

                    modified_time = int(parser.parse(modified_time).timestamp())
                except Exception:
                    modified_time = 0

            if self.previously_processed_docs_dict and is_doc_previously_processed(
                previously_processed_docs_dict=self.previously_processed_docs_dict,
                doc_id=doc_id,
                modified_time=modified_time,
            ):
                logger.info(
                    f"Skipping already processed document: {source}",
                    extra=self.common_log_arguments,
                )
                self.record_skipped_document(
                    metadata=metadata,
                    doc_id=doc_id,
                    doc_name=source,
                    reason="Document already processed",
                )
                return None

            # Create processed document
            processed_doc: dict[str, Any] = {
                "id": doc_id,
                "name": source,
                "metadata": json.dumps(doc.metadata),
                "source_id": source,
                "modified_time": modified_time if isinstance(modified_time, int) else 0,
            }

            # Download binary content so downstream ExtractDoclingOperator can process it
            if not self.extract_content(
                doc=doc,
                source=source,
                processed_doc=processed_doc,
                metadata=metadata,
                idx=idx,
            ):
                return None

            logger.info(
                f"Successfully processed document: {source}",
                extra=self.common_log_arguments,
            )
            return processed_doc

        except Exception as e:
            logger.error(
                f"Error processing document {idx}: {e!s}",
                extra=self.common_log_arguments,
            )
            self.record_failed_document(
                metadata=metadata,
                doc_id=str(idx),
                doc_name=doc.metadata.get("source", f"unknown_{idx}"),
                reason=f"Processing error: {e!s}",
            )
            return None

    def extract_content(
        self,
        doc: Document,
        source: str,
        processed_doc: dict[str, Any],
        metadata: dict[str, Any],
        idx: int,
    ) -> bool:
        """
        Download and store binary content for a document so that downstream operators
        (e.g. ExtractDoclingOperator) can process it.  Mirrors the pattern used by
        IngestLocalOperator.extract_content().

        For providers that expose a file_id / object key in the document metadata the
        binary is fetched directly via the provider SDK.  For all other cases the
        already-extracted page_content text is encoded to UTF-8 bytes as a fallback so
        that the pipeline can still continue.

        Args:
            doc: LangChain Document object returned by the loader.
            source: Source identifier (URL, path, file ID …).
            processed_doc: Document dictionary being built; ``binary_content`` and
                ``path`` are added in-place.
            metadata: Operator metadata dictionary used for error tracking.
            idx: Document index (used for error reporting only).

        Returns:
            True if binary content was successfully obtained, False otherwise.
        """
        try:
            binary_content = self._get_binary_content(doc, source)
            if binary_content is None:
                return False

            processed_doc["binary_content"] = binary_content
            processed_doc["path"] = source
            return True

        except Exception as exc:
            logger.error(
                f"Error extracting content for document {idx} ({source}): {exc}",
                extra=self.common_log_arguments,
            )
            self.record_failed_document(
                metadata=metadata,
                doc_id=str(idx),
                doc_name=source,
                reason=f"Could not extract binary content: {exc}",
            )
            return False

    # Provides fallback if _binary_content is missing
    # Provider specific logic can be removed after all the adapters have been migrated
    def _get_binary_content(self, doc: Document, source: str) -> bytes | None:
        """
        Get binary content from document using appropriate method based on provider.

        Args:
            doc: LangChain Document object.
            source: Source identifier.

        Returns:
            Binary content as bytes, or None if unavailable.
        """
        # Check for pre-fetched binary content from adapters
        binary_content = self._check_adapter_binary_content(doc, source)
        if binary_content is not None:
            return binary_content

        # Try provider-specific download
        if self.provider in ("s3", "ibm_cos"):
            binary_content = self._download_s3_content(doc, source)
            # Fallback to page_content
            if binary_content is None:
                binary_content = self._fallback_to_page_content(doc, source)
        else:
            # For non-S3 providers, use page_content
            binary_content = self._fallback_to_page_content(doc, source)

        return binary_content

    # Required for the new adapters
    def _check_adapter_binary_content(self, doc: Document, source: str) -> bytes | None:
        """Check if binary content is pre-fetched from adapter."""
        if hasattr(doc, "_binary_content") and doc._binary_content is not None:
            logger.info(
                f"Using pre-fetched binary content from adapter for: {source} (size: {len(doc._binary_content)} bytes)",
                extra=self.common_log_arguments,
            )
            return doc._binary_content

        if doc.metadata.get("has_binary_content"):
            logger.error(
                f"Binary content marked as available but not found for: {source}. "
                f"has_attr: {hasattr(doc, '_binary_content')}, "
                f"value: {getattr(doc, '_binary_content', 'NOT_SET')}",
                extra=self.common_log_arguments,
            )
            return None

        return None

    def _download_s3_content(self, doc: Document, source: str) -> bytes | None:
        """Download content from S3 or IBM COS."""
        bucket = self.connection_params.get("bucket")
        key = doc.metadata.get("source", source)

        try:
            client_config = {
                "aws_access_key_id": self.credentials.get("access_key"),
                "aws_secret_access_key": self.credentials.get("secret_key"),
            }
            if self.provider == "ibm_cos":
                client_config["endpoint_url"] = self.connection_params.get("endpoint_url")

            s3_client = boto3.client("s3", **client_config)
            response = s3_client.get_object(Bucket=bucket, Key=key)
            s3_bytes = response["Body"].read()

            logger.info(
                f"Downloaded {len(s3_bytes)} bytes from S3/COS for: {source}",
                extra=self.common_log_arguments,
            )
            return s3_bytes

        except Exception as err:
            logger.warning(
                f"Could not download binary from S3/COS for {source}: {err}. "
                "Falling back to page_content text.",
                extra=self.common_log_arguments,
            )
            return None

    def _fallback_to_page_content(self, doc: Document, source: str) -> bytes:
        """Fallback to encoding page_content as UTF-8 bytes."""
        logger.info(
            f"No provider-specific download available for {source}; using page_content as binary content.",
            extra=self.common_log_arguments,
        )
        return (doc.page_content or "").encode("utf-8")

    def _get_s3_file_keys(self) -> list[str]:
        """
        Get list of S3 file keys, filtering out directories, hidden files, and applying include/exclude filters.
        """
        bucket: str = self.connection_params.get("bucket")
        prefix: str = self.connection_params.get("prefix", "")

        s3_client = self._create_s3_client()
        pages = s3_client.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix)

        file_keys: list[str] = []
        for page in pages:
            if "Contents" in page:
                file_keys.extend(self._filter_s3_objects(page["Contents"]))

        return file_keys

    def _create_s3_client(self) -> Any:
        """Create and configure boto3 S3 client."""
        client_config: dict[str, Any] = {
            "aws_access_key_id": self.credentials.get("access_key"),
            "aws_secret_access_key": self.credentials.get("secret_key"),
        }

        if self.provider == "ibm_cos":
            client_config["endpoint_url"] = self.connection_params.get("endpoint_url")

        return boto3.client("s3", **client_config)

    def _filter_s3_objects(self, objects: list[dict[str, Any]]) -> list[str]:
        """Filter S3 objects to get valid file keys."""
        file_keys: list[str] = []

        for obj in objects:
            key: str = obj["Key"]

            if self._should_skip_s3_object(key, obj):
                continue

            file_keys.append(key)

        return file_keys

    def _should_skip_s3_object(self, key: str, obj: dict[str, Any]) -> bool:
        """Check if S3 object should be skipped based on filters."""
        # Skip directory markers
        if key.endswith("/"):
            return True

        # Skip hidden files/directories
        if self._is_hidden_path(key):
            return True

        # Skip empty files
        if obj.get("Size", 0) == 0:
            return True

        # Skip based on extension filters
        if filter_based_on_extension(key, self.excluded_extensions, self.included_extensions):
            return True

        return False

    def _is_hidden_path(self, key: str) -> bool:
        """Check if any path component is hidden (starts with .)."""
        path_parts: list[str] = key.split("/")
        return any(part.startswith(".") and part not in [".", ".."] for part in path_parts)

    def _load_s3_documents(self) -> list[Document]:
        """
        Load S3 documents with hidden file filtering.
        Uses S3FileLoader to load each file individually, avoiding temp directory issues.
        """
        # Get S3 file keys using existing method (already filters hidden files)
        file_keys: list[str] = self._get_s3_file_keys()

        # Apply max_files limit to file keys
        if self.max_files > 0:
            file_keys = file_keys[: self.max_files]

        # Setup client config
        client_config: dict[str, Any] = {}
        if self.provider == "ibm_cos":
            client_config["endpoint_url"] = self.connection_params.get("endpoint_url")

        # Load each file individually
        documents: list[Document] = []
        bucket: str = self.connection_params.get("bucket")

        for key in file_keys:
            try:
                loader = S3FileLoader(
                    bucket=bucket,
                    key=key,
                    aws_access_key_id=self.credentials.get("access_key"),
                    aws_secret_access_key=self.credentials.get("secret_key"),
                    **client_config,
                )
                documents.extend(loader.load())
            except Exception as e:
                logger.warning(
                    f"Failed to load {key}: {e!s}",
                    extra=self.common_log_arguments,
                )
                continue

        return documents

    def _get_loader(self) -> BaseLoader:
        """
        Factory method to initialize the correct LangChain loader.

        Note: S3/IBM COS providers use _load_s3_documents() directly and should not call this method.
        See process_documents() for the special S3 handling logic.
        """

        # 1. Amazon S3 / IBM COS (S3 Compatible)
        # Note: This case should never be reached as process_documents() calls _load_s3_documents()
        # directly for S3/IBM COS providers. Keeping this for backward compatibility with tests.
        if self.provider in ["s3", "ibm_cos"]:
            raise ValueError(
                "S3/IBM COS providers should not call _get_loader(). "
                "The process_documents() method uses _load_s3_documents() instead."
            )

        # 2. Microsoft SharePoint, OneDrive & Google Drive
        # These providers use the hexagonal architecture adapters via _load_documents_via_adapter()
        # and should not reach this method. Keeping this for backward compatibility.
        elif self.provider in ["sharepoint", "onedrive", "google_drive"]:
            raise ValueError(
                f"{self.provider} provider should use _load_documents_via_adapter(). "
                "This provider is registered with SourceAdapterFactory and should be handled automatically."
            )

        # 5. Custom / FileNet / Other
        # This allows users to provide a python path to ANY loader class
        elif self.provider == "custom":
            loader_path: str = self.connection_params.get("loader_class_path")
            if not loader_path:
                raise ValueError("Provider is 'custom' but 'loader_class_path' is missing.")

            # Dynamic Import: "my_package.loaders.FileNetLoader"
            module_name: str
            class_name: str
            module_name, class_name = loader_path.rsplit(".", 1)
            module: Any = importlib.import_module(module_name)
            loader_class: Any = getattr(module, class_name)

            # Initialize with merged params and credentials
            init_kwargs: dict[str, Any] = {**self.connection_params, **self.credentials}
            return loader_class(**init_kwargs)

        else:
            raise ValueError(f"Provider '{self.provider}' is not supported.")

    def get_metadata(self) -> dict[str, Any]:
        """
        Get metadata about the operator including features and attributes.

        Returns operator metadata for the LangChain loader ingest mode.
        """
        metadata_features: dict[str, dict[str, Any]] = {
            "path": {
                OperatorConstants.Columns.NAME: "Source Path",
                OperatorConstants.Config.DESCRIPTION: "The source identifier (URL, file path, etc.) for the document",
                OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB: False,
                OperatorConstants.Misc.TYPE: OperatorConstants.Types.TYPE_STRING,
            },
            "binary_content": {
                OperatorConstants.Columns.NAME: "Binary Content",
                OperatorConstants.Config.DESCRIPTION: "The raw binary content of the document for downstream extraction operators",
                OperatorConstants.Config.AVAILABLE_FOR_FILTER: False,
                OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB: False,
                OperatorConstants.Misc.TYPE: OperatorConstants.Types.TYPE_STRING,
            },
            "metadata": {
                OperatorConstants.Columns.NAME: "Document Metadata",
                OperatorConstants.Config.DESCRIPTION: "JSON-serialized metadata from the source document",
                OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB: False,
                OperatorConstants.Misc.TYPE: OperatorConstants.Types.TYPE_STRING,
            },
            "source_id": {
                OperatorConstants.Columns.NAME: "Source ID",
                OperatorConstants.Config.DESCRIPTION: "The source identifier (file path, URL, etc.)",
                OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB: False,
                OperatorConstants.Misc.TYPE: OperatorConstants.Types.TYPE_STRING,
            },
            self.doc_id_hash: {
                OperatorConstants.Columns.NAME: "Hash ID",
                OperatorConstants.Config.DESCRIPTION: "Hash ID of the document",
                OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB: True,
                OperatorConstants.Misc.TYPE: OperatorConstants.Types.TYPE_STRING,
                OperatorConstants.Misc.IS_PRIMARY: True,
                OperatorConstants.Misc.TAGS: [
                    OperatorConstants.Misc.MANDATORY,
                    OperatorConstants.Misc.PRIMARY,
                ],
            },
        }

        return {
            OperatorConstants.Misc.CATEGORY: self.category.value,
            OperatorConstants.Config.FEATURES: metadata_features,
            OperatorConstants.Misc.IS_OPERATOR_AVAILABLE: self.is_available(),
            OperatorConstants.Config.ATTRIBUTES: {
                PROVIDER_KEY: {
                    OperatorConstants.Columns.NAME: "Provider",
                    OperatorConstants.Config.DESCRIPTION: "Storage provider (s3, ibm_cos, sharepoint, onedrive, google_drive, custom)",
                    OperatorConstants.Config.REQUIRED: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
                CONNECTION_PARAMS_KEY: {
                    OperatorConstants.Columns.NAME: "Connection Parameters",
                    OperatorConstants.Config.DESCRIPTION: "Provider-specific connection parameters (bucket, prefix, folder_id, etc.)",
                    OperatorConstants.Config.REQUIRED: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.JSON,
                },
                CREDENTIALS_KEY: {
                    OperatorConstants.Columns.NAME: "Credentials",
                    OperatorConstants.Config.DESCRIPTION: "Authentication credentials for the provider",
                    OperatorConstants.Config.REQUIRED: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.JSON,
                },
                MAX_FILES_KEY: {
                    OperatorConstants.Columns.NAME: "Max Files",
                    OperatorConstants.Config.DESCRIPTION: "Maximum number of files to ingest",
                    OperatorConstants.Config.DEFAULT: MAX_FILES_DEFAULT_VALUE,
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.INTEGER,
                },
                INCLUDE_FILTER_KEY: {
                    OperatorConstants.Columns.NAME: "Include File Type",
                    OperatorConstants.Config.DESCRIPTION: "File types to be included (comma-separated extensions)",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.LIST,
                },
                EXCLUDE_FILTER_KEY: {
                    OperatorConstants.Columns.NAME: "Exclude File Type",
                    OperatorConstants.Config.DESCRIPTION: "File types to be excluded (comma-separated extensions)",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.LIST,
                },
            },
        }
