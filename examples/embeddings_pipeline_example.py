#!/usr/bin/env python3
"""
Example: Complete Embeddings Pipeline

This example demonstrates a complete pipeline: Ingest → Extract → Chunk → Embeddings

The script automatically handles Ollama setup:
- Checks if Ollama is installed
- Starts Ollama server if not running
- Pulls the specified model if not available

Usage:
    python embeddings_pipeline_example.py [OPTIONS]

Examples:
    # Use default PDF and model (auto-setup enabled)
    python embeddings_pipeline_example.py

    # Specify custom PDF
    python embeddings_pipeline_example.py --pdf tests/fixtures/invoices/TR-INV_001_3_2.1.pdf

    # Specify custom Ollama model
    python embeddings_pipeline_example.py --model mistral

    # Skip automatic setup
    python embeddings_pipeline_example.py --no-auto-setup

    # Disable automatic model pulling
    python embeddings_pipeline_example.py --no-auto-pull
"""

import argparse
import sys
from pathlib import Path
from typing import Any

import pyarrow as pa

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from docpipe.core.constants.constants import Metrics
from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.operators.functional.embeddings import EmbeddingsOperator
from docpipe.integrations.ollama.client import OllamaClient
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger()


def main() -> int:
    """Run the complete embeddings pipeline demo."""
    # Calculate project root directory dynamically
    project_root: Path = Path(__file__).resolve().parents[1]
    default_pdf_path: Path = project_root / "tests" / "fixtures" / "invoices"

    # Parse command line arguments
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Demo: Complete pipeline from PDF ingestion to embeddings generation"
    )
    parser.add_argument(
        "--pdf",
        type=str,
        default=str(default_pdf_path),
        help=f"Path to PDF file or directory (default: {default_pdf_path})",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="granite4",
        help="Ollama model to use for embeddings (default: granite4)",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=512,
        help="Chunk size in tokens (default: 512)",
    )
    parser.add_argument(
        "--no-auto-setup",
        action="store_true",
        help="Skip automatic Ollama setup (installation check, server start, model pull)",
    )
    parser.add_argument(
        "--no-auto-pull",
        action="store_true",
        help="Disable automatic model pulling (only check if model exists)",
    )
    args: argparse.Namespace = parser.parse_args()

    # ========================================================================
    # OLLAMA SETUP - Automatic setup if not disabled
    # ========================================================================
    if not args.no_auto_setup:
        print("=" * 80)
        print("OLLAMA SETUP CHECK")
        print("=" * 80)

        # Check Ollama readiness with auto-remediation
        print("\nChecking Ollama prerequisites...")
        auto_pull = not args.no_auto_pull
        success, message = OllamaClient.ensure_ready(model_name=args.model, auto_start=True, auto_pull=auto_pull)

        if not success:
            print(f"\n✗ {message}")
            print("\n" + "=" * 80)
            print("SETUP REQUIRED")
            print("=" * 80)
            print("Please follow the instructions above to set up Ollama.")
            print("=" * 80)
            return 1

        print(f"✓ {message}")
    else:
        # Manual setup mode - just check if everything is ready
        print("=" * 80)
        print("OLLAMA SETUP CHECK (Manual Mode)")
        print("=" * 80)

        # Check if Ollama package is available
        try:
            import ollama
        except ImportError:
            print("\n❌ Error: ollama package not installed")
            print("   Install it with: pip install ollama")
            return 1

        # Check if Ollama is running
        try:
            ollama.list()
            print("✓ Ollama is running")
        except Exception:
            print("\n❌ Error: Ollama is not running or not accessible")
            print("   Please start Ollama with: ollama serve")
            print(f"   Then pull a model with: ollama pull {args.model}")
            return 1

    # Import required operators
    try:
        from docpipe.core.operators.extract.extract_operator import ExtractOperator
        from docpipe.core.operators.functional.chunker import ChunkerOperator
        from docpipe.core.operators.ingest.ingest_local import IngestLocalOperator
    except ImportError as e:
        logger.error(f"Failed to import required operators: {e}")
        print("\nError: Failed to import operators. Make sure you are running from the repository root.")
        print('   Try: export PYTHONPATH="$(pwd)/src:${PYTHONPATH}"')
        return 1

    # Validate PDF path
    pdf_path: Path = Path(args.pdf)
    if not pdf_path.exists():
        print("\n" + "=" * 80)
        print("❌ ERROR: PDF PATH NOT FOUND")
        print("=" * 80)
        print(f"The specified path does not exist: {pdf_path}")
        print(f"Absolute path: {pdf_path.resolve()}")
        print(f"\nProject root: {project_root}")
        print(f"Expected test fixtures at: {default_pdf_path}")
        print("\nPlease ensure:")
        print("  1. The path exists")
        print("  2. You have the correct permissions")
        print("  3. The test fixtures are in the expected location")
        return 1

    # Count PDF files
    pdf_files: list[Path]
    pdf_count: int
    if pdf_path.is_dir():
        pdf_files = list(pdf_path.glob("*.pdf")) + list(pdf_path.glob("*.PDF"))
        pdf_count = len(pdf_files)
    else:
        pdf_count = 1 if pdf_path.suffix.lower() == ".pdf" else 0

    print("=" * 80)
    print("EMBEDDINGS PIPELINE DEMO")
    print("=" * 80)
    print(f"PDF Path: {args.pdf}")
    print(f"  Resolved: {pdf_path.resolve()}")
    print(f"  Type: {'Directory' if pdf_path.is_dir() else 'File'}")
    print(f"  PDF files found: {pdf_count}")
    print(f"Model: {args.model}")
    print(f"Chunk Size: {args.chunk_size}")
    print(f"Project Root: {project_root}")
    print("=" * 80)

    if pdf_count == 0:
        print("\n❌ WARNING: No PDF files found in the specified path")
        print("The pipeline will continue but may not find any documents to process.")

    # ========================================================================
    # STEP 1: INGEST - Load PDF files from local folder
    # ========================================================================
    print("\n" + "=" * 80)
    print("STEP 1: INGEST PDF FILES")
    print("=" * 80)

    # Handle both file and directory paths
    ingest_path: str
    include_filter: str
    if pdf_path.is_file():
        ingest_path = str(pdf_path.parent)
        include_filter = "pdf"
        print(f"  Ingesting single file: {pdf_path.name}")
        print(f"  From directory: {ingest_path}")
    else:
        ingest_path = args.pdf
        include_filter = "pdf"
        print(f"  Ingesting all PDFs from directory: {ingest_path}")

    ingest_config: dict[str, Any] = {
        "paths": ingest_path,
        "include_filter": include_filter,
        "max_files": 10,
        "force_ingest": True,
    }

    try:
        ingest_operator: Any = IngestLocalOperator(ingest_config)
        ingest_tables: list[pa.Table]
        ingest_metadata: dict[str, Any]
        ingest_tables, ingest_metadata = ingest_operator.transform(None)
        ingest_table: pa.Table = ingest_tables[0]

        # If a specific file was requested, filter to only that file
        if pdf_path.is_file() and ingest_table.num_rows > 0:
            target_path: str = str(pdf_path.resolve())
            if "name" in ingest_table.column_names:
                mask: list[bool] = [
                    str(Path(ingest_table["name"][i].as_py()).resolve()) == target_path
                    for i in range(ingest_table.num_rows)
                ]
                ingest_table = ingest_table.filter(pa.array(mask))
                print(f"  Filtered to target file: {pdf_path.name}")

        print(f"✓ Ingested {ingest_table.num_rows} document(s)")
        print(f"  Columns: {ingest_table.column_names}")
        print(
            f"  Metadata: Processed={ingest_metadata.get('processed_docs', 0)}, "
            f"Failed={ingest_metadata.get('failed_docs_count', 0)}"
        )

        if ingest_table.num_rows == 0:
            print(f"\n❌ No documents found in {args.pdf}")
            print(f"   Expected path: {pdf_path.resolve()}")
            if pdf_path.is_file():
                print("   Note: When passing a file, all PDFs in parent directory are scanned first")
            return 1

        if "name" in ingest_table.column_names:
            print(f"\n  Sample document: {ingest_table['name'][0].as_py()}")

    except Exception as e:
        print(f"\n❌ Ingest failed: {e}")
        logger.error(f"Ingest error: {e}", exc_info=True)
        return 1

    # ========================================================================
    # STEP 2: EXTRACT - Extract content using Docling
    # ========================================================================
    print("\n" + "=" * 80)
    print("STEP 2: EXTRACT CONTENT WITH DOCLING")
    print("=" * 80)

    extract_config: dict[str, Any] = {
        OperatorConstants.Config.TEXT_EXTRACTION: {
            OperatorConstants.Config.PROVIDER: "docling_library",
            OperatorConstants.Config.DOC_COLUMN: OperatorConstants.Columns.DOC_COLUMN_DEFAULT,
        },
        OperatorConstants.Config.ENTITY_EXTRACTION: {
            OperatorConstants.Config.PROVIDER: OperatorConstants.ExtractionModes.ENTITY_MODE_NONE
        },
    }

    try:
        extract_operator: Any = ExtractOperator(extract_config)
        extract_tables: list[pa.Table]
        extract_metadata: dict[str, Any]
        extract_tables, extract_metadata = extract_operator.transform(ingest_table)
        extract_table: pa.Table = extract_tables[0]

        print(f"✓ Extracted content from {extract_table.num_rows} document(s)")
        print(f"  Columns: {extract_table.column_names}")
        print(
            f"  Metadata: Processed={extract_metadata.get('processed_docs', 0)}, "
            f"Failed={extract_metadata.get('failed_docs_count', 0)}"
        )

        if "content" in extract_table.column_names and extract_table.num_rows > 0:
            content: Any = extract_table["content"][0].as_py()
            if content:
                preview: str = content[:200].replace("\n", " ")
                print(f"\n  Content preview: {preview}...")
                print(f"  Total characters: {len(content)}")

    except Exception as e:
        print(f"\n❌ Extract failed: {e}")
        logger.error(f"Extract error: {e}", exc_info=True)
        return 1

    # ========================================================================
    # STEP 3: CHUNK - Split content into chunks
    # ========================================================================
    print("\n" + "=" * 80)
    print("STEP 3: CHUNK CONTENT")
    print("=" * 80)

    chunk_config: dict[str, Any] = {
        "chunk_type": "hybrid",
        OperatorConstants.Config.DOC_COLUMN: OperatorConstants.Columns.DOC_COLUMN_DEFAULT,
        OperatorConstants.Processing.CHUNK_SIZE: args.chunk_size,
        "chunk_overlap": 128,
        "docling_tokenizer": "sentence-transformers/all-MiniLM-L6-v2",
        "retain_original_content": False,
        OperatorConstants.Config.SUMMARIZATION: {},
    }

    try:
        chunker_operator: Any = ChunkerOperator(chunk_config)
        chunk_tables: list[pa.Table]
        chunk_metadata: dict[str, Any]
        chunk_tables, chunk_metadata = chunker_operator.transform(extract_table)
        chunk_table: pa.Table = chunk_tables[0]

        print(f"✓ Chunked {chunk_table.num_rows} document(s)")
        print(f"  Columns: {chunk_table.column_names}")
        print(f"  Total chunks: {chunk_metadata.get(Metrics.External.TOTAL_CHUNKS, 0)}")
        print(
            f"  Metadata: Processed={chunk_metadata.get('processed_docs', 0)}, "
            f"Failed={chunk_metadata.get('failed_docs_count', 0)}"
        )

        if "chunked_content" in chunk_table.column_names and chunk_table.num_rows > 0:
            chunked_content: Any = chunk_table["chunked_content"][0].as_py()
            if chunked_content:
                chunks: list[dict[str, Any]] = chunked_content
                print(f"\n  First document has {len(chunks)} chunks")
                if chunks:
                    first_chunk: dict[str, Any] = chunks[0]
                    preview = first_chunk["chunk"][:150].replace("\n", " ")
                    print(f"  First chunk preview: {preview}...")
                    print(f"  First chunk metadata: {first_chunk.get('metadata', {})}")

    except Exception as e:
        print(f"\n❌ Chunking failed: {e}")
        logger.error(f"Chunking error: {e}", exc_info=True)
        return 1

    # ========================================================================
    # STEP 4: EMBEDDINGS - Generate embeddings with Ollama
    # ========================================================================
    print("\n" + "=" * 80)
    print("STEP 4: GENERATE EMBEDDINGS")
    print("=" * 80)

    embeddings_config: dict[str, Any] = {
        OperatorConstants.Config.PROVIDER: OperatorConstants.Config.PROVIDER_LITELLM,
        OperatorConstants.Config.PROVIDER_CONFIG: {
            OperatorConstants.Config.MODEL_ID: f"openai/{args.model}",
            OperatorConstants.LLM.API_BASE: "http://localhost:11434",
            OperatorConstants.Config.BATCH_SIZE: 32,
            OperatorConstants.Processing.TIMEOUT: 120,
        },
        OperatorConstants.Columns.EMBEDDINGS_COLUMN: OperatorConstants.Columns.EMBEDDINGS_COLUMN_DEFAULT,
        OperatorConstants.Config.DOC_COLUMN: OperatorConstants.Columns.DOC_COLUMN_DEFAULT,
        "overlap_ratio": 0.2,
    }

    try:
        embeddings_operator: EmbeddingsOperator = EmbeddingsOperator(embeddings_config)
        embeddings_tables: list[pa.Table]
        embeddings_metadata: dict[str, Any]
        embeddings_tables, embeddings_metadata = embeddings_operator.transform(chunk_table)
        embeddings_table: pa.Table = embeddings_tables[0]

        print(f"✓ Generated embeddings for {embeddings_table.num_rows} document(s)")
        print(f"  Columns: {embeddings_table.column_names}")
        print(
            f"  Metadata: Processed={embeddings_metadata.get('processed_docs', 0)}, "
            f"Failed={embeddings_metadata.get('failed_docs_count', 0)}"
        )

        if OperatorConstants.Columns.EMBEDDINGS in embeddings_table.column_names and embeddings_table.num_rows > 0:
            embeddings_data: Any = embeddings_table[OperatorConstants.Columns.EMBEDDINGS][0].as_py()
            if embeddings_data:
                if isinstance(embeddings_data, list):
                    if isinstance(embeddings_data[0], list):
                        print(f"\n  Generated {len(embeddings_data)} embedding vectors")
                        print(f"  Embedding dimensions: {len(embeddings_data[0])}")
                        print(f"  First embedding sample (first 5 values): {embeddings_data[0][:5]}")
                    else:
                        print(f"\n  Embedding dimensions: {len(embeddings_data)}")
                        print(f"  Embedding sample (first 5 values): {embeddings_data[:5]}")

        if (
            OperatorConstants.Columns.DOC_ID_HASH_DEFAULT in embeddings_table.column_names
            and embeddings_table.num_rows > 0
        ):
            doc_hash: str = embeddings_table[OperatorConstants.Columns.DOC_ID_HASH_DEFAULT][0].as_py()
            print(f"  Document hash: {doc_hash}")

    except Exception as e:
        print(f"\n❌ Embeddings generation failed: {e}")
        logger.error(f"Embeddings error: {e}", exc_info=True)
        return 1

    # ========================================================================
    # SUMMARY
    # ========================================================================
    print("\n" + "=" * 80)
    print("PIPELINE SUMMARY")
    print("=" * 80)
    print(f"✓ Ingest:     {ingest_metadata.get('processed_docs', 0)} documents")
    print(f"✓ Extract:    {extract_metadata.get('processed_docs', 0)} documents")
    print(f"✓ Chunk:      {chunk_metadata.get('processed_docs', 0)} documents")
    print(f"✓ Embeddings: {embeddings_metadata.get('processed_docs', 0)} documents")
    print("=" * 80)
    print("\n✓ Pipeline completed successfully!")
    print(f"\nFinal table shape: {embeddings_table.num_rows} rows x {len(embeddings_table.column_names)} columns")
    print(f"Final columns: {embeddings_table.column_names}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
