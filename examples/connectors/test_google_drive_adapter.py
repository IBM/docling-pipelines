"""Test script for Google Drive adapter with service account authentication."""

import asyncio
import os
import sys
from pathlib import Path


def _load_environment() -> None:
    try:
        from dotenv import load_dotenv

        env_path = Path(__file__).parent / ".env"
        if env_path.exists():
            load_dotenv(env_path)
            print(f"Loaded environment variables from {env_path}")
    except ImportError:
        print("python-dotenv not installed. Install with: pip install python-dotenv")
        print("Or set environment variables manually.")


async def main():
    from docpipe.core.operators.ingest.adapters.outbound.sources.google_drive.adapter import (
        GoogleDriveSourceAdapter,
    )
    from docpipe.core.operators.ingest.adapters.outbound.sources.google_drive.config import (
        GoogleDriveSourceConfig,
    )

    _load_environment()
    """
    Test the Google Drive adapter with service account authentication.

    Usage:
        python examples/connectors/test_google_drive_adapter.py

    Requirements:
        1. Create Google Cloud service account
        2. Download service account JSON file
        3. Share Google Drive folder with service account email
        4. Set environment variables:
           - GOOGLE_DRIVE_SERVICE_ACCOUNT_PATH (path to service account JSON)
           - GOOGLE_DRIVE_FOLDER_ID (optional, folder to ingest from)
        5. Run this script
    """
    print("=" * 80)
    print("Google Drive Adapter Test (Service Account)")
    print("=" * 80)

    # Get configuration from environment
    service_account_json = os.getenv("GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON")
    folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
    recursive = os.getenv("GOOGLE_DRIVE_RECURSIVE", "true").lower() == "true"

    # Check if credentials are provided
    if not service_account_json:
        print("\nERROR: Service account JSON not provided")
        print("\nSetup Instructions:")
        print("  1. Go to https://console.cloud.google.com/")
        print("  2. Create a new project or select existing one")
        print("  3. Enable Google Drive API")
        print("  4. Create service account credentials")
        print("  5. Download service account JSON file")
        print("  6. Share Google Drive folder with service account email")
        print("\nSet environment variable with JSON content:")
        print("  1. Copy examples/connectors/.env.example to examples/connectors/.env")
        print('  2. Set GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON=\'{"type":"service_account",...}\'')
        print("  3. Set GOOGLE_DRIVE_FOLDER_ID=your-folder-id (optional)")
        print("  4. Run: python examples/connectors/test_google_drive_adapter.py")
        print("\nOr export directly:")
        print('  export GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON=\'{"type":"service_account",...}\'')
        print("  export GOOGLE_DRIVE_FOLDER_ID='your-folder-id'")
        print("  python examples/connectors/test_google_drive_adapter.py")
        print("\nTo get folder ID:")
        print("  1. Open folder in Google Drive web interface")
        print("  2. Copy ID from URL: https://drive.google.com/drive/folders/FOLDER_ID")
        print("\nIMPORTANT: Share the folder with your service account email!")
        print("  The service account email is in the JSON file (client_email field)")
        sys.exit(1)

    # Create configuration
    try:
        config = GoogleDriveSourceConfig(
            service_account_json=service_account_json,
            folder_id=folder_id,
            recursive=recursive,
            file_extensions=[".pdf", ".txt", ".docx", ".xlsx"],
        )
        print("\nConfiguration:")
        print("  Service Account: <from environment variable>")
        print(f"  Folder ID: {config.folder_id or 'Root (My Drive)'}")
        print(f"  Recursive: {config.recursive}")
        print(f"  File Extensions: {config.file_extensions}")
    except Exception as e:
        print(f"\nERROR: Failed to create configuration: {e}")
        sys.exit(1)

    # Create adapter
    adapter = GoogleDriveSourceAdapter()

    # Test 1: Connection test
    print("\n" + "=" * 80)
    print("Test 1: Connection Test")
    print("=" * 80)

    try:
        success, message = await adapter.test_connection(config)
        if success:
            print(f"\n✓ SUCCESS: {message}")
        else:
            print(f"\n✗ FAILED: {message}")
            print("\nTroubleshooting:")
            print("  1. Verify service account JSON file is valid")
            print("  2. Check that Google Drive API is enabled in your project")
            print("  3. Ensure folder is shared with service account email")
            print("  4. If using folder_id, verify it's correct")
            sys.exit(1)
    except Exception as e:
        print(f"\n✗ EXCEPTION: {e}")
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
                print(f"    MIME Type: {document.metadata.get('original_mime_type', 'N/A')}")
                print(f"    Drive ID: {document.metadata.get('drive_id', 'N/A')}")

            # Limit output for large folders
            if doc_count >= 10:
                print("\n  ... (showing first 10 documents)")
                break

        print("\n" + "-" * 80)
        if doc_count > 0:
            print(f"✓ SUCCESS: Fetched {doc_count} document(s)")
            print(f"  Total Size: {total_size:,} bytes ({total_size / 1024 / 1024:.2f} MB)")
        else:
            print("⚠ WARNING: No documents found")
            print("  - Check that folder_id is correct")
            print("  - Verify folder contains files matching file_extensions filter")
            print("  - Ensure service account has access to the folder")
            print("  - Try sharing the folder with the service account email")

    except Exception as e:
        print(f"\n✗ EXCEPTION: {e}")
        sys.exit(1)

    print("\n" + "=" * 80)
    print("All tests passed!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
