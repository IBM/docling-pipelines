"""Utility functions for fetching binary content from documents on-demand.

This module provides functions to fetch binary content on-demand, supporting both:
1. Cloud sources (S3, SharePoint, Google Drive, etc.) via source adapters
2. Local filesystem sources

The on-demand fetching strategy allows operators to defer binary content fetching until
it's actually needed, reducing memory usage and improving performance.
"""

from pathlib import Path
from typing import Any

from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.operators.ingest.adapters.outbound.sources.factories.source_factory import (
    SourceAdapterFactory,
)
from docpipe.core.operators.ingest.ports.outbound.document_source import DocumentSourcePort
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger(__name__)


def get_binary_content(
    *,
    doc_metadata: dict[str, Any],
    global_config: dict[str, Any],
) -> bytes | None:
    """
    Fetch binary content for a document using on-demand fetching strategy.

    This function determines whether to fetch content from a cloud source (using adapters)
    or from the local filesystem, based on the presence of ingest_source configuration.

    Strategy:
    1. If global_config contains ingest_source: Use cloud provider adapter to fetch on-demand
    2. Otherwise: Read from local file path (existing IngestLocal behavior)

    Args:
        doc_metadata: Document metadata containing 'path', 'source_id', 'source', etc.
            Expected keys:
            - 'path': Local file path (for filesystem sources)
            - 'source_id': Source identifier (for cloud sources)
            - 'source': Source URL or path
        global_config: Global configuration that may contain ingest_source parameters
            Expected structure (if present):
            {
                OperatorConstants.Config.INGEST_SOURCE: {
                    OperatorConstants.Config.PROVIDER: "s3",  # or "sharepoint", "google_drive", etc.
                    OperatorConstants.Config.CONNECTION_PARAMS: {...},
                    OperatorConstants.Config.CREDENTIALS: {...}
                }
            }

    Returns:
        Binary content as bytes, or None if unavailable or error occurred

    Examples:
        >>> # Cloud source (S3)
        >>> config = {
        ...     OperatorConstants.Config.INGEST_SOURCE: {
        ...         OperatorConstants.Config.PROVIDER: "s3",
        ...         OperatorConstants.Config.CONNECTION_PARAMS: {"bucket": "my-bucket", "prefix": "docs/"},
        ...         OperatorConstants.Config.CREDENTIALS: {"access_key": "...", "secret_key": "..."}
        ...     }
        ... }
        >>> metadata = {"source_id": "docs/file.pdf", "name": "file.pdf"}
        >>> content = get_binary_content(doc_metadata=metadata, global_config=config)

        >>> # Local filesystem
        >>> metadata = {"path": "/path/to/file.pdf"}
        >>> content = get_binary_content(doc_metadata=metadata, global_config={})
    """
    try:
        # Check if ingest_source configuration exists
        ingest_source = global_config.get(OperatorConstants.Config.INGEST_SOURCE)

        doc_name = doc_metadata.get("name") or doc_metadata.get("source_id") or doc_metadata.get("path", "unknown")
        logger.info(
            f"get_binary_content called for '{doc_name}': "
            f"ingest_source_present={ingest_source is not None}, "
            f"global_config_keys={list(global_config.keys())}"
        )

        if ingest_source:
            # Cloud source: Use adapter to fetch binary content
            logger.info(
                f"Using cloud source adapter for '{doc_name}', provider={ingest_source.get(OperatorConstants.Config.PROVIDER)}"
            )
            return _fetch_from_cloud_source(
                doc_metadata=doc_metadata,
                ingest_source=ingest_source,
            )
        else:
            # Local source: Read from filesystem
            logger.info(f"Using local filesystem for '{doc_name}'")
            return _read_from_local_file(doc_metadata=doc_metadata)

    except Exception as e:
        doc_name = doc_metadata.get("name") or doc_metadata.get("source_id") or doc_metadata.get("path", "unknown")
        logger.error(
            f"Failed to fetch binary content for document '{doc_name}': {e}",
            exc_info=True,
        )
        return None


def get_adapter_for_provider(
    *,
    provider: str,
    connection_params: dict[str, Any],
    credentials: dict[str, Any],
) -> DocumentSourcePort | None:
    """
    Create source adapter instance for the given provider.

    This function uses the SourceAdapterFactory to instantiate the appropriate
    adapter based on the provider name. The adapter can then be used to fetch
    binary content from the cloud source.

    Args:
        provider: Provider name (e.g., "s3", "sharepoint", "google_drive", "onedrive", "box", "web")
        connection_params: Provider-specific connection parameters
            Examples:
            - S3: {"bucket": "my-bucket", "prefix": "docs/", "region": "us-east-1"}
            - SharePoint: {"site_url": "...", "drive_id": "...", "folder_path": "..."}
            - Google Drive: {"folder_id": "...", "service_account_key": "..."}
        credentials: Authentication credentials
            Examples:
            - S3: {"access_key": "...", "secret_key": "..."}
            - SharePoint: {"client_id": "...", "client_secret": "...", "tenant_id": "..."}
            - Google Drive: {"service_account_json": "..."}

    Returns:
        Adapter instance for fetching binary content, or None if provider not found

    Raises:
        ValueError: If provider is not registered or configuration is invalid

    Examples:
        >>> adapter = get_adapter_for_provider(
        ...     provider="s3",
        ...     connection_params={"bucket": "my-bucket", "prefix": "docs/"},
        ...     credentials={"access_key": "...", "secret_key": "..."}
        ... )
        >>> if adapter:
        ...     # Use adapter to fetch documents
        ...     config = adapter.build_config_from_operator_params(
        ...         connection_params=connection_params,
        ...         credentials=credentials
        ...     )
    """
    try:
        # Check if provider is registered
        if not SourceAdapterFactory.is_registered(provider):
            available = ", ".join(SourceAdapterFactory.get_registered_names())
            logger.error(f"Provider '{provider}' is not registered. Available providers: {available}")
            return None

        # Create adapter instance
        adapter = SourceAdapterFactory.create(provider)
        return adapter

    except Exception as e:
        logger.error(
            f"Failed to create adapter for provider '{provider}': {e}",
            exc_info=True,
        )
        return None


def _fetch_from_cloud_source(
    *,
    doc_metadata: dict[str, Any],
    ingest_source: dict[str, Any],
) -> bytes | None:
    """
    Fetch binary content from cloud source using dynamic adapter lookup.

    This function uses the SourceAdapterFactory to get the appropriate adapter
    and calls its fetch_binary_content() method to download the file.

    Args:
        doc_metadata: Document metadata with source_id or path
        ingest_source: Ingest source configuration with provider, connection_params, credentials

    Returns:
        Binary content as bytes, or None if not found or error occurred
    """
    from docpipe.core.operators.operator_utils import resolve_env_var

    provider = ingest_source.get(OperatorConstants.Config.PROVIDER)
    connection_params = ingest_source.get(OperatorConstants.Config.CONNECTION_PARAMS, {})
    credentials = ingest_source.get(OperatorConstants.Config.CREDENTIALS, {})

    if not provider:
        logger.error(f"Missing '{OperatorConstants.Config.PROVIDER}' in ingest_source configuration")
        return None

    # Get source identifier
    source_id = doc_metadata.get("source_id") or doc_metadata.get("source") or doc_metadata.get("path")
    if not source_id:
        logger.error("Document metadata missing 'source_id', 'source', or 'path'")
        return None

    # Resolve environment variables in credentials (they may be stored unresolved in metadata)
    resolved_credentials = {}
    for key, value in credentials.items():
        if isinstance(value, str):
            resolved_credentials[key] = resolve_env_var(value)
        else:
            resolved_credentials[key] = value

    # Resolve environment variables in connection_params as well
    resolved_connection_params = {}
    for key, value in connection_params.items():
        if isinstance(value, str):
            resolved_connection_params[key] = resolve_env_var(value)
        else:
            resolved_connection_params[key] = value

    # For OneDrive/SharePoint: Pass item_id in credentials if available
    # This allows the adapter to extract the actual item ID when source_id is a web URL
    if "item_id" in doc_metadata:
        resolved_credentials = {**resolved_credentials, "item_id": doc_metadata["item_id"]}

    # Use dynamic adapter lookup
    if not SourceAdapterFactory.is_registered(provider):
        logger.error(f"No adapter registered for provider: {provider}")
        return None

    try:
        # Get adapter instance
        adapter = SourceAdapterFactory.create(provider)

        # Call adapter's fetch_binary_content method with resolved credentials
        return adapter.fetch_binary_content(
            source_id=source_id,
            connection_params=resolved_connection_params,
            credentials=resolved_credentials,
        )
    except Exception as e:
        logger.error(f"Failed to fetch binary content using {provider} adapter: {e}", exc_info=True)
        return None


def _read_from_local_file(
    *,
    doc_metadata: dict[str, Any],
) -> bytes | None:
    """
    Read binary content from local filesystem.

    This is an internal helper function that handles local file reading,
    matching the existing IngestLocal behavior.

    Args:
        doc_metadata: Document metadata containing 'path' key

    Returns:
        Binary content as bytes, or None if file not found or error occurred
    """
    file_path = doc_metadata.get("path")

    if not file_path:
        logger.error("Document metadata missing 'path' for local file reading")
        return None

    try:
        path = Path(file_path)

        if not path.exists():
            logger.error(f"Local file not found: {file_path}")
            return None

        if not path.is_file():
            logger.error(f"Path is not a file: {file_path}")
            return None

        # Read binary content
        with open(path, "rb") as f:
            content = f.read()

        return content

    except Exception as e:
        logger.error(
            f"Failed to read local file '{file_path}': {e}",
            exc_info=True,
        )
        return None
