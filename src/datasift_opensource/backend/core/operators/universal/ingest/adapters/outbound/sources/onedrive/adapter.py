"""OneDrive source adapter using Microsoft Graph API."""

import os
from datetime import datetime
from typing import AsyncGenerator

from core.operators.universal.ingest.adapters.outbound.sources.factories.source_factory import (
    register_source_adapter,
)
from core.operators.universal.ingest.adapters.outbound.sources.onedrive.config import OneDriveSourceConfig
from core.operators.universal.ingest.domain.models import Document
from core.operators.universal.ingest.ports.outbound.document_source import DocumentSourcePort

# Import the MicrosoftGraphLoader from ingest_source.py
from core.operators.universal.ingest.ingest_source import MicrosoftGraphLoader


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

                # Convert page_content (string) to bytes
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


async def main():
    """
    Test the OneDrive adapter with sample configuration.

    Usage:
        python -m src.datasift_opensource.backend.core.operators.universal.ingest.adapters.outbound.sources.onedrive.adapter

    Requirements:
        1. Create Azure AD App Registration
        2. Set environment variables:
           - ONEDRIVE_CLIENT_ID
           - ONEDRIVE_CLIENT_SECRET
           - ONEDRIVE_TENANT_ID
           - ONEDRIVE_DRIVE_ID (optional)
        3. Run this script to test connection and fetch documents
    """
    import sys

    print("=" * 80)
    print("OneDrive Adapter Test")
    print("=" * 80)

    # Get configuration from environment
    client_id = os.getenv("ONEDRIVE_CLIENT_ID")
    client_secret = os.getenv("ONEDRIVE_CLIENT_SECRET")
    tenant_id = os.getenv("ONEDRIVE_TENANT_ID")
    drive_id = os.getenv("ONEDRIVE_DRIVE_ID")
    folder_path = os.getenv("ONEDRIVE_FOLDER_PATH", "/Documents")

    if not all([client_id, client_secret, tenant_id]):
        print("\nERROR: Required environment variables not set")
        print("\nUsage:")
        print("  export ONEDRIVE_CLIENT_ID='your-client-id'")
        print("  export ONEDRIVE_CLIENT_SECRET='your-client-secret'")
        print("  export ONEDRIVE_TENANT_ID='your-tenant-id'")
        print("  export ONEDRIVE_DRIVE_ID='your-drive-id'  # Optional")
        print("  export ONEDRIVE_FOLDER_PATH='/Documents'  # Optional")
        print(
            "  python -m src.datasift_opensource.backend.core.operators.universal.ingest.adapters.outbound.sources.onedrive.adapter"
        )
        sys.exit(1)

    # Create configuration
    try:
        config = OneDriveSourceConfig(
            client_id=client_id,
            client_secret=client_secret,
            tenant_id=tenant_id,
            drive_id=drive_id,
            folder_path=folder_path,
            recursive=True,
            file_extensions=[".pdf", ".txt", ".docx", ".xlsx"],
        )
        print("\nConfiguration:")
        print(f"  Client ID: {config.client_id[:8]}...")
        print(f"  Tenant ID: {config.tenant_id[:8]}...")
        print(f"  Drive ID: {config.drive_id or 'Default'}")
        print(f"  Folder Path: {config.folder_path or 'Root'}")
        print(f"  Recursive: {config.recursive}")
        print(f"  File Extensions: {config.file_extensions}")
    except Exception as e:
        print(f"\nERROR: Failed to create configuration: {e}")
        sys.exit(1)

    # Create adapter
    adapter = OneDriveSourceAdapter()

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