"""Test script for SharePoint adapter."""

import asyncio
import os
import sys
from pathlib import Path

# Load environment variables from .env file in connectors directory
try:
    from dotenv import load_dotenv

    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        print(f"Loaded environment variables from {env_path}")
except ImportError:
    print("python-dotenv not installed. Install with: pip install python-dotenv")
    print("Or set environment variables manually.")

from docpipe.core.operators.ingest.adapters.outbound.sources.sharepoint.adapter import (
    SharePointSourceAdapter,
)
from docpipe.core.operators.ingest.adapters.outbound.sources.sharepoint.config import (
    SharePointSourceConfig,
)


async def main():
    """
    Test the SharePoint adapter with sample configuration.

    Usage:
        python connectors/test_sharepoint_adapter.py

    Requirements:
        1. Create Azure AD App Registration
        2. Set environment variables:
           - SHAREPOINT_CLIENT_ID
           - SHAREPOINT_CLIENT_SECRET
           - SHAREPOINT_TENANT_ID
           - SHAREPOINT_DOCUMENT_LIBRARY_ID
        3. Run this script to test connection and fetch documents
    """
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
        print("\nERROR: Required credentials not provided")
        print("\nOption 1 - Create connectors/.env file:")
        print("  1. Copy connectors/.env.example to connectors/.env")
        print("  2. Fill in your SharePoint credentials")
        print("  3. Run: python connectors/test_sharepoint_adapter.py")
        print("\nOption 2 - Set environment variables:")
        print("  export SHAREPOINT_CLIENT_ID='your-client-id'")
        print("  export SHAREPOINT_CLIENT_SECRET='your-client-secret'")
        print("  export SHAREPOINT_TENANT_ID='your-tenant-id'")
        print("  export SHAREPOINT_DOCUMENT_LIBRARY_ID='your-document-library-id'")
        print("  export SHAREPOINT_FOLDER_PATH='/Shared Documents'  # Optional")
        print("  python connectors/test_sharepoint_adapter.py")
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
    asyncio.run(main())
