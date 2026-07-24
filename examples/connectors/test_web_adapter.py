"""Test script for Web Page source adapter."""

import asyncio
import logging
import os
import sys
from pathlib import Path

from docpipe.core.operators.ingest.adapters.outbound.sources.web.adapter import (
    WebPageSourceAdapter,
    WebPageSourceConfig,
)

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

# Add the backend directory to Python path
backend_path = Path(__file__).parent.parent.parent / "src" / "docpipe_app" / "backend"
sys.path.insert(0, str(backend_path))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


async def test_web_adapter():
    """Test the Web Page source adapter with single URL."""
    # Get configuration from environment
    urls_str = os.getenv("WEB_TEST_URLS", "https://example.com,https://www.iana.org/domains/reserved")
    urls = [url.strip() for url in urls_str.split(",")]
    max_depth = int(os.getenv("WEB_TEST_MAX_DEPTH", "1"))
    timeout = int(os.getenv("WEB_TEST_TIMEOUT", "30"))

    # Initialize adapter
    adapter = WebPageSourceAdapter()

    # Test configuration with single URL (use first URL from list)
    config = WebPageSourceConfig(
        urls=[urls[0]],
        max_depth=max_depth,
        exclude_patterns=[],
        timeout=timeout,
    )

    logger.info("Testing Web Page adapter with single URL...")
    logger.info(f"Configuration: {config}")

    # Test connection
    logger.info("\n=== Testing Connection ===")
    success, message = await adapter.test_connection(config=config)
    logger.info(f"Connection test: {'✓ Success' if success else '✗ Failed'}")
    logger.info(f"Message: {message}")

    if not success:
        logger.error("Connection test failed. Exiting.")
        return

    # Fetch documents
    logger.info("\n=== Fetching Documents ===")
    doc_count = 0
    async for document in adapter.fetch_documents(config=config):
        doc_count += 1
        logger.info(f"\nDocument {doc_count}:")
        logger.info(f"  ID: {document.id}")
        logger.info(f"  Name: {document.name}")
        logger.info(f"  Source URL: {document.source_url}")
        logger.info(f"  Content size: {len(document.content)} bytes")
        logger.info(f"  Metadata: {document.metadata}")

        # Limit output for testing
        if doc_count >= 3:
            logger.info("\n(Limiting output to first 3 documents)")
            break

    logger.info("\n=== Summary ===")
    logger.info(f"Total documents fetched: {doc_count}")


async def test_multiple_urls():
    """Test the Web Page source adapter with multiple URLs."""
    # Get configuration from environment
    urls_str = os.getenv("WEB_TEST_URLS", "https://example.com,https://www.iana.org/domains/reserved")
    urls = [url.strip() for url in urls_str.split(",")]
    max_depth = int(os.getenv("WEB_TEST_MAX_DEPTH", "1"))
    timeout = int(os.getenv("WEB_TEST_TIMEOUT", "30"))

    # Initialize adapter
    adapter = WebPageSourceAdapter()

    # Test configuration with multiple URLs
    config = WebPageSourceConfig(
        urls=urls,
        max_depth=max_depth,
        exclude_patterns=[],
        timeout=timeout,
    )

    logger.info("\n=== Testing Multiple URLs ===")
    logger.info(f"Configuration: {config}")

    # Test connection
    logger.info("\n=== Testing Connection for Multiple URLs ===")
    success, message = await adapter.test_connection(config=config)
    logger.info(f"Connection test: {'✓ Success' if success else '✗ Failed'}")
    logger.info(f"Message:\n{message}")

    if not success:
        logger.error("Connection test failed. Exiting.")
        return

    # Fetch documents
    logger.info("\n=== Fetching Documents from Multiple URLs ===")
    doc_count = 0
    url_counts = {}

    async for document in adapter.fetch_documents(config=config):
        doc_count += 1
        source_url = document.source_url

        # Track documents per URL
        base_url = source_url.split("/")[2] if "/" in source_url else source_url
        url_counts[base_url] = url_counts.get(base_url, 0) + 1

        logger.info(f"\nDocument {doc_count}:")
        logger.info(f"  ID: {document.id}")
        logger.info(f"  Name: {document.name}")
        logger.info(f"  Source URL: {document.source_url}")
        logger.info(f"  Content size: {len(document.content)} bytes")

        # Limit output for testing
        if doc_count >= 5:
            logger.info("\n(Limiting output to first 5 documents)")
            break

    logger.info("\n=== Summary ===")
    logger.info(f"Total documents fetched: {doc_count}")
    logger.info(f"Documents per URL: {url_counts}")


async def test_build_config():
    """Test building config from operator parameters."""
    # Get configuration from environment
    urls_str = os.getenv("WEB_TEST_URLS", "https://example.com,https://www.iana.org")
    urls = [url.strip() for url in urls_str.split(",")]
    max_depth = int(os.getenv("WEB_TEST_MAX_DEPTH", "2"))
    timeout = int(os.getenv("WEB_TEST_TIMEOUT", "60"))

    adapter = WebPageSourceAdapter()

    logger.info("\n=== Testing Config Builder ===")

    # Simulate operator parameters
    connection_params = {
        "urls": urls,
        "max_depth": max_depth,
        "exclude_patterns": ["/admin", "/login"],
        "timeout": timeout,
    }

    credentials = {}  # Web adapter doesn't use credentials

    # Build config
    config = adapter.build_config_from_operator_params(
        connection_params=connection_params,
        credentials=credentials,
        included_extensions=None,  # Not used for web
    )

    logger.info(f"Built config: {config}")
    logger.info(f"Config type: {type(config)}")

    # Verify config
    assert config.urls == urls
    assert config.max_depth == max_depth
    assert config.exclude_patterns == ["/admin", "/login"]
    assert config.timeout == timeout

    logger.info("✓ Config builder test passed")


async def test_metadata():
    """Test adapter metadata."""
    adapter = WebPageSourceAdapter()

    logger.info("\n=== Testing Adapter Metadata ===")

    metadata = adapter.get_metadata()
    logger.info(f"Adapter metadata: {metadata}")

    assert metadata["name"] == "web"
    assert metadata["display_name"] == "Web Pages"
    assert metadata["version"] == "1.0.0"

    logger.info("✓ Metadata test passed")


async def main():
    """Run all tests."""
    try:
        await test_metadata()
        await test_build_config()
        await test_web_adapter()
        await test_multiple_urls()
        logger.info("\n✓ All tests completed successfully!")
    except Exception as e:
        logger.error(f"\n✗ Test failed with error: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())
