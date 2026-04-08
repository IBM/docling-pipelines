"""OneDrive source adapter using Microsoft Graph API."""

import os
from datetime import datetime
from typing import AsyncGenerator

from core.operators.ingest.adapters.outbound.sources.factories.source_factory import (
    register_source_adapter,
)
from core.operators.ingest.adapters.outbound.sources.onedrive.config import OneDriveSourceConfig
from core.operators.ingest.domain.models import Document

# Import the MicrosoftGraphLoader from ingest_source.py
from core.operators.ingest.ingest_source import MicrosoftGraphLoader
from core.operators.ingest.ports.outbound.document_source import DocumentSourcePort


@register_source_adapter
class OneDriveSourceAdapter(DocumentSourcePort):
    """
    Adapter for ingesting documents from OneDrive using Microsoft Graph API.

    This adapter uses the custom MicrosoftGraphLoader which supports
    app-only authentication (client credentials flow) for OneDrive access.

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
      - Files.Read.All (Application permission)
    """

    # Metadata for connector discovery
    SOURCE_NAME = "onedrive"
    SOURCE_DISPLAY_NAME = "Microsoft OneDrive"
    SOURCE_DESCRIPTION = "Ingest documents from OneDrive using Microsoft Graph API"
    SOURCE_VERSION = "1.0.0"

    async def fetch_documents(self, config: OneDriveSourceConfig) -> AsyncGenerator[Document, None]:
        """
        Fetch documents from OneDrive using Microsoft Graph API.

        Args:
            config: Validated OneDrive configuration

        Yields:
            Document: Domain documents from OneDrive

        Raises:
            ImportError: If required dependencies (msal, requests) are not installed
            ValueError: If authentication fails or folder not found
        """
        try:
            # Create MicrosoftGraphLoader with configuration
            loader = MicrosoftGraphLoader(
                drive_id=config.drive_id,
                client_id=config.client_id,
                client_secret=config.client_secret,
                tenant_id=config.tenant_id,
                folder_path=config.folder_path,
                recursive=config.recursive,
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
                if config.file_extensions:
                    file_ext = os.path.splitext(doc_name)[1].lower()
                    if file_ext not in config.file_extensions:
                        continue

                # Apply file size filter if specified
                if config.max_file_size_mb:
                    file_size_mb = len(content) / (1024 * 1024)
                    if file_size_mb > config.max_file_size_mb:
                        continue

                # Parse modified time if available
                modified_time = None
                if metadata.get("modified_time"):
                    try:
                        # Microsoft Graph returns ISO 8601 format
                        modified_time = datetime.fromisoformat(
                            metadata["modified_time"].replace("Z", "+00:00")
                        )
                    except (ValueError, AttributeError):
                        pass

                # Build source URL
                source_url = metadata.get("web_url", f"https://onedrive.live.com/?cid={doc_id}")

                # Create domain document
                document = Document(
                    id=doc_id,
                    name=doc_name,
                    content=content,
                    source_url=source_url,
                    modified_time=modified_time,
                    metadata={
                        "drive_id": config.drive_id,
                        "file_size": metadata.get("size", len(content)),
                        "mime_type": metadata.get("mime_type"),
                        "created_time": metadata.get("created_time"),
                        "web_url": metadata.get("web_url"),
                    },
                )

                yield document

        except ImportError as e:
            raise ImportError(
                "Microsoft Graph dependencies not installed. "
                "Install with: pip install msal requests"
            ) from e
        except Exception as e:
            raise ValueError(f"Failed to fetch documents from OneDrive: {e!s}") from e

    async def test_connection(self, config: OneDriveSourceConfig) -> tuple[bool, str]:
        """
        Test OneDrive connection using Microsoft Graph API.

        Args:
            config: Validated OneDrive configuration

        Returns:
            Tuple[bool, str]: (success, message)
        """
        try:
            # Create loader to test authentication
            loader = MicrosoftGraphLoader(
                drive_id=config.drive_id,
                client_id=config.client_id,
                client_secret=config.client_secret,
                tenant_id=config.tenant_id,
                folder_path=config.folder_path,
                recursive=False,  # Don't recurse for connection test
            )

            # Try to get access token (this will fail if credentials are invalid)
            token = loader._get_token()

            if not token:
                return False, "Failed to acquire access token"

            # Try to list files (this will fail if drive_id or folder_path is invalid)
            files = list(loader.lazy_load())

            return True, f"Successfully connected to OneDrive. Found {len(files)} document(s)."

        except ImportError:
            return False, "Microsoft Graph dependencies not installed (msal, requests)"
        except ValueError as e:
            return False, f"Configuration error: {e!s}"
        except Exception as e:
            return False, f"Connection test failed: {e!s}"

    def get_config_schema(self) -> type[OneDriveSourceConfig]:
        """
        Get the configuration schema for this adapter.

        Returns:
            type[OneDriveSourceConfig]: The Pydantic configuration model
        """
        return OneDriveSourceConfig

    def build_config_from_operator_params(
        self,
        connection_params: dict,
        credentials: dict,
        included_extensions: list[str] | None = None,
    ) -> OneDriveSourceConfig:
        """
        Build OneDrive configuration from operator parameters.

        Args:
            connection_params: Connection parameters (drive_id, folder_path, etc.)
            credentials: Credentials (client_id, client_secret, tenant_id)
            included_extensions: File extensions to include (optional)

        Returns:
            OneDriveSourceConfig: Validated configuration object
        """
        return OneDriveSourceConfig(
            client_id=credentials.get("client_id", ""),
            client_secret=credentials.get("client_secret", ""),
            tenant_id=credentials.get("tenant_id", ""),
            drive_id=connection_params.get("drive_id"),
            folder_path=connection_params.get("folder_path"),
            recursive=connection_params.get("recursive", True),
            file_extensions=included_extensions,
        )
