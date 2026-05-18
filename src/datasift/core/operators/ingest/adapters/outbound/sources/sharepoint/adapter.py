"""SharePoint source adapter using Microsoft Graph API."""

import os
from datetime import datetime
from typing import AsyncGenerator, cast

from pydantic import BaseModel

from datasift.core.operators.ingest.adapters.outbound.sources.factories.source_factory import (
    register_source_adapter,
)
from datasift.core.operators.ingest.adapters.outbound.sources.sharepoint.config import SharePointSourceConfig
from datasift.core.operators.ingest.domain.models import Document

# Import the MicrosoftGraphLoader from ingest_source.py
from datasift.core.operators.ingest.ingest_source import MicrosoftGraphLoader
from datasift.core.operators.ingest.ports.outbound.document_source import DocumentSourcePort
from datasift.core.operators.operator_utils import resolve_env_var


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

    async def fetch_documents(self, config: BaseModel) -> AsyncGenerator[Document, None]:  # type: ignore[override]
        """
        Fetch documents from SharePoint using Microsoft Graph API.

        Args:
            config: Validated SharePoint configuration (SharePointSourceConfig)

        Yields:
            Document: Domain documents from SharePoint

        Raises:
            ImportError: If required dependencies (msal, requests) are not installed
            ValueError: If authentication fails or document library not found
        """
        sharepoint_config: SharePointSourceConfig = cast(SharePointSourceConfig, config)
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

            # Load documents (synchronous operation)
            # Note: MicrosoftGraphLoader.lazy_load() returns an iterator
            langchain_docs = loader.lazy_load()

            # Convert LangChain documents to domain documents
            for lc_doc in langchain_docs:
                # Extract metadata
                metadata = lc_doc.metadata
                doc_id = metadata.get("id", "")
                doc_name = metadata.get("source", "unknown")

                # Get binary content - prefer _binary_content attribute if available
                if hasattr(lc_doc, "_binary_content") and lc_doc._binary_content is not None:
                    content = lc_doc._binary_content
                else:
                    # Fallback: Convert page_content (string) to bytes
                    content = lc_doc.page_content.encode("utf-8")

                # Apply file extension filter if specified
                if sharepoint_config.file_extensions:
                    file_ext = os.path.splitext(doc_name)[1].lower()
                    if file_ext not in sharepoint_config.file_extensions:
                        continue

                # Apply file size filter if specified
                if sharepoint_config.max_file_size_mb:
                    file_size_mb = len(content) / (1024 * 1024)
                    if file_size_mb > sharepoint_config.max_file_size_mb:
                        continue

                # Parse modified time if available
                modified_time = None
                if metadata.get("modified_time"):
                    try:
                        # Microsoft Graph returns ISO 8601 format
                        modified_time = datetime.fromisoformat(metadata["modified_time"].replace("Z", "+00:00"))
                    except (ValueError, AttributeError):
                        pass

                # Build source URL
                source_url = metadata.get("web_url", f"https://sharepoint.com/?id={doc_id}")

                # Create domain document
                document = Document(
                    id=doc_id,
                    name=doc_name,
                    content=content,
                    source_url=source_url,
                    modified_time=modified_time,
                    metadata={
                        "document_library_id": sharepoint_config.document_library_id,
                        "file_size": metadata.get("size", len(content)),
                        "mime_type": metadata.get("mime_type"),
                        "created_time": metadata.get("created_time"),
                        "web_url": metadata.get("web_url"),
                    },
                )

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
            "folder_path": connection_params.get("folder_path"),
            "recursive": connection_params.get("recursive", True),
            "file_extensions": included_extensions,
            "max_file_size_mb": connection_params.get("max_file_size_mb"),
        }

        if "graph_api_version" in connection_params:
            config_params["graph_api_version"] = connection_params["graph_api_version"]

        return SharePointSourceConfig(**config_params)
