#!/usr/bin/env python3
"""
LiteLLM Embeddings Example

This example demonstrates how to use the LiteLLM adapter for generating embeddings
with various providers (OpenAI, Azure, Cohere, etc.).

Prerequisites:
    1. Install dependencies: uv sync
    2. Set API key environment variable (e.g., export OPENAI_API_KEY=sk-...)
    3. Run from project root: python examples/embeddings_litellm_example.py

For detailed documentation, see:
    src/docpipe_app/backend/core/operators/functional/embeddings/adapters/outbound/README_LITELLM.md
"""

import os
import sys
from pathlib import Path

import pyarrow as pa

from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.operators.functional.embeddings.embeddings_operator import EmbeddingsOperator

# Add backend to path
backend_path = Path(__file__).parent.parent / "src" / "docpipe_app" / "backend"
sys.path.insert(0, str(backend_path))


def example_openai():
    """Example using OpenAI embeddings."""
    print("\n" + "=" * 60)
    print("Example 1: OpenAI Embeddings")
    print("=" * 60)

    # Check if API key is set
    if not os.getenv("OPENAI_API_KEY"):
        print("OPENAI_API_KEY not set. Skipping OpenAI example.")
        print("To run this example:")
        print("  export OPENAI_API_KEY=sk-proj-your-key-here")
        return

    try:
        # Initialize operator with LiteLLM provider
        config = {
            OperatorConstants.Config.PROVIDER: OperatorConstants.Config.PROVIDER_LITELLM,
            OperatorConstants.Config.PROVIDER_CONFIG: {
                OperatorConstants.Config.MODEL_ID: "openai/text-embedding-3-small",
                OperatorConstants.Config.BATCH_SIZE: 32,
            },
        }
        operator = EmbeddingsOperator(config=config)

        # Create sample data
        table = pa.table(
            {
                "text": [
                    "LiteLLM provides a unified interface to 100+ LLM providers",
                    "OpenAI's text-embedding-3-small model is cost-effective",
                    "Embeddings are useful for semantic search and RAG",
                ],
                "doc_id": ["doc1", "doc2", "doc3"],
            }
        )

        print(f"\nInput: {len(table)} documents")
        print("Model: text-embedding-3-small")
        print("Provider: OpenAI (via LiteLLM)")

        # Generate embeddings
        result_tables, _metadata = operator.transform(table)
        result = result_tables[0]

        print(f"\nOutput: {len(result)} embeddings generated")
        print(f"Embedding dimension: {len(result[OperatorConstants.Columns.EMBEDDINGS][0].as_py())}")
        print(f"First embedding (first 5 values): {result[OperatorConstants.Columns.EMBEDDINGS][0].as_py()[:5]}")

        print("\nSuccess! OpenAI embeddings generated via LiteLLM.")

    except Exception as e:
        print(f"\nError: {e}")
        print("\nTroubleshooting:")
        print("1. Verify OPENAI_API_KEY is set correctly")
        print("2. Check your OpenAI account has credits")
        print("3. Verify network connectivity")


def example_azure():
    """Example using Azure OpenAI embeddings."""
    print("\n" + "=" * 60)
    print("Example 2: Azure OpenAI Embeddings")
    print("=" * 60)

    # Check if Azure credentials are set
    if not all(
        [
            os.getenv("AZURE_API_KEY"),
            os.getenv("AZURE_API_BASE"),
        ]
    ):
        print("Azure credentials not set. Skipping Azure example.")
        print("To run this example:")
        print("  export AZURE_API_KEY=your-azure-key")
        print("  export AZURE_API_BASE=https://your-resource.openai.azure.com")
        print("  export AZURE_API_VERSION=2023-05-15")
        return

    try:
        # Initialize operator with Azure deployment
        config = {
            OperatorConstants.Config.PROVIDER: OperatorConstants.Config.PROVIDER_LITELLM,
            OperatorConstants.Config.PROVIDER_CONFIG: {
                OperatorConstants.Config.MODEL_ID: "azure/your-deployment-name",  # Replace with your deployment
                OperatorConstants.Config.BATCH_SIZE: 32,
            },
        }
        operator = EmbeddingsOperator(config=config)

        # Create sample data
        table = pa.table(
            {
                "text": ["Azure OpenAI provides enterprise-grade AI services"],
                "doc_id": ["doc1"],
            }
        )

        print(f"\nInput: {len(table)} documents")
        print("Model: azure/your-deployment-name")
        print("Provider: Azure OpenAI (via LiteLLM)")

        # Generate embeddings
        result_tables, _metadata = operator.transform(table)
        result = result_tables[0]

        print(f"\nOutput: {len(result)} embeddings generated")
        print(f"Embedding dimension: {len(result[OperatorConstants.Columns.EMBEDDINGS][0].as_py())}")

        print("\nSuccess! Azure OpenAI embeddings generated via LiteLLM.")

    except Exception as e:
        print(f"\nError: {e}")
        print("\nNote: Replace 'your-deployment-name' with your actual Azure deployment name")


def example_cohere():
    """Example using Cohere embeddings."""
    print("\n" + "=" * 60)
    print("Example 3: Cohere Embeddings")
    print("=" * 60)

    # Check if API key is set
    if not os.getenv("COHERE_API_KEY"):
        print("COHERE_API_KEY not set. Skipping Cohere example.")
        print("To run this example:")
        print("  export COHERE_API_KEY=your-cohere-key")
        return

    try:
        # Initialize operator with Cohere model
        config = {
            OperatorConstants.Config.PROVIDER: OperatorConstants.Config.PROVIDER_LITELLM,
            OperatorConstants.Config.PROVIDER_CONFIG: {
                OperatorConstants.Config.MODEL_ID: "cohere/embed-english-v3.0",
                OperatorConstants.Config.BATCH_SIZE: 32,
            },
        }
        operator = EmbeddingsOperator(config=config)

        # Create sample data
        table = pa.table(
            {
                "text": [
                    "Cohere provides powerful embedding models",
                    "embed-english-v3.0 is optimized for English text",
                ],
                "doc_id": ["doc1", "doc2"],
            }
        )

        print(f"\nInput: {len(table)} documents")
        print("Model: embed-english-v3.0")
        print("Provider: Cohere (via LiteLLM)")

        # Generate embeddings
        result_tables, _metadata = operator.transform(table)
        result = result_tables[0]

        print(f"\nOutput: {len(result)} embeddings generated")
        print(f"Embedding dimension: {len(result[OperatorConstants.Columns.EMBEDDINGS][0].as_py())}")

        print("\nSuccess! Cohere embeddings generated via LiteLLM.")

    except Exception as e:
        print(f"\nError: {e}")


def example_error_handling():
    """Example demonstrating error handling."""
    print("\n" + "=" * 60)
    print("Example 4: Error Handling")
    print("=" * 60)

    print("\nDemonstrating error handling with invalid configuration...")

    try:
        # Try to initialize with missing API key
        config = {
            OperatorConstants.Config.PROVIDER: OperatorConstants.Config.PROVIDER_LITELLM,
            OperatorConstants.Config.PROVIDER_CONFIG: {
                OperatorConstants.Config.MODEL_ID: "openai/text-embedding-3-small",
                OperatorConstants.Config.BATCH_SIZE: 32,
            },
        }
        operator = EmbeddingsOperator(config=config)

        # This will fail if OPENAI_API_KEY is not set
        table = pa.table({"text": ["test"], "doc_id": ["doc1"]})

        _result_tables, _metadata = operator.transform(table)
        print("Embeddings generated successfully")

    except Exception as e:
        print(f"\nExpected error caught: {type(e).__name__}")
        print(f"Error message: {str(e)[:200]}...")
        print("\nThe adapter includes automatic retry logic:")
        print("- 3 retry attempts")
        print("- Exponential backoff (1s, 2s, 4s)")
        print("- Handles rate limiting and temporary failures")


def example_custom_endpoint():
    """Example using custom API endpoint."""
    print("\n" + "=" * 60)
    print("Example 5: Custom API Endpoint")
    print("=" * 60)

    print("\nDemonstrating custom API endpoint configuration...")

    try:
        # Initialize with custom endpoint
        config = {
            OperatorConstants.Config.PROVIDER: OperatorConstants.Config.PROVIDER_LITELLM,
            OperatorConstants.Config.PROVIDER_CONFIG: {
                OperatorConstants.Config.MODEL_ID: "openai/text-embedding-3-small",
                OperatorConstants.LLM.API_BASE: "https://custom-endpoint.com/v1",  # Custom endpoint
                OperatorConstants.Config.BATCH_SIZE: 32,
            },
        }
        _operator = EmbeddingsOperator(config=config)

        print("Operator initialized with custom endpoint")
        print("API Base: https://custom-endpoint.com/v1")
        print("\nNote: This example won't actually run without a valid custom endpoint")

    except Exception as e:
        print(f"Configuration created (would fail on actual API call): {e}")


def main():
    """Run all examples."""
    print("\n" + "=" * 60)
    print("LiteLLM Embeddings Examples")
    print("=" * 60)
    print("\nThese examples demonstrate using LiteLLM adapter with various providers.")
    print("LiteLLM provides a unified interface to 100+ embedding providers.")
    print("\nFor detailed documentation, see:")
    print("  src/docpipe_app/backend/core/operators/functional/embeddings/adapters/outbound/README_LITELLM.md")

    # Run examples
    example_openai()
    example_azure()
    example_cohere()
    example_error_handling()
    example_custom_endpoint()

    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print("\nLiteLLM Adapter Features:")
    print("- Unified interface to 100+ providers")
    print("- Automatic provider detection from model name")
    print("- Environment variable support for API keys")
    print("- Automatic retry logic with exponential backoff")
    print("- Custom endpoint support")
    print("- Comprehensive error handling")

    print("\nSupported Providers:")
    print("- OpenAI (text-embedding-3-small, text-embedding-3-large)")
    print("- Azure OpenAI (azure/deployment-name)")
    print("- Cohere (embed-english-v3.0, embed-multilingual-v3.0)")
    print("- AWS Bedrock (bedrock/amazon.titan-embed-text-v1)")
    print("- Google Vertex AI (vertex_ai/textembedding-gecko@001)")
    print("- And 100+ more...")

    print("\nNext Steps:")
    print("1. Set your API key: export OPENAI_API_KEY=sk-...")
    print("2. Run this script: python examples/embeddings_litellm_example.py")
    print("3. Check the detailed documentation for more providers")
    print("4. Integrate into your data pipeline")


if __name__ == "__main__":
    main()
