"""SharePoint source adapter using Microsoft Graph API."""

from datetime import datetime
from pathlib import Path
from typing import Any, AsyncGenerator, cast

from pydantic import BaseModel

from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.operators.ingest.adapters.outbound.sources.factories.source_factory import (
    register_source_adapter,
)
from docpipe.core.operators.ingest.adapters.outbound.sources.sharepoint.config import SharePointSourceConfig
from docpipe.core.operators.ingest.domain.models import Document

# Import the MicrosoftGraphLoader from ingest_source.py
from docpipe.core.operators.ingest.ingest_source import MicrosoftGraphLoader
from docpipe.core.operators.ingest.ingest_utils import (
    extract_msgraph_file_id_from_url,
    handle_msgraph_resolution_result,
    resolve_msgraph_file_id_to_item_id,
)
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
      - Word documents (.docx)
      - Excel spreadsheets (.xlsx)
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

    def _resolve_sharepoint_item_id(
        self,
        *,
        file_path: str,
        document_library_id: str,
        loader: "MicrosoftGraphLoader",
        token: str,
    ) -> tuple[str | None, str]:
        """Resolve a file path or URL to an (item_id, actual_drive_id) pair for SharePoint."""
        if not file_path.startswith("http"):
            logger.info("Using direct file path as item ID: %s", file_path)
            return file_path, document_library_id

        file_id = extract_msgraph_file_id_from_url(file_path)
        if not file_id:
            raise ValueError(f"Could not extract file ID from URL: {file_path}")
        logger.info("Extracted file ID from URL: %s", file_id)
        item_id, actual_drive_id = resolve_msgraph_file_id_to_item_id(
            file_id=file_id,
            drive_id=document_library_id,
            rest_client=loader._rest_client,
            token=token,
            original_url=file_path,
            strip_path_prefixes=["Shared Documents/", "Documents/", "Shared%20Documents/"],
        )
        return handle_msgraph_resolution_result(
            file_id=file_id,
            item_id=item_id,
            actual_drive_id=actual_drive_id,
            fallback_drive_id=document_library_id,
            allow_guid_fallback=True,
            original_url=file_path,
        )

    def _build_sharepoint_document(
        self,
        *,
        item: dict,
        document_library_id: str,
        config: "SharePointSourceConfig",
        is_single_file: bool = False,
    ) -> Document:
        """Build a lazy-loading Document from a Graph API item dict for SharePoint."""
        doc_id = item.get(OperatorConstants.Columns.ID, "")
        doc_name = item.get(OperatorConstants.Columns.NAME, "unknown")
        file_size = item.get("size", 0)
        source_url = item.get("webUrl", f"https://sharepoint.com/?{OperatorConstants.Columns.ID}={doc_id}")
        extension = Path(doc_name).suffix.lower()

        modified_time = None
        last_modified = item.get("lastModifiedDateTime")
        if last_modified:
            try:
                modified_time = datetime.fromisoformat(last_modified.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass

        metadata: dict = {
            "document_library_id": document_library_id,
            "item_id": doc_id,
            "file_size": file_size,
            "mime_type": item.get("file", {}).get("mimeType"),
            "created_time": item.get("createdDateTime"),
            "web_url": source_url,
            OperatorConstants.Config.PROVIDER: "sharepoint",
            "client_id": config.client_id,
            "client_secret": config.client_secret,
            "tenant_id": config.tenant_id,
        }
        if not is_single_file:
            metadata[OperatorConstants.Columns.SOURCE_ID] = doc_id  # Required by binary_content_fetcher

        return Document(
            id=doc_id,
            name=doc_name,
            content=b"",
            source_url=source_url,
            modified_time=modified_time,
            mimetype=item.get("file", {}).get("mimeType", "application/octet-stream"),
            size=file_size,
            extension=extension,
            metadata=metadata,
        )

    @staticmethod
    def _should_skip_sharepoint_item(*, doc_name: str, file_size: int, config: "SharePointSourceConfig") -> bool:
        """Return True if the item should be filtered out based on extension or size."""
        if config.file_extensions and Path(doc_name).suffix.lower() not in config.file_extensions:
            return True
        if config.max_file_size_mb and file_size / (1024 * 1024) > config.max_file_size_mb:
            return True
        return False

    @staticmethod
    def _resolve_sharepoint_folder_item_id(
        *, loader: "MicrosoftGraphLoader", document_library_id: str, folder_path: str, headers: dict
    ) -> str | None:
        """Look up the item ID for a folder path in a SharePoint document library."""
        path = folder_path.strip("/")
        try:
            data = loader._rest_client.call_rest_json(
                method=RestMethod.GET,
                url=f"/drives/{document_library_id}/root:/{path}",
                headers=headers,
            )
            return data.get(OperatorConstants.Columns.ID)
        except Exception as e:
            raise ValueError(
                f"Folder path '{folder_path}' not found in document library '{document_library_id}': {e!s}"
            ) from e

    async def fetch_documents(self, config: SharePointSourceConfig) -> AsyncGenerator[Document, None]:  # type: ignore[override]
        """
        Fetch document metadata from SharePoint using Microsoft Graph API.

        This method implements lazy loading - it only fetches metadata, not binary content.
        Binary content is fetched on-demand by the Extract operator via fetch_binary_content().
        """
        sharepoint_config: SharePointSourceConfig = config
        try:
            loader = MicrosoftGraphLoader(
                drive_id=sharepoint_config.document_library_id,
                client_id=sharepoint_config.client_id,
                client_secret=sharepoint_config.client_secret,
                tenant_id=sharepoint_config.tenant_id,
                folder_path=sharepoint_config.folder_path,
                recursive=sharepoint_config.recursive,
            )

            if config.file_path:
                token = loader._get_token()
                item_id, actual_drive_id = self._resolve_sharepoint_item_id(
                    file_path=config.file_path,
                    document_library_id=config.document_library_id,
                    loader=loader,
                    token=token,
                )
                headers = {"Authorization": f"Bearer {token}"}
                item = loader._rest_client.call_rest_json(
                    method=RestMethod.GET,
                    url=f"/drives/{actual_drive_id}/items/{item_id}",
                    headers=headers,
                )
                yield self._build_sharepoint_document(
                    item=item,
                    document_library_id=actual_drive_id,
                    config=sharepoint_config,
                    is_single_file=True,
                )
                return

            # Folder mode
            token = loader._get_token()
            headers = {"Authorization": f"Bearer {token}"}

            folder_item_id = None
            if sharepoint_config.folder_path:
                folder_item_id = self._resolve_sharepoint_folder_item_id(
                    loader=loader,
                    document_library_id=sharepoint_config.document_library_id,
                    folder_path=sharepoint_config.folder_path,
                    headers=headers,
                )

            for item in loader._list_files(folder_item_id=folder_item_id):
                doc_name = item.get(OperatorConstants.Columns.NAME, "unknown")
                file_size = item.get("size", 0)
                if self._should_skip_sharepoint_item(doc_name=doc_name, file_size=file_size, config=sharepoint_config):
                    continue
                document = self._build_sharepoint_document(
                    item=item,
                    document_library_id=sharepoint_config.document_library_id,
                    config=sharepoint_config,
                )
                logger.debug("Created document metadata for SharePoint file: %s (%s bytes)", doc_name, file_size)
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
                url=endpoint,
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
                    url=download_url,
                )
                content = response.content
            else:
                # Fallback: use content endpoint
                content_endpoint = f"/drives/{document_library_id}/items/{item_id}/content"
                response = loader._rest_client.call_rest(
                    method=RestMethod.GET,
                    url=content_endpoint,
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

        if "file_path" in connection_params:
            config_params["file_path"] = connection_params["file_path"]

        if "graph_api_version" in connection_params:
            config_params["graph_api_version"] = connection_params["graph_api_version"]

        return SharePointSourceConfig(**config_params)
