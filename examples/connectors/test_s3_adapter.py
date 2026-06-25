"""Test script for S3 source adapter."""

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

from docpipe.core.operators.ingest.adapters.outbound.sources.s3.adapter import S3SourceAdapter
from docpipe.core.operators.ingest.adapters.outbound.sources.s3.config import S3SourceConfig


async def main():
    """
    Test the S3 adapter with sample configuration.

    Usage:
        python examples/connectors/test_s3_adapter.py

    Requirements:
        1. AWS credentials or S3-compatible storage credentials
        2. Set environment variables:
           - S3_ACCESS_KEY
           - S3_SECRET_KEY
           - S3_BUCKET
           - S3_PREFIX (optional)
           - S3_ENDPOINT_URL (optional, for S3-compatible storage)
           - S3_REGION (optional)
        3. Run this script to test connection and fetch documents
    """
    print("=" * 80)
    print("S3 Adapter Test")
    print("=" * 80)

    # Get configuration from environment
    access_key = os.getenv("S3_ACCESS_KEY")
    secret_key = os.getenv("S3_SECRET_KEY")
    bucket = os.getenv("S3_BUCKET")
    prefix = os.getenv("S3_PREFIX", "")
    endpoint_url = os.getenv("S3_ENDPOINT_URL")
    region = os.getenv("S3_REGION")

    if not all([access_key, secret_key, bucket]):
        print("\nERROR: Required credentials not provided")
        print("\nOption 1 - Create examples/connectors/.env file:")
        print("  1. Copy examples/connectors/.env.example to examples/connectors/.env")
        print("  2. Fill in your S3 credentials")
        print("  3. Run: python examples/connectors/test_s3_adapter.py")
        print("\nOption 2 - Set environment variables:")
        print("  export S3_ACCESS_KEY='your-access-key'")
        print("  export S3_SECRET_KEY='your-secret-key'")
        print("  export S3_BUCKET='your-bucket-name'")
        print("  export S3_PREFIX='documents/'  # Optional")
        print("  export S3_ENDPOINT_URL='https://s3.example.com'  # Optional, for S3-compatible storage")
        print("  export S3_REGION='us-east-1'  # Optional")
        print("  python examples/connectors/test_s3_adapter.py")
        sys.exit(1)

    # Create configuration
    try:
        config = S3SourceConfig(
            access_key=access_key,
            secret_key=secret_key,
            bucket=bucket,
            prefix=prefix,
            endpoint_url=endpoint_url,
            region=region,
            recursive=True,
            file_extensions=[".pdf", ".txt", ".docx", ".xlsx"],
            skip_hidden_files=True,
            skip_empty_files=True,
            max_file_size_mb=100,
        )
        print("\nConfiguration:")
        print(f"  Access Key: {config.access_key[:8]}...")
        print(f"  Bucket: {config.bucket}")
        print(f"  Prefix: {config.prefix or '(root)'}")
        print(f"  Endpoint URL: {config.endpoint_url or '(AWS S3)'}")
        print(f"  Region: {config.region or '(default)'}")
        print(f"  Recursive: {config.recursive}")
        print(f"  File Extensions: {config.file_extensions}")
        print(f"  Skip Hidden Files: {config.skip_hidden_files}")
        print(
            f"  Max File Size: {config.max_file_size_mb} MB" if config.max_file_size_mb else "  Max File Size: No limit"
        )
    except Exception as e:
        print(f"\nERROR: Failed to create configuration: {e}")
        sys.exit(1)

    # Create adapter
    adapter = S3SourceAdapter()

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
        import traceback

        traceback.print_exc()
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
                print(f"    Bucket: {document.metadata.get('bucket', 'N/A')}")
                print(f"    Key: {document.metadata.get('key', 'N/A')}")
                print(f"    Content Type: {document.metadata.get('content_type', 'N/A')}")
                print(f"    Storage Class: {document.metadata.get('storage_class', 'N/A')}")

            # Limit output for large buckets
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
