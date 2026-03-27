#!/usr/bin/env python3
"""
Example: Document Chunking

This example demonstrates different chunking strategies:
- Simple chunking: Basic token-based chunking
- Semantic chunking: Content-aware chunking
- Hybrid chunking: Combination of both approaches

The example shows a complete pipeline: Ingest → Extract → Chunk
"""

import json
import sys
from pathlib import Path
from typing import Any

import pyarrow as pa

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "datasift_opensource" / "backend"))

from core.operators.extract.extract_docling import ExtractDoclingOperator
from core.operators.functional.chunker import ChunkerOperator, ChunkType
from core.operators.ingest.ingest_local_folder import IngestLocalOperator


def main_hybrid(runtime: str = "python") -> None:  # pragma: no cover
    """
    Demonstrate hybrid chunking with a complete pipeline.
    
    Args:
        runtime: The runtime environment (default: "python")
    """
    print("=" * 80)
    print("HYBRID CHUNKING EXAMPLE")
    print("=" * 80)

    # 1. Ingest files
    ingest_operator: IngestLocalOperator = IngestLocalOperator(
        {
            "input_folder": "../../../tests/fixtures/customer_support_docs/",
            "include_filter": "pdf,txt",
            "force_ingest": True,
        }
    )

    input_table: pa.Table | None = None
    table_list, _ = ingest_operator.transform(input_table)
    table: pa.Table = table_list[0]
    print(f">>>>>>>>>>>>> Number of rows after ingest: {table.num_rows}")

    # 2. Extract text content from binary
    extract_operator: ExtractDoclingOperator = ExtractDoclingOperator(
        {
            "doc_column": "content",
        }
    )
    table_list, _ = extract_operator.transform(table)
    table = table_list[0]
    print(f">>>>>>>>>>>>> Number of rows after extraction: {table.num_rows}")

    # 3. Run chunking operator with hybrid chunking
    config: dict[str, Any] = {
        "chunk_type": ChunkType.HYBRID.value,  # Use hybrid chunking
        "chunk_size": 512,  # Token-based chunk size
        "docling_tokenizer": "sentence-transformers/all-MiniLM-L6-v2",  # Tokenizer for chunking
        "doc_column": "content",
        "retain_original_content": True,
        "enable_summarization": True,
    }
    print(f"\n>>>>>>>>>>>>> Testing HYBRID chunking with chunk_size: {config['chunk_size']} tokens")
    print(f">>>>>>>>>>>>> Tokenizer: {config['docling_tokenizer']}")

    operator: ChunkerOperator
    if runtime == "python":
        operator = ChunkerOperator(config=config)
    else:
        raise ValueError("unknown operator value")
    print(operator)

    metadata: dict[str, Any]
    table_list, metadata = operator.transform(table)
    table = table_list[0]
    print(table.schema)
    print(f">>>>>>>>>>>>> Number of rows after chunking: {table.num_rows}")

    # Calculate chunk statistics per document and overall
    print("\n>>>>>>>>>>>>> Per-Document Chunk Statistics:")
    total_chunks = 0
    all_chunk_sizes = []

    for row in table.to_pylist():
        doc_name = row.get("name", "Unknown")
        if row.get("chunked_content"):
            chunks = row["chunked_content"]
            num_chunks = len(chunks)
            total_chunks += num_chunks

            doc_chunk_sizes = []
            for chunk in chunks:
                if "chunk" in chunk:
                    size = len(chunk["chunk"])
                    doc_chunk_sizes.append(size)
                    all_chunk_sizes.append(size)

            if doc_chunk_sizes:
                avg_size = sum(doc_chunk_sizes) / len(doc_chunk_sizes)
                min_size = min(doc_chunk_sizes)
                max_size = max(doc_chunk_sizes)
                print(f"  {doc_name}:")
                print(f"    Chunks: {num_chunks}, Avg: {avg_size:.0f}, Min: {min_size}, Max: {max_size} chars")

    # Initialize statistics variables
    avg_chunk_size = 0.0
    min_chunk_size = 0
    max_chunk_size = 0

    if all_chunk_sizes:
        avg_chunk_size = sum(all_chunk_sizes) / len(all_chunk_sizes)
        min_chunk_size = min(all_chunk_sizes)
        max_chunk_size = max(all_chunk_sizes)
        print("\n>>>>>>>>>>>>> Overall Chunk Statistics:")
        print(f"  Total chunks created: {total_chunks}")
        print(f"  Average chunk size: {avg_chunk_size:.2f} characters")
        print(f"  Min chunk size: {min_chunk_size} characters")
        print(f"  Max chunk size: {max_chunk_size} characters")

    print(f"\n>>>>>>>>>>>>> Meta Data : - \n {json.dumps(metadata, indent=2)}")


def main(runtime: str = "python") -> None:  # pragma: no cover
    """
    Main entry point for the chunking example.
    
    Args:
        runtime: The runtime environment (default: "python")
    """
    # For simple chunking, use:
    #   main_simple()

    # For semantic chunking, use:
    # main_semantic(runtime)

    # For hybrid chunking, use:
    main_hybrid(runtime)


if __name__ == "__main__":  # pragma: no cover
    main()

# Made with Bob
