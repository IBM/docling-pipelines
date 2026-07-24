#!/usr/bin/env python3
"""
OpenSearch Integration Example
Demonstrates end-to-end usage of the OpenSearch operator with real data.
Uses environment variables from .env file for configuration.
"""

import sys
from pathlib import Path

import numpy as np
import pyarrow as pa

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "docpipe"))

from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.operators.vectordb import VectorDBOperator
from docpipe.utils.infrastructure.config import get_opensearch_config

# Check if .env file exists
env_file = Path(__file__).parent.parent / ".env"
if not env_file.exists():
    print("⚠️  .env file not found!")
    print("This example requires OpenSearch configuration in a .env file.")
    print(f"Please create {env_file} based on .env.example")
    print("\nSkipping example execution.")
    sys.exit(0)


def create_sample_documents(num_docs=10, vector_dim=384):
    """Create sample documents with embeddings"""
    doc_ids = [f"doc_{i}" for i in range(num_docs)]
    contents = [f"This is sample document number {i} with some content." for i in range(num_docs)]
    embeddings = [np.random.rand(vector_dim).tolist() for _ in range(num_docs)]

    return pa.table(
        {
            "doc_id_hash": doc_ids,
            "content": contents,
            "embeddings": embeddings,
            "metadata": [f"metadata_{i}" for i in range(num_docs)],
        }
    )


def example_1_basic_indexing():
    """Example 1: Basic document indexing with FAISS engine"""
    print("\n" + "=" * 80)
    print("Example 1: Basic Document Indexing")
    print("=" * 80)

    # Get base config from environment variables
    config = get_opensearch_config()

    # Override with example-specific settings
    config.update(
        {
            "index_name": "docpipe_example_basic",
            "available_features": {
                "doc_id_hash": {
                    "name": "Document ID",
                    "available_for_vector_db": True,
                    "mandatory_for_vector_db": True,
                    "type": "string",
                    "is_primary": True,
                },
                "content": {
                    "name": "Content",
                    "available_for_vector_db": True,
                    "type": "string",
                },
                "embeddings": {
                    "name": "Embeddings",
                    "available_for_vector_db": True,
                    "mandatory_for_vector_db": True,
                    "type": "vector",
                },
                "metadata": {
                    "name": "Metadata",
                    "available_for_vector_db": True,
                    "type": "string",
                },
            },
            "feature_mappings": {
                "doc_id_hash": "id",
                "content": "text",
                "embeddings": "vector",
                "metadata": "meta",
            },
        }
    )

    # Create sample data
    print("\n1. Creating sample documents...")
    table = create_sample_documents(num_docs=10)
    print(f"   Created {table.num_rows} documents")

    # Initialize operator
    print("\n2. Initializing OpenSearch operator...")
    operator = VectorDBOperator(config)
    print("   Operator initialized successfully")

    # Index documents
    print("\n3. Indexing documents...")
    _result_tables, metadata = operator.transform(table)

    print("\n4. Indexing Results:")
    print(f"   Total documents: {metadata['total_docs_count']}")
    print(f"   Processed: {metadata['processed_docs']}")
    print(f"   Failed: {metadata['failed_docs_count']}")
    print(f"   Skipped: {metadata['skipped_docs_count']}")
    print(f"   Batches: {metadata.get('number_of_batches', 0)}")

    # Get document count
    print("\n5. Verifying index...")
    count = operator.get_document_count()
    print(f"   Total documents in index: {count}")

    return operator


def example_2_lucene_engine():
    """Example 2: Using Lucene engine with cosine similarity"""
    print("\n" + "=" * 80)
    print("Example 2: Lucene Engine with Cosine Similarity")
    print("=" * 80)

    # Get base config from environment variables
    config = get_opensearch_config()

    # Override with example-specific settings
    config.update(
        {
            "index_name": "docpipe_example_lucene",
            "batch_size": 50,
            OperatorConstants.Config.PROVIDER_CONFIG: {
                OperatorConstants.VectorDB.ENGINE: "lucene",
                OperatorConstants.VectorDB.SPACE_TYPE: "cosine",
                OperatorConstants.VectorDB.ENGINE_PARAMETERS: {
                    "ef_construction": 256,
                    "m": 32,
                },
            },
            "available_features": {
                "doc_id_hash": {
                    "available_for_vector_db": True,
                    "mandatory_for_vector_db": True,
                    "type": "string",
                    "is_primary": True,
                },
                "content": {"available_for_vector_db": True, "type": "string"},
                "embeddings": {
                    "available_for_vector_db": True,
                    "mandatory_for_vector_db": True,
                    "type": "vector",
                },
            },
            "feature_mappings": {
                "doc_id_hash": "id",
                "content": "text",
                "embeddings": "vector",
            },
        }
    )

    print("\n1. Creating sample documents...")
    table = create_sample_documents(num_docs=20)

    print("\n2. Initializing OpenSearch operator with Lucene engine...")
    operator = VectorDBOperator(config)
    provider_config = config.get(OperatorConstants.Config.PROVIDER_CONFIG, {})
    print(f"   Engine: {provider_config.get(OperatorConstants.VectorDB.ENGINE, 'N/A')}")
    print(f"   Algorithm: {provider_config.get(OperatorConstants.VectorDB.ALGORITHM, 'N/A')}")
    print(f"   Space Type: {provider_config.get(OperatorConstants.VectorDB.SPACE_TYPE, 'N/A')}")
    print(f"   Custom Parameters: {provider_config.get(OperatorConstants.VectorDB.ENGINE_PARAMETERS, {})}")

    print("\n3. Indexing documents...")
    _result_tables, metadata = operator.transform(table)

    print("\n4. Results:")
    print(f"   Processed: {metadata['processed_docs']}/{metadata['total_docs_count']}")
    print(f"   Batches: {metadata.get('number_of_batches', 0)}")

    return operator


def example_3_query_operations(operator):
    """Example 3: Query and delete operations"""
    print("\n" + "=" * 80)
    print("Example 3: Query and Delete Operations")
    print("=" * 80)

    # Query documents
    print("\n1. Querying documents by names...")
    doc_names = ["doc_0", "doc_1", "doc_2"]
    docs = operator.query_by_doc_names(doc_names, fields=["content", "metadata"])
    print(f"   Found {len(docs)} documents")
    for doc in docs[:3]:
        print(f"   - {doc.get('name', 'N/A')}: {doc.get('content', 'N/A')[:50]}...")

    # Get document count
    print("\n2. Getting document count...")
    count_before = operator.get_document_count()
    print(f"   Documents before deletion: {count_before}")

    # Delete documents
    print("\n3. Deleting documents...")
    doc_ids_to_delete = ["doc_0", "doc_1"]
    success, failed = operator.delete_documents_by_ids(doc_ids_to_delete)
    print(f"   Deleted: {success}, Failed: {failed}")

    # Verify deletion
    print("\n4. Verifying deletion...")
    count_after = operator.get_document_count()
    print(f"   Documents after deletion: {count_after}")
    print(f"   Difference: {count_before - count_after}")


def example_4_batch_processing():
    """Example 4: Large batch processing"""
    print("\n" + "=" * 80)
    print("Example 4: Large Batch Processing")
    print("=" * 80)

    # Get base config from environment variables
    config = get_opensearch_config()

    # Override with example-specific settings
    config.update(
        {
            "index_name": "docpipe_example_batch",
            "batch_size": 50,  # Smaller batch size for demonstration
            "available_features": {
                "doc_id_hash": {
                    "available_for_vector_db": True,
                    "mandatory_for_vector_db": True,
                    "type": "string",
                    "is_primary": True,
                },
                "content": {"available_for_vector_db": True, "type": "string"},
                "embeddings": {
                    "available_for_vector_db": True,
                    "mandatory_for_vector_db": True,
                    "type": "vector",
                },
            },
            "feature_mappings": {
                "doc_id_hash": "id",
                "content": "text",
                "embeddings": "vector",
            },
        }
    )

    print("\n1. Creating large dataset...")
    table = create_sample_documents(num_docs=150)
    print(f"   Created {table.num_rows} documents")

    print("\n2. Initializing operator with batch size 50...")
    operator = VectorDBOperator(config)

    print("\n3. Processing in batches...")
    _result_tables, metadata = operator.transform(table)

    print("\n4. Batch Processing Results:")
    print(f"   Total documents: {metadata['total_docs_count']}")
    print(f"   Processed: {metadata['processed_docs']}")
    print(f"   Number of batches: {metadata.get('number_of_batches', 0)}")
    print(f"   Average batch size: {metadata['processed_docs'] / max(metadata.get('number_of_batches', 1), 1):.1f}")

    return operator


def example_5_error_handling():
    """Example 5: Error handling and recovery"""
    print("\n" + "=" * 80)
    print("Example 5: Error Handling")
    print("=" * 80)

    # Get base config from environment variables
    config = get_opensearch_config()

    # Override with example-specific settings
    config.update(
        {
            "index_name": "docpipe_example_errors",
            "available_features": {
                "doc_id_hash": {
                    "available_for_vector_db": True,
                    "mandatory_for_vector_db": True,
                    "type": "string",
                    "is_primary": True,
                },
                "embeddings": {
                    "available_for_vector_db": True,
                    "mandatory_for_vector_db": True,
                    "type": "vector",
                },
            },
            "feature_mappings": {"doc_id_hash": "id", "embeddings": "vector"},
        }
    )

    # Create data with some missing doc IDs
    print("\n1. Creating data with missing doc IDs...")
    doc_ids = ["doc_1", None, "doc_3", None, "doc_5"]  # Some None values
    embeddings = [np.random.rand(384).tolist() for _ in range(5)]

    table = pa.table({"doc_id_hash": doc_ids, "embeddings": embeddings})

    print("\n2. Processing documents with errors...")
    operator = VectorDBOperator(config)
    _result_tables, metadata = operator.transform(table)

    print("\n3. Error Handling Results:")
    print(f"   Total documents: {metadata['total_docs_count']}")
    print(f"   Processed: {metadata['processed_docs']}")
    print(f"   Skipped: {metadata['skipped_docs_count']}")
    print(f"   Failed: {metadata['failed_docs_count']}")

    if metadata["skipped_docs"]:
        print("\n4. Skipped Documents:")
        for doc in metadata["skipped_docs"][:5]:
            print(f"   - {doc['name']}: {doc['reason']}")


def main():
    """Run all examples"""
    print("\n" + "=" * 80)
    print("OpenSearch Operator Integration Examples")
    print("=" * 80)
    print("\nThese examples demonstrate the OpenSearch operator capabilities:")
    print("1. Basic document indexing")
    print("2. Different engines and algorithms")
    print("3. Query and delete operations")
    print("4. Batch processing")
    print("5. Error handling")

    try:
        # Example 1: Basic indexing
        operator1 = example_1_basic_indexing()

        # Example 2: Lucene engine
        _operator2 = example_2_lucene_engine()

        # Example 3: Query operations (using operator from example 1)
        example_3_query_operations(operator1)

        # Example 4: Batch processing
        _operator4 = example_4_batch_processing()

        # Example 5: Error handling
        example_5_error_handling()

        print("\n" + "=" * 80)
        print("All examples completed successfully!")
        print("=" * 80)

    except Exception as e:
        print(f"\n❌ Error running examples: {e!s}")
        import traceback

        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
