import asyncio
import hashlib
import importlib
import itertools
import json
from typing import Any, ClassVar, Iterator, cast

import pyarrow as pa

# Import standard LangChain loaders
from langchain_core.document_loaders import BaseLoader
from langchain_core.documents import Document

from docpipe.core.constants.constants import (
    AttributeDataTypes,
    DocpipeConstants,
    Metrics,
)
from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.incremental_metadata import IncrementalUpdateService
from docpipe.core.incremental_metadata.adapters.config import create_incremental_metadata_store
from docpipe.core.operators.abstract_operator import AbstractOperator, OperatorCategory
from docpipe.core.operators.ingest.ingest_utils import (
    filter_based_on_extension,
    get_filter_extensions,
    is_doc_previously_processed,
)
from docpipe.core.operators.operator_utils import OperatorUtils
from docpipe.integrations.rest_client import RestClient, RestClientConfig, RestMethod
from docpipe.utils.infrastructure.logging import get_logger

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

        # Initialize RestClient with appropriate configuration for Microsoft Graph API
        rest_config = RestClientConfig(
            timeout=60,  # Graph API can be slow for large files
            retry_backoff_factor=2.0,
        )
        self._rest_client = RestClient(
            config=rest_config,
            base_url=MICROSOFT_GRAPH_API_BASE,
        )

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

        if not isinstance(result, dict):
            raise TypeError(f"Unexpected response type: {type(result).__name__}")

        access_token = result.get("access_token")
        if not access_token:
            raise ValueError(
                f"Failed to acquire Microsoft Graph token: {result.get('error')} - {result.get('error_description')}"
            )

        self._token = access_token
        return access_token

    def _list_files(self, folder_item_id: str | None = None) -> list[dict]:  # NOSONAR python:S3776
        """Recursively list all files in the drive (or a specific folder)."""
        token = self._get_token()
        headers = {"Authorization": f"Bearer {token}"}

        if folder_item_id:
            endpoint = f"/drives/{self.drive_id}/items/{folder_item_id}/children"
        else:
            endpoint = f"/drives/{self.drive_id}/root/children"

        files = []
        while endpoint:
            # Use RestClient for API call
            data = self._rest_client.call_rest_json(
                method=RestMethod.GET,
                endpoint=endpoint,
                headers=headers,
            )

            for item in data.get("value", []):
                if "folder" in item:
                    if self.recursive:
                        files.extend(self._list_files(folder_item_id=item["id"]))
                else:
                    files.append(item)

            # Handle pagination - extract endpoint from nextLink
            next_link = data.get("@odata.nextLink")
            if next_link:
                # Extract the path after the base URL
                endpoint = next_link.replace(MICROSOFT_GRAPH_API_BASE, "")
            else:
                endpoint = None  # type: ignore[assignment]

        return files

    def _download_file(self, item: dict) -> bytes:
        """Download file content from Graph API."""
        token = self._get_token()
        headers = {"Authorization": f"Bearer {token}"}
        download_url = item.get("@microsoft.graph.downloadUrl")

        if not download_url:
            # Fallback: get download URL via API
            endpoint = f"/drives/{self.drive_id}/items/{item['id']}/content"
            response = self._rest_client.call_rest(
                method=RestMethod.GET,
                endpoint=endpoint,
                headers=headers,
                expected_status_codes=[200, 302],  # 302 for redirects
            )
            return response.content

        # For direct download URLs, create a temporary RestClient without base_url
        # since download URLs are complete URLs
        temp_config = RestClientConfig(
            timeout=120,  # Longer timeout for file downloads
            max_retries=3,
            retry_backoff_factor=2.0,
            verify_ssl=True,
        )
        temp_client = RestClient(config=temp_config)
        response = temp_client.call_rest(
            method=RestMethod.GET,
            endpoint=download_url,
        )
        return response.content

    def lazy_load(self) -> Iterator[Document]:
        """Lazily load documents from the Microsoft Graph API drive."""
        # Resolve folder path to an item ID if specified
        folder_item_id = None
        if self.folder_path:
            token = self._get_token()
            headers = {"Authorization": f"Bearer {token}"}
            # Normalize path
            path = self.folder_path.strip("/")
            endpoint = f"/drives/{self.drive_id}/root:/{path}"

            try:
                data = self._rest_client.call_rest_json(
                    method=RestMethod.GET,
                    endpoint=endpoint,
                    headers=headers,
                )
                folder_item_id = data.get("id")
            except Exception as e:
                raise ValueError(f"Folder path '{self.folder_path}' not found in drive '{self.drive_id}': {e!s}") from e

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
                doc._binary_content = binary_content  # type: ignore[attr-defined]
                yield doc
            except Exception as e:
                import logging

                logger = logging.getLogger(__name__)
                logger.error(f"Failed to download file {item.get('name', '')}: {e!s}", exc_info=True)
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


# Configuration keys
PROVIDER_KEY: str = "provider"
CONNECTION_PARAMS_KEY: str = "connection_params"
CREDENTIALS_KEY: str = "credentials"
MAX_FILES_KEY: str = "max_files"
MAX_FILES_DEFAULT_VALUE: int = 100
INCLUDE_FILTER_KEY: str = "include_filter"
EXCLUDE_FILTER_KEY: str = "exclude_filter"
ADAPTER_MANAGED_PROVIDERS: frozenset[str] = frozenset(
    {"s3", "ibm_cos", "sharepoint", "onedrive", "google_drive", "box_driver", "filesystem", "web"}
)

logger = get_logger()

# Import factory and adapters AFTER MicrosoftGraphLoader class definition to avoid circular imports
from docpipe.core.operators.ingest.adapters.outbound.sources.factories.source_factory import (  # noqa: E402, I001
    SourceAdapterFactory,
)

# Import adapters to trigger registration via @register_source_adapter decorator
import docpipe.core.operators.ingest.adapters.outbound.sources  # noqa: E402, F401


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
    owner = DocpipeConstants.OWNER_DOCPIPE

    def validate(self, errors: list, warnings: list, available_features: list):
        """
        Validate operator configuration including adapter-specific requirements.

        This method validates:
        1. Required features (via parent class)
        2. Provider-specific configuration (for adapter-managed providers)

        Args:
            errors: List to append validation errors
            warnings: List to append validation warnings
            available_features: List of available input features
        """
        # Call parent validation for required features
        super().validate(errors=errors, warnings=warnings, available_features=available_features)

        # Validate adapter configuration for adapter-managed providers
        if self.provider in ADAPTER_MANAGED_PROVIDERS:
            try:
                # Attempt to build adapter config to trigger Pydantic validation
                # This will catch missing required fields like secret_key
                _, _ = self._build_adapter_config(self.provider)
            except Exception as e:
                # Extract meaningful error message from Pydantic validation errors
                error_msg = str(e)
                # Format Pydantic validation errors more clearly
                if "validation error" in error_msg.lower():
                    # Extract field-specific errors from Pydantic
                    errors.append(f"Configuration validation failed for provider '{self.provider}': {error_msg}")
                else:
                    errors.append(f"Invalid configuration for provider '{self.provider}': {error_msg}")

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
        self.force_ingest: bool = config.get(DocpipeConstants.FORCE_INGEST, False)
        self.doc_id_hash: str = config.get(
            OperatorConstants.Columns.DOC_ID_HASH, OperatorConstants.Columns.DOC_ID_HASH_DEFAULT
        )
        self.ignore_hidden_files: bool = config.get("ignore_hidden_files", True)
        self.common_log_arguments: dict[str, Any] = {
            DocpipeConstants.JOB_ID: self.job_id,
            DocpipeConstants.JOB_RUN_ID: self.job_run_id,
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

        # Initialize incremental update service
        job_id_for_tracking: str = ""
        if self.context_id:
            job_id_for_tracking = self.context_id
        else:
            if self.job_id:
                job_id_for_tracking = self.job_id
            else:
                job_id_for_tracking = ""

        store = create_incremental_metadata_store(job_id=job_id_for_tracking if job_id_for_tracking else None)
        incremental_service = IncrementalUpdateService(store=store)

        self.previously_processed_docs_dict = (
            None if self.force_ingest else incremental_service.get_all_processed_docs(job_id=job_id_for_tracking)
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
                    "document_format": [],
                    "metadata": [],
                    "source_id": [],
                    "path": [],
                    "modified_time": [],
                },
                schema=pa.schema(
                    [
                        ("id", pa.string()),
                        ("name", pa.string()),
                        ("document_format", pa.string()),
                        ("metadata", pa.string()),
                        ("source_id", pa.string()),
                        ("path", pa.string()),
                        ("modified_time", pa.int64()),
                    ]
                ),
            )

        # Update metadata
        metadata[Metrics.External.TOTAL_DOCS] = (
            len(doc_data) + metadata[Metrics.External.SKIPPED_DOCS_COUNT] + metadata[Metrics.External.FAILED_DOCS_COUNT]
        )
        metadata[Metrics.External.PROCESSED_DOCS] = len(doc_data)

        # Determine node status using common utility
        metadata[Metrics.External.NODE_STATUS] = OperatorUtils.determine_execution_status(
            processed_count=metadata[Metrics.External.PROCESSED_DOCS],
            failed_count=metadata[Metrics.External.FAILED_DOCS_COUNT],
            skipped_count=metadata[Metrics.External.SKIPPED_DOCS_COUNT],
        )

        return [output_table], metadata

    def process_documents(self, metadata: dict[str, Any]) -> list[dict[str, Any]]:  # NOSONAR python:S3776
        """
        Process documents from the configured LangChain loader or new adapter.

        Implements batch-fetch logic: fetches documents in batches of max_files,
        processes them, and continues fetching until max_files newly processed
        documents are reached or no more documents are available.

        For adapters: Uses async generator pattern for true memory efficiency,
        processing documents as they're yielded instead of loading all into memory.

        Args:
            metadata: Metadata dictionary for tracking

        Returns:
            List of document dictionaries
        """
        doc_data: list[dict[str, Any]] = []
        processed_count: int = 0
        total_fetched: int = 0

        try:
            logger.info(
                f"Loading documents from {self.provider}",
                extra=self.common_log_arguments,
            )

            # Get document iterator (lazy loading)
            if SourceAdapterFactory.is_registered(self.provider):
                # Use async generator for memory-efficient streaming
                doc_data = self._process_documents_from_adapter(metadata)
                return doc_data
            else:
                loader: BaseLoader = self._get_loader()
                # Use lazy_load if available, otherwise fall back to load()
                if hasattr(loader, "lazy_load"):
                    documents = cast(Iterator[Document], loader.lazy_load())
                else:
                    documents = iter(loader.load())

                # Process documents in batches until max_files newly processed docs reached
                while processed_count < self.max_files:
                    # Fetch next batch of documents
                    batch = list(itertools.islice(documents, self.max_files))

                    if not batch:
                        # No more documents available
                        logger.info(
                            f"No more documents available. Total fetched: {total_fetched}, processed: {processed_count}",
                            extra=self.common_log_arguments,
                        )
                        break

                    total_fetched += len(batch)
                    logger.info(
                        f"Fetched batch of {len(batch)} documents (total fetched: {total_fetched})",
                        extra=self.common_log_arguments,
                    )

                    # Process each document in the batch
                    for idx, doc in enumerate(batch):
                        if processed_count >= self.max_files:
                            logger.info(
                                f"Reached max files limit: {self.max_files}",
                                extra=self.common_log_arguments,
                            )
                            break

                        # Calculate global index for this document
                        global_idx = total_fetched - len(batch) + idx

                        # Process individual document
                        processed_doc: dict[str, Any] | None = self.process_document(doc, global_idx, metadata)
                        if processed_doc:
                            doc_data.append(processed_doc)
                            processed_count += 1

                    # If we've processed enough documents, stop fetching more batches
                    if processed_count >= self.max_files:
                        break

                logger.info(
                    f"Fetched {total_fetched} documents, processed {processed_count} new documents from {self.provider}",
                    extra=self.common_log_arguments,
                )

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

    def _process_documents_from_adapter(self, metadata: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Process documents from adapter using async generator for memory efficiency.

        This method preserves the async generator pattern from adapters, processing
        documents as they're yielded instead of loading all into memory first.
        Implements batch-fetch logic with incremental processing support.

        Args:
            metadata: Metadata dictionary for tracking

        Returns:
            List of processed document dictionaries

        Raises:
            ValueError: If provider is not registered or configuration is invalid
        """
        # Create adapter instance and build config
        adapter, config = self._build_adapter_config(self.provider)

        doc_data: list[dict[str, Any]] = []
        processed_count: int = 0
        total_fetched: int = 0

        # Process documents using async generator with batch-fetch logic
        async def process_async_generator():
            nonlocal processed_count, total_fetched

            batch: list[Document] = []
            batch_size = self.max_files

            # Iterate through async generator
            async for domain_doc in adapter.fetch_documents(config):  # type: ignore[misc]
                # Convert domain Document to LangChain Document
                langchain_doc = Document(
                    page_content="",
                    metadata={
                        "source": domain_doc.source_url,
                        "name": domain_doc.name,
                        "id": domain_doc.id,
                        "last_modified": domain_doc.modified_time.isoformat() if domain_doc.modified_time else None,
                        "size": domain_doc.size,
                        "mimetype": domain_doc.mimetype,
                        "extension": domain_doc.extension,
                        "has_binary_content": True,
                        **domain_doc.metadata,
                    },
                )
                langchain_doc._binary_content = domain_doc.content  # type: ignore[attr-defined]

                batch.append(langchain_doc)
                total_fetched += 1

                # Process batch when it reaches batch_size
                if len(batch) >= batch_size:
                    logger.info(
                        f"Fetched batch of {len(batch)} documents (total fetched: {total_fetched})",
                        extra=self.common_log_arguments,
                    )

                    # Process documents in batch
                    for idx, doc in enumerate(batch):
                        if processed_count >= self.max_files:
                            logger.info(
                                f"Reached max files limit: {self.max_files}",
                                extra=self.common_log_arguments,
                            )
                            return  # Stop processing

                        global_idx = total_fetched - len(batch) + idx
                        processed_doc = self.process_document(doc, global_idx, metadata)
                        if processed_doc:
                            doc_data.append(processed_doc)
                            processed_count += 1

                    # Clear batch and check if we've processed enough
                    batch.clear()
                    if processed_count >= self.max_files:
                        return  # Stop fetching more documents

            # Process remaining documents in final batch
            if batch and processed_count < self.max_files:
                logger.info(
                    f"Fetched final batch of {len(batch)} documents (total fetched: {total_fetched})",
                    extra=self.common_log_arguments,
                )

                for idx, doc in enumerate(batch):
                    if processed_count >= self.max_files:
                        break

                    global_idx = total_fetched - len(batch) + idx
                    processed_doc = self.process_document(doc, global_idx, metadata)
                    if processed_doc:
                        doc_data.append(processed_doc)
                        processed_count += 1

        # Run async generator in sync context
        try:
            asyncio.get_running_loop()
            # Event loop already running - run in separate thread
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, process_async_generator())
                future.result()
        except RuntimeError:
            # No event loop - safe to create new one
            asyncio.run(process_async_generator())

        logger.info(
            f"Fetched {total_fetched} documents, processed {processed_count} new documents from {self.provider}",
            extra=self.common_log_arguments,
        )

        return doc_data

    def _build_adapter_config(self, provider: str):
        """
        Build provider-specific configuration from operator parameters.

        This method delegates configuration building to the appropriate adapter,
        following the Open/Closed Principle. Each adapter knows how to construct
        its own configuration from operator parameters.

        Args:
            provider: The provider name (e.g., "filesystem", "google_drive")

        Returns:
            Tuple of (adapter instance, provider-specific configuration object)

        Raises:
            ValueError: If provider is not supported or configuration is invalid
        """
        # Create adapter instance to access its config builder
        adapter = SourceAdapterFactory.create(provider)

        # Delegate configuration building to the adapter
        config = adapter.build_config_from_operator_params(
            connection_params=self.connection_params,
            credentials=self.credentials,
            included_extensions=self.included_extensions,
            max_files=self.max_files,
        )

        # Return both adapter and config to avoid creating adapter twice
        return adapter, config

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
            doc_id: str = hashlib.md5(source.encode(), usedforsecurity=False).hexdigest()

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

            # Extract document format from metadata
            document_format: str = doc.metadata.get("extension", "")

            source_id = doc.metadata.get("source_id", source)

            # Create processed document
            processed_doc: dict[str, Any] = {
                "id": doc_id,
                "name": source,
                "document_format": document_format,
                "metadata": json.dumps(doc.metadata),
                "source_id": source_id,
                "path": source,
                "modified_time": modified_time if isinstance(modified_time, int) else 0,
            }

            logger.info(
                f"Successfully processed document: {source} (format: {document_format})",
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

    # REMOVED: extract_content() method - binary loading now handled by downstream operators
    # REMOVED: _get_binary_content() method - no longer needed
    # REMOVED: _check_adapter_binary_content() method - no longer needed
    # REMOVED: _fallback_to_page_content() method - no longer needed
    # Note: Adapters still attach _binary_content to documents, but we don't extract it here.
    # The 'path' field in the output table allows downstream operators to load binary on-demand.

    def _is_hidden_path(self, key: str) -> bool:
        """Check if any path component is hidden (starts with .)."""
        path_parts: list[str] = key.split("/")
        return any(part.startswith(".") and part not in [".", ".."] for part in path_parts)

    def _get_loader(self) -> BaseLoader:
        """
        Factory method to initialize the correct LangChain loader.

        Note: Providers using hexagonal architecture adapters (S3, SharePoint, OneDrive, Google Drive, Web)
        should not call this method. They are handled via _process_documents_from_adapter().
        """

        # 1. Amazon S3 / IBM COS (S3 Compatible), Microsoft SharePoint, OneDrive, Google Drive , Box & Web
        # These providers now use the hexagonal architecture adapter
        if self.provider in ADAPTER_MANAGED_PROVIDERS:
            raise ValueError(
                f"{self.provider} provider should use _process_documents_from_adapter(). "
                "This provider is registered with SourceAdapterFactory and should be handled automatically."
            )

        # 2. Custom / FileNet / Other
        # This allows users to provide a python path to ANY loader class
        elif self.provider == "custom":
            loader_path = self.connection_params.get("loader_class_path")
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

    @staticmethod
    def get_metadata() -> dict[str, Any]:
        """
        Get metadata about the operator including features and attributes.

        Returns operator metadata for the LangChain loader ingest mode.
        """
        metadata_features: dict[str, dict[str, Any]] = {
            OperatorConstants.Columns.ID: {
                OperatorConstants.Columns.NAME: "Document ID",
                OperatorConstants.Config.DESCRIPTION: "Document identifier",
                OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB: True,
                OperatorConstants.Misc.TYPE: OperatorConstants.Types.TYPE_STRING,
            },
            OperatorConstants.Columns.NAME: {
                OperatorConstants.Columns.NAME: "Document Name",
                OperatorConstants.Config.DESCRIPTION: "The source name or file name of the document",
                OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB: False,
                OperatorConstants.Misc.TYPE: OperatorConstants.Types.TYPE_STRING,
            },
            "path": {
                OperatorConstants.Columns.NAME: "Source Path",
                OperatorConstants.Config.DESCRIPTION: "The source identifier (URL, file path, etc.) for the document",
                OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB: False,
                OperatorConstants.Misc.TYPE: OperatorConstants.Types.TYPE_STRING,
            },
            OperatorConstants.Metadata.DOCUMENT_FORMAT: {
                OperatorConstants.Columns.NAME: "Document Format",
                OperatorConstants.Config.DESCRIPTION: "File format/extension of the document (e.g., .pdf, .xlsx)",
                OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
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
            OperatorConstants.Metadata.MODIFIED_TIME: {
                OperatorConstants.Columns.NAME: "Modified Time",
                OperatorConstants.Config.DESCRIPTION: "Last modified timestamp of the source document (Unix epoch time)",
                OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB: False,
                OperatorConstants.Misc.TYPE: OperatorConstants.Types.TYPE_INT64,
            },
            OperatorConstants.Columns.DOC_ID_HASH_DEFAULT: {
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
            OperatorConstants.Misc.SDK: True,
            OperatorConstants.Misc.CATEGORY: IngestSourceOperator.category.value,
            OperatorConstants.Misc.LABEL: "Remote Source Ingest",
            OperatorConstants.Config.DESCRIPTION: "Ingest documents from remote storage sources (S3, IBM COS, SharePoint, OneDrive, Google Drive).",
            OperatorConstants.Config.FEATURES: metadata_features,
            OperatorConstants.Misc.IS_OPERATOR_AVAILABLE: IngestSourceOperator.is_available(),
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
                DocpipeConstants.FORCE_INGEST: {
                    OperatorConstants.Columns.NAME: "Force Ingest",
                    OperatorConstants.Config.DESCRIPTION: "Force re-ingestion of previously processed documents",
                    OperatorConstants.Config.DEFAULT: False,
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.BOOLEAN,
                },
                "ignore_hidden_files": {
                    OperatorConstants.Columns.NAME: "Ignore Hidden Files",
                    OperatorConstants.Config.DESCRIPTION: "Skip files starting with '.' (hidden files)",
                    OperatorConstants.Config.DEFAULT: True,
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.BOOLEAN,
                },
            },
        }
