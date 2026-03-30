"""SharePoint source adapter using Microsoft Graph API."""

import os
from datetime import datetime
from typing import AsyncGenerator

from core.operators.ingest.adapters.outbound.sources.factories.source_factory import (
    register_source_adapter,
)
from core.operators.ingest.adapters.outbound.sources.sharepoint.config import SharePointSourceConfig
from core.operators.ingest.domain.models import Document
from core.operators.ingest.ports.outbound.document_source import DocumentSourcePort

# Import the MicrosoftGraphLoader from ingest_source.py
from core.operators.ingest.ingest_source import MicrosoftGraphLoader


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

    async def fetch_documents(self, config: SharePointSourceConfig) -> AsyncGenerator[Document, None]:
        """
        Fetch documents from SharePoint using Microsoft Graph API.

        Args:
            config: Validated SharePoint configuration

        Yields:
            Document: Domain documents from SharePoint

        Raises:
            ImportError: If required dependencies (msal, requests) are not installed
            ValueError: If authentication fails or document library not found
        """
        try:
            # Create MicrosoftGraphLoader with configuration
            # Note: SharePoint uses document_library_id which is the drive_id in Graph API
            loader = MicrosoftGraphLoader(
                drive_id=config.document_library_id,
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
                source_url = metadata.get("web_url", f"https://sharepoint.com/?id={doc_id}")

                # Create domain document
                document = Document(
                    id=doc_id,
                    name=doc_name,
                    content=content,
                    source_url=source_url,
                    modified_time=modified_time,
                    metadata={
                        "document_library_id": config.document_library_id,
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
            raise ValueError(f"Failed to fetch documents from SharePoint: {e!s}") from e

    async def test_connection(self, config: SharePointSourceConfig) -> tuple[bool, str]:
        """
        Test SharePoint connection using Microsoft Graph API.

        Args:
            config: Validated SharePoint configuration

        Returns:
            Tuple[bool, str]: (success, message)
        """
        try:
            # Create loader to test authentication
            loader = MicrosoftGraphLoader(
                drive_id=config.document_library_id,
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

            # Try to list files (this will fail if document_library_id or folder_path is invalid)
            files = list(loader.lazy_load())

            return True, f"Successfully connected to SharePoint. Found {len(files)} document(s)."

        except ImportError:
            return False, "Microsoft Graph dependencies not installed (msal, requests)"
        except ValueError as e:
            return False, f"Configuration error: {e!s}"
        except Exception as e:
            return False, f"Connection test failed: {e!s}"

    def get_config_schema(self) -> type[SharePointSourceConfig]:
        """
        Get the configuration schema for this adapter.

        Returns:
            type[SharePointSourceConfig]: The Pydantic configuration model
        """
        return SharePointSourceConfig
    def build_config_from_operator_params(
        self,
        connection_params: dict,
        credentials: dict,
        included_extensions: list[str] | None = None,
    ) -> SharePointSourceConfig:
        """
        Build SharePoint configuration from operator parameters.

        Args:
            connection_params: Connection parameters (document_library_id, folder_path, etc.)
            credentials: Credentials (client_id, client_secret, tenant_id)
            included_extensions: File extensions to include (optional)

        Returns:
            SharePointSourceConfig: Validated configuration object
        """
        return SharePointSourceConfig(
            client_id=credentials.get("client_id", ""),
            client_secret=credentials.get("client_secret", ""),
            tenant_id=credentials.get("tenant_id", ""),
            document_library_id=connection_params.get("document_library_id", ""),
            folder_path=connection_params.get("folder_path"),
            recursive=connection_params.get("recursive", True),
            file_extensions=included_extensions,
        )


async def main():
    """
    Test the SharePoint adapter with sample configuration.

    Usage:
        python -m src.datasift_opensource.backend.core.operators.universal.ingest.adapters.outbound.sources.sharepoint.adapter

    Requirements:
        1. Create Azure AD App Registration
        2. Set environment variables:
           - SHAREPOINT_CLIENT_ID
           - SHAREPOINT_CLIENT_SECRET
           - SHAREPOINT_TENANT_ID
           - SHAREPOINT_DOCUMENT_LIBRARY_ID
        3. Run this script to test connection and fetch documents
    """
    import sys

    print("=" * 80)
    print("SharePoint Adapter Test")
    print("=" * 80)

    # Get configuration from environment
    client_id = os.getenv("SHAREPOINT_CLIENT_ID")
    client_secret = os.getenv("SHAREPOINT_CLIENT_SECRET")
    tenant_id = os.getenv("SHAREPOINT_TENANT_ID")
    document_library_id = os.getenv("SHAREPOINT_DOCUMENT_LIBRARY_ID")
    folder_path = os.getenv("SHAREPOINT_FOLDER_PATH", "/Shared Documents")

    if not all([client_id, client_secret, tenant_id, document_library_id]):
        print("\nERROR: Required environment variables not set")
        print("\nUsage:")
        print("  export SHAREPOINT_CLIENT_ID='your-client-id'")
        print("  export SHAREPOINT_CLIENT_SECRET='your-client-secret'")
        print("  export SHAREPOINT_TENANT_ID='your-tenant-id'")
        print("  export SHAREPOINT_DOCUMENT_LIBRARY_ID='your-document-library-id'")
        print("  export SHAREPOINT_FOLDER_PATH='/Shared Documents'  # Optional")
        print(
            "  python -m src.datasift_opensource.backend.core.operators.universal.ingest.adapters.outbound.sources.sharepoint.adapter"
        )
        sys.exit(1)

    # Create configuration
    try:
        config = SharePointSourceConfig(
            client_id=client_id,
            client_secret=client_secret,
            tenant_id=tenant_id,
            document_library_id=document_library_id,
            folder_path=folder_path,
            recursive=True,
            file_extensions=[".pdf", ".txt", ".docx", ".xlsx"],
        )
        print("\nConfiguration:")
        print(f"  Client ID: {config.client_id[:8]}...")
        print(f"  Tenant ID: {config.tenant_id[:8]}...")
        print(f"  Document Library ID: {config.document_library_id[:8]}...")
        print(f"  Folder Path: {config.folder_path or 'Root'}")
        print(f"  Recursive: {config.recursive}")
        print(f"  File Extensions: {config.file_extensions}")
    except Exception as e:
        print(f"\nERROR: Failed to create configuration: {e}")
        sys.exit(1)

    # Create adapter
    adapter = SharePointSourceAdapter()

    # Test 1: Connection test
    print("\n" + "=" * 80)
    print("Test 1: Connection Test")
    print("=" * 80)

    try:
        success, message = await adapter.test_connection(config)
        if success:
            print(f"✓ SUCCESS: {message}")
        else:
            print(f"✗ FAILED: {message}")
            sys.exit(1)
    except Exception as e:
        print(f"✗ EXCEPTION: {e}")
        sys.exit(1)

    # Test 2: Fetch documents
    print("\n" + "=" * 80)
    print("Test 2: Fetch Documents")
    print("=" * 80)

    try:
        doc_count = 0
        total_size = 0

        print("\nFetching documents...")
        async for document in adapter.fetch_documents(config):
            doc_count += 1
            doc_size = len(document.content)
            total_size += doc_size

            print(f"\n  Document {doc_count}:")
            print(f"    ID: {document.id}")
            print(f"    Name: {document.name}")
            print(f"    Size: {doc_size:,} bytes")
            print(f"    URL: {document.source_url}")
            if document.modified_time:
                print(f"    Modified: {document.modified_time}")
            if document.metadata:
                print(f"    MIME Type: {document.metadata.get('mime_type', 'N/A')}")

            # Limit output for large folders
            if doc_count >= 10:
                print("\n  ... (showing first 10 documents)")
                break

        print("\n" + "-" * 80)
        print(f"✓ SUCCESS: Fetched {doc_count} document(s)")
        print(f"  Total Size: {total_size:,} bytes ({total_size / 1024 / 1024:.2f} MB)")

    except Exception as e:
        print(f"\n✗ EXCEPTION: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

    print("\n" + "=" * 80)
    print("All tests passed!")
    print("=" * 80)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())

# Made with Bob
