"""Test script for OneDrive adapter."""

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

from docpipe.core.operators.ingest.adapters.outbound.sources.onedrive.adapter import (
    OneDriveSourceAdapter,
)
from docpipe.core.operators.ingest.adapters.outbound.sources.onedrive.config import (
    OneDriveSourceConfig,
)


async def main():
    """
    Test the OneDrive adapter with sample configuration.

    Usage:
        python connectors/test_onedrive_adapter.py

    Requirements:
        1. Create Azure AD App Registration
        2. Set environment variables:
           - ONEDRIVE_CLIENT_ID
           - ONEDRIVE_CLIENT_SECRET
           - ONEDRIVE_TENANT_ID
           - ONEDRIVE_DRIVE_ID (optional)
        3. Run this script to test connection and fetch documents
    """
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
        print("\nERROR: Required credentials not provided")
        print("\nOption 1 - Create connectors/.env file:")
        print("  1. Copy connectors/.env.example to connectors/.env")
        print("  2. Fill in your OneDrive credentials")
        print("  3. Run: python connectors/test_onedrive_adapter.py")
        print("\nOption 2 - Set environment variables:")
        print("  export ONEDRIVE_CLIENT_ID='your-client-id'")
        print("  export ONEDRIVE_CLIENT_SECRET='your-client-secret'")
        print("  export ONEDRIVE_TENANT_ID='your-tenant-id'")
        print("  export ONEDRIVE_DRIVE_ID='your-drive-id'  # Optional")
        print("  export ONEDRIVE_FOLDER_PATH='/Documents'  # Optional")
        print("  python connectors/test_onedrive_adapter.py")
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
    asyncio.run(main())
