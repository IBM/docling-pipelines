#!/usr/bin/env python3
"""
Example: Document Set Operator

This example demonstrates how to use the DocumentSetOperator to store
processed documents with their metadata in a structured format using
hexagonal architecture.

The example shows:
1. Creating a document set with metadata
2. Storing PyArrow table data
3. Querying stored documents
4. Previewing data
5. Getting statistics

Requirements:
- DuckDB (installed via docpipe dependencies)
- PyArrow (installed via docpipe dependencies)
"""

import sys
from pathlib import Path
from typing import Any

import pyarrow as pa

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.operators.document_sets.document_set_operator import DocumentSetOperator
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger(__name__)


def create_sample_data() -> pa.Table:
    """Create sample document data as PyArrow table.

    Returns:
        PyArrow table with sample document data
    """
    return pa.table(
        {
            OperatorConstants.Columns.ID: ["doc_001", "doc_002", "doc_003"],
            "content": [
                "This is the first sample document about machine learning.",
                "Second document discusses natural language processing.",
                "Third document covers computer vision applications.",
            ],
            "source_path": ["/data/ml_doc.txt", "/data/nlp_doc.txt", "/data/cv_doc.txt"],
            "size": [100, 150, 200],
            "pages_processed": [1, 2, 3],
            OperatorConstants.Metadata.METADATA: [
                '{"category": "ML", "author": "Alice"}',
                '{"category": "NLP", "author": "Bob"}',
                '{"category": "CV", "author": "Charlie"}',
            ],
        }
    )


def main() -> int:
    """Main example function.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    print("=" * 80)
    print("DOCUMENT SET OPERATOR EXAMPLE")
    print("=" * 80)

    # Configuration
    database_path = "data/example_documents.db"
    document_set_name = "example_document_collection"

    # Ensure data directory exists
    Path("data").mkdir(exist_ok=True)

    # Step 1: Create DocumentSetOperator
    print("\nStep 1: Creating DocumentSetOperator")
    print("-" * 80)

    config: dict[str, Any] = {
        OperatorConstants.DocumentSet.DOCUMENT_SET_NAME: document_set_name,
        OperatorConstants.Config.DESCRIPTION: "Example document collection for demonstration",
        OperatorConstants.DocumentSet.DATABASE_PATH: database_path,
        OperatorConstants.DocumentSet.METADATA_BACKEND: "duckdb",
        OperatorConstants.DocumentSet.DATA_BACKEND: "duckdb",
    }

    try:
        operator = DocumentSetOperator(config=config)
        print(f"✓ Created document set operator: {document_set_name}")
    except Exception as e:
        print(f"✗ Failed to create operator: {e}")
        return 1

    # Step 2: Create sample data
    print("\nStep 2: Creating sample document data")
    print("-" * 80)

    sample_data = create_sample_data()
    print(f"✓ Created {len(sample_data)} sample documents")
    print(f"  Columns: {sample_data.column_names}")

    # Step 3: Store data using operator
    print("\nStep 3: Storing documents in document set")
    print("-" * 80)

    try:
        result_tables, metadata = operator.transform(table=sample_data)
        result = result_tables[0]
        print(f"✓ Stored {len(result)} documents successfully")
        print(f"  Metadata keys: {list(metadata.keys())}")
        print(f"  Stored documents: {metadata.get(OperatorConstants.DocumentSet.META_STORED_DOCUMENTS, 0)}")
        print(f"  Total size: {metadata.get(OperatorConstants.DocumentSet.META_TOTAL_SIZE_BYTES, 0)} bytes")
        print(f"  Total pages: {metadata.get(OperatorConstants.DocumentSet.META_TOTAL_PAGES, 0)}")
    except Exception as e:
        print(f"✗ Failed to store data: {e}")
        return 1

    # Step 4: Query stored documents
    print("\nStep 4: Querying stored documents")
    print("-" * 80)

    try:
        doc_set = operator.service.get_document_set_by_name(name=document_set_name)
        print("✓ Retrieved document set")
        print(f"  ID: {doc_set.id}")
        print(f"  Name: {doc_set.name}")
        print(f"  Description: {doc_set.description}")
        print(f"  Table Name: {doc_set.table_name}")
        print(f"  Total Documents: {doc_set.total_documents}")
        print(f"  Total Size: {doc_set.total_size_bytes} bytes")
        print(f"  Total Pages: {doc_set.total_pages}")
    except Exception as e:
        print(f"✗ Failed to query document set: {e}")
        return 1

    # Step 5: Preview data
    print("\nStep 5: Previewing stored data")
    print("-" * 80)

    try:
        preview_data = operator.service.preview_data(document_set_id=doc_set.id or "", limit=2)
        print("✓ Preview (first 2 rows):")
        print(f"  Columns: {preview_data.column_names}")
        print(f"  Row count: {len(preview_data)}")

        if len(preview_data) > 0:
            print("\n  Sample row 1:")
            print(f"    ID: {preview_data[OperatorConstants.Columns.ID][0].as_py()}")
            print(f"    Content: {preview_data['content'][0].as_py()[:50]}...")
    except Exception as e:
        print(f"✗ Failed to preview data: {e}")
        return 1

    # Step 6: List all document sets
    print("\nStep 6: Listing all document sets")
    print("-" * 80)

    try:
        all_sets = operator.service.list_document_sets()
        print(f"✓ Total document sets: {len(all_sets)}")
        for ds in all_sets:
            print(f"  - {ds.name} (ID: {ds.id})")
            print(f"    Documents: {ds.total_documents}, Size: {ds.total_size_bytes} bytes")
    except Exception as e:
        print(f"✗ Failed to list document sets: {e}")
        return 1

    # Summary
    print("\n" + "=" * 80)
    print("EXAMPLE COMPLETED SUCCESSFULLY")
    print("=" * 80)
    print(f"Database location: {database_path}")
    print(f"Document set name: {document_set_name}")
    print(f"Total documents stored: {doc_set.total_documents}")
    print("\nYou can inspect the database using DuckDB CLI:")
    print(f"  duckdb {database_path}")
    print(f"  SELECT * FROM {doc_set.table_name};")
    print("=" * 80)

    return 0


if __name__ == "__main__":
    sys.exit(main())
