"""
Example usage of the filesystem source adapter.

This demonstrates the hexagonal architecture in action:
1. Configuration is type-safe using Pydantic
2. The adapter implements the port interface
3. The factory handles registration and creation
4. Everything is testable and swappable
"""

import asyncio

from ..factories.source_factory import SourceAdapterFactory, register_source_adapter
from .adapter import FilesystemSourceAdapter
from .config import FilesystemSourceConfig


# Register the adapter (normally done at module import time)
@register_source_adapter
class RegisteredFilesystemAdapter(FilesystemSourceAdapter):
    """Registered version of filesystem adapter."""

    pass


async def example_basic_usage():
    """Example 1: Basic usage with direct instantiation."""
    print("=" * 80)
    print("Example 1: Basic Usage")
    print("=" * 80)

    # Create configuration (with validation)
    config = FilesystemSourceConfig(
        root_path="./tests/fixtures/customer_support_docs",
        recursive=True,
        file_extensions=[".txt", ".pdf"],
        max_file_size_mb=10,
    )

    # Create adapter instance
    adapter = FilesystemSourceAdapter()

    # Test connection
    success, message = await adapter.test_connection(config)
    print(f"\nConnection test: {message}")

    if success:
        # Fetch documents
        print("\nFetching documents...")
        doc_count = 0
        async for document in adapter.fetch_documents(config):
            doc_count += 1
            print(f"  [{doc_count}] {document.name} ({document.size} bytes)")
            print(f"      Source: {document.source_url}")
            print(f"      Modified: {document.modified_time}")

        print(f"\nTotal documents fetched: {doc_count}")


async def example_factory_usage():
    """Example 2: Using the factory pattern."""
    print("\n" + "=" * 80)
    print("Example 2: Factory Pattern Usage")
    print("=" * 80)

    # List all available sources
    print("\nAvailable source adapters:")
    for source in SourceAdapterFactory.list_sources():
        print(f"  - {source['name']}: {source['display_name']}")
        print(f"    {source['description']}")
        print(f"    Version: {source['version']}")

    # Create adapter by name
    print("\nCreating adapter using factory...")
    adapter = SourceAdapterFactory.create("filesystem")
    print(f"Created: {adapter.__class__.__name__}")

    # Get configuration schema
    config_schema = adapter.get_config_schema()
    print(f"\nConfiguration schema: {config_schema.__name__}")
    print(f"Required fields: {list(config_schema.model_fields.keys())}")


async def example_error_handling():
    """Example 3: Error handling and validation."""
    print("\n" + "=" * 80)
    print("Example 3: Error Handling")
    print("=" * 80)

    # Try invalid configuration
    print("\nTrying invalid configuration (non-existent path)...")
    try:
        config = FilesystemSourceConfig(root_path="/non/existent/path", recursive=True)
    except ValueError as e:
        print(f"  ✓ Validation caught error: {e}")

    # Try invalid file extension
    print("\nTrying invalid file extension format...")
    config = FilesystemSourceConfig(
        root_path="./tests/fixtures",
        file_extensions=["txt", "pdf"],  # Missing dots
    )
    print(f"  ✓ Auto-corrected extensions: {config.file_extensions}")


async def example_metadata():
    """Example 4: Adapter metadata."""
    print("\n" + "=" * 80)
    print("Example 4: Adapter Metadata")
    print("=" * 80)

    adapter = FilesystemSourceAdapter()
    metadata = adapter.get_metadata()

    print("\nAdapter metadata:")
    for key, value in metadata.items():
        if key != "config_schema":  # Skip schema for brevity
            print(f"  {key}: {value}")


async def main():
    """Run all examples."""
    print("\n" + "=" * 80)
    print("FILESYSTEM SOURCE ADAPTER - EXAMPLE USAGE")
    print("=" * 80)

    await example_basic_usage()
    await example_factory_usage()
    await example_error_handling()
    await example_metadata()

    print("\n" + "=" * 80)
    print("Examples completed!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
