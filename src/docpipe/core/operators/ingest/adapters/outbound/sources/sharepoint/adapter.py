"""SharePoint source adapter using Microsoft Graph API."""

import os
from datetime import datetime
from typing import Any, AsyncGenerator, cast

from pydantic import BaseModel

from docpipe.core.operators.ingest.adapters.outbound.sources.factories.source_factory import (
    register_source_adapter,
)
from docpipe.core.operators.ingest.adapters.outbound.sources.sharepoint.config import SharePointSourceConfig
from docpipe.core.operators.ingest.domain.models import Document

# Import the MicrosoftGraphLoader from ingest_source.py
from docpipe.core.operators.ingest.ingest_source import MicrosoftGraphLoader
from docpipe.core.operators.ingest.ports.outbound.document_source import DocumentSourcePort
from docpipe.core.operators.operator_utils import resolve_env_var
from docpipe.integrations.rest_client import RestMethod
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger(__name__)


@register_source_adapter
class SharePointSourceAdapter(DocumentSourcePort):
    """
    Adapter for ingesting documents from SharePoint using Microsoft Graph API.

    This adapter uses the custom MicrosoftGraphLoader which supports
    app-only authentication (client credentials flow) for SharePoint access.

    Features:
    - App-only authentication using Azure AD client credentials
    - Recursive folder traversal
    - Automatic text extraction from common file types:
      - Text files (.txt, .md, .csv, .json, etc.)
      - PDF files (.pdf)
      - Word documents (.docx, .doc)
      - Excel spreadsheets (.xlsx, .xls)
    - File extension filtering
    - Metadata preservation

    Authentication Requirements:
    - Azure AD App Registration with:
      - Application (client) ID
      - Client secret
      - Tenant (directory) ID
    - Microsoft Graph API permissions:
      - Sites.Read.All (Application permission)
    """

    # Metadata for connector discovery
    SOURCE_NAME = "sharepoint"
    SOURCE_DISPLAY_NAME = "Microsoft SharePoint"
    SOURCE_DESCRIPTION = "Ingest documents from SharePoint using Microsoft Graph API"
    SOURCE_VERSION = "1.0.0"

    async def fetch_documents(self, config: SharePointSourceConfig) -> AsyncGenerator[Document, None]:  # type: ignore[override]  # NOSONAR python:S3776
        """
        Fetch document metadata from SharePoint using Microsoft Graph API.

        This method implements lazy loading - it only fetches metadata, not binary content.
        Binary content is fetched on-demand by the Extract operator via fetch_binary_content().

        Args:
            config: Validated SharePoint configuration (SharePointSourceConfig)

        Yields:
            Document: Domain documents with metadata only (content=b"")

        Raises:
            ImportError: If required dependencies (msal, requests) are not installed
            ValueError: If authentication fails or document library not found
        """
        sharepoint_config: SharePointSourceConfig = config
        try:
            # Create MicrosoftGraphLoader with configuration
            # Note: SharePoint uses document_library_id which is the drive_id in Graph API
            loader = MicrosoftGraphLoader(
                drive_id=sharepoint_config.document_library_id,
                client_id=sharepoint_config.client_id,
                client_secret=sharepoint_config.client_secret,
                tenant_id=sharepoint_config.tenant_id,
                folder_path=sharepoint_config.folder_path,
                recursive=sharepoint_config.recursive,
            )

            # List files to get metadata only (don't download binary content)
            token = loader._get_token()
            headers = {"Authorization": f"Bearer {token}"}

            # Resolve folder path to item ID if specified
            folder_item_id = None
            if sharepoint_config.folder_path:
                path = sharepoint_config.folder_path.strip("/")
                endpoint = f"/drives/{sharepoint_config.document_library_id}/root:/{path}"
                try:
                    data = loader._rest_client.call_rest_json(
                        method=RestMethod.GET,
                        endpoint=endpoint,
                        headers=headers,
                    )
                    folder_item_id = data.get("id")
                except Exception as e:
                    raise ValueError(
                        f"Folder path '{sharepoint_config.folder_path}' not found in document library '{sharepoint_config.document_library_id}': {e!s}"
                    ) from e

            # List files without downloading content
            files = loader._list_files(folder_item_id=folder_item_id)

            # Convert file metadata to domain documents
            for item in files:
                doc_id = item.get("id", "")
                doc_name = item.get("name", "unknown")

                # Apply file extension filter if specified
                if sharepoint_config.file_extensions:
                    file_ext = os.path.splitext(doc_name)[1].lower()
                    if file_ext not in sharepoint_config.file_extensions:
                        continue

                # Apply file size filter if specified
                file_size = item.get("size", 0)
                if sharepoint_config.max_file_size_mb:
                    file_size_mb = file_size / (1024 * 1024)
                    if file_size_mb > sharepoint_config.max_file_size_mb:
                        continue

                # Parse modified time if available
                modified_time = None
                last_modified = item.get("lastModifiedDateTime")
                if last_modified:
                    try:
                        # Microsoft Graph returns ISO 8601 format
                        modified_time = datetime.fromisoformat(last_modified.replace("Z", "+00:00"))
                    except (ValueError, AttributeError):
                        pass

                # Build source URL
                source_url = item.get("webUrl", f"https://sharepoint.com/?id={doc_id}")

                # Get file extension
                extension = os.path.splitext(doc_name)[1].lower()

                # Create domain document WITHOUT binary content (lazy loading)
                document = Document(
                    id=doc_id,
                    name=doc_name,
                    content=b"",  # Empty - binary loaded on-demand by downstream operators
                    source_url=source_url,
                    modified_time=modified_time,
                    mimetype=item.get("file", {}).get("mimeType", "application/octet-stream"),
                    size=file_size,
                    extension=extension,
                    metadata={
                        "source_id": doc_id,  # Required by binary_content_fetcher
                        "document_library_id": sharepoint_config.document_library_id,
                        "item_id": doc_id,
                        "file_size": file_size,
                        "mime_type": item.get("file", {}).get("mimeType"),
                        "created_time": item.get("createdDateTime"),
                        "web_url": source_url,
                        "provider": "sharepoint",
                    },
                )

                logger.debug(f"Created document metadata for SharePoint file: {doc_name} ({file_size} bytes)")
                yield document

        except ImportError as e:
            raise ImportError(
                "Microsoft Graph dependencies not installed. Install with: pip install msal requests"
            ) from e
        except Exception as e:
            raise ValueError(f"Failed to fetch documents from SharePoint: {e!s}") from e

    async def test_connection(self, config: BaseModel) -> tuple[bool, str]:
        """
        Test SharePoint connection using Microsoft Graph API.

        Args:
            config: Validated SharePoint configuration

        Returns:
            Tuple[bool, str]: (success, message)
        """
        sharepoint_config = cast(SharePointSourceConfig, config)
        try:
            # Create loader to test authentication
            loader = MicrosoftGraphLoader(
                drive_id=sharepoint_config.document_library_id,
                client_id=sharepoint_config.client_id,
                client_secret=sharepoint_config.client_secret,
                tenant_id=sharepoint_config.tenant_id,
                folder_path=sharepoint_config.folder_path,
                recursive=False,  # Don't recurse for connection test
            )

            # Try to get access token (this will fail if credentials are invalid)
            token = loader._get_token()

            if not token:
                return False, "Failed to acquire access token"

            # Try to list files (this will fail if document_library_id or folder_path is invalid)
            files = list(loader.lazy_load())

            return True, f"Successfully connected to SharePoint. Found {len(files)} document(s)."

        except ImportError:
            return False, "Microsoft Graph dependencies not installed (msal, requests)"
        except ValueError as e:
            return False, f"Configuration error: {e!s}"
        except Exception as e:
            return False, f"Connection test failed: {e!s}"

    def get_config_schema(self) -> type[BaseModel]:
        """
        Get the configuration schema for this adapter.

        Returns:
            type[BaseModel]: The Pydantic configuration model
        """
        return SharePointSourceConfig

    def fetch_binary_content(
        self,
        *,
        source_id: str,
        connection_params: dict[str, Any],
        credentials: dict[str, Any],
    ) -> bytes | None:
        """
        Fetch binary content for a specific document from SharePoint on-demand.

        Args:
            source_id: SharePoint item ID (file ID) or web URL
            connection_params: Connection parameters (document_library_id, etc.)
            credentials: Authentication credentials (client_id, client_secret, tenant_id)

        Returns:
            bytes | None: Binary content of the SharePoint file, or None if not found or error occurred
        """
        try:
            # Extract required parameters and resolve environment variables
            document_library_id = resolve_env_var(connection_params.get("document_library_id"))
            client_id = resolve_env_var(credentials.get("client_id"))
            client_secret = resolve_env_var(credentials.get("client_secret"))
            tenant_id = resolve_env_var(credentials.get("tenant_id"))

            if not all([document_library_id, client_id, client_secret, tenant_id]):
                logger.error("Missing required parameters for SharePoint binary content fetch")
                return None

            # Handle case where source_id is a web URL instead of item_id
            # During lazy loading, the binary fetcher may receive the web URL as source_id
            # We need to extract the actual item_id from credentials if available
            item_id = source_id
            if source_id.startswith("http"):
                # source_id is a web URL, extract item_id from credentials
                extracted_id = credentials.get("item_id")
                if not extracted_id:
                    logger.error(f"source_id is a web URL but no item_id found in credentials: {source_id}")
                    return None
                item_id = str(extracted_id)
                logger.info(f"Extracted item_id from credentials: {item_id} (source_id was web URL)")

            # Create MicrosoftGraphLoader to reuse authentication logic
            loader = MicrosoftGraphLoader(
                drive_id=str(document_library_id),
                client_id=str(client_id),
                client_secret=str(client_secret),
                tenant_id=str(tenant_id),
                folder_path=None,
                recursive=False,
            )

            # Get access token
            token = loader._get_token()
            headers = {"Authorization": f"Bearer {token}"}

            # Download file content using Graph API
            logger.info(
                f"Downloading binary content from SharePoint: document_library_id={document_library_id}, item_id={item_id}"
            )

            # Try direct download URL first
            endpoint = f"/drives/{document_library_id}/items/{item_id}"
            item_data = loader._rest_client.call_rest_json(
                method=RestMethod.GET,
                endpoint=endpoint,
                headers=headers,
            )

            download_url = item_data.get("@microsoft.graph.downloadUrl")

            if download_url:
                # Use direct download URL
                from docpipe.integrations.rest_client import RestClient, RestClientConfig

                temp_config = RestClientConfig(
                    timeout=120,
                    max_retries=3,
                    retry_backoff_factor=2.0,
                    verify_ssl=True,
                )
                temp_client = RestClient(config=temp_config)
                response = temp_client.call_rest(
                    method=RestMethod.GET,
                    endpoint=download_url,
                )
                content = response.content
            else:
                # Fallback: use content endpoint
                content_endpoint = f"/drives/{document_library_id}/items/{item_id}/content"
                response = loader._rest_client.call_rest(
                    method=RestMethod.GET,
                    endpoint=content_endpoint,
                    headers=headers,
                    expected_status_codes=[200, 302],
                )
                content = response.content

            logger.info(f"Successfully downloaded {len(content)} bytes from SharePoint: {item_id}")
            return content

        except Exception as e:
            logger.error(f"Error fetching binary content from SharePoint {source_id}: {e}", exc_info=True)
            return None

    def build_config_from_operator_params(
        self,
        *,
        connection_params: dict,
        credentials: dict,
        included_extensions: list[str] | None = None,
        max_files: int | None = None,
    ) -> BaseModel:
        """
        Build SharePoint configuration from operator parameters.

        Args:
            connection_params: Connection parameters (document_library_id, folder_path, etc.)
            credentials: Credentials (client_id, client_secret, tenant_id)
            included_extensions: File extensions to include (optional)
            max_files: Maximum number of files to fetch (optional, not used by SharePoint adapter)

        Returns:
            SharePointSourceConfig: Validated configuration object
        """
        if included_extensions is None:
            included_extensions = []

        config_params = {
            "client_id": resolve_env_var(credentials.get("client_id", "")),
            "client_secret": resolve_env_var(credentials.get("client_secret", "")),
            "tenant_id": resolve_env_var(credentials.get("tenant_id", "")),
            "document_library_id": resolve_env_var(connection_params.get("document_library_id", "")),
            "folder_path": resolve_env_var(connection_params.get("folder_path")),
            "recursive": connection_params.get("recursive", True),
            "file_extensions": included_extensions,
            "max_file_size_mb": connection_params.get("max_file_size_mb"),
        }

        if "graph_api_version" in connection_params:
            config_params["graph_api_version"] = connection_params["graph_api_version"]

        return SharePointSourceConfig(**config_params)
