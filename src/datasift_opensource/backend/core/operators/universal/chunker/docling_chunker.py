#!/usr/bin/env python3
"""
Docling Chunker Operator
Implements document chunking using Docling's HybridChunker.
Follows the structure of IngestLocalOperator with AbstractOperator as parent class.
Based on: https://docling-project.github.io/docling/concepts/chunking/
"""

import json
import logging
from typing import Any

import pyarrow as pa

from common.util.constants import (
    AttributeDataTypes,
    DatasiftConstants,
    ExecutionStatus,
    Metrics,
    OperatorConstants,
)
from common.util.log import get_logger
from core.operators.abstract_operator import AbstractOperator, OperatorCategory
from core.operators.universal.doc_id.doc_id_hash import DocIdHashOperator

# Try to import TransformUtils from data-prep-toolkit-transforms
try:
    from data_processing.utils import TransformUtils

    HAS_TRANSFORM_UTILS: bool = True
except ImportError:
    HAS_TRANSFORM_UTILS: bool = False

    # Fallback implementation
    class TransformUtils:
        @staticmethod
        def add_column(table: pa.Table, name: str, content: list) -> pa.Table:
            """Add a column to a PyArrow table."""
            new_column: pa.Array = pa.array(content)
            new_field: pa.Field = pa.field(name, new_column.type)
            return table.append_column(new_field, new_column)


# Import Docling chunking components
from docling_core.transforms.chunker.hybrid_chunker import HybridChunker
from docling_core.types.doc.document import DoclingDocument

logger: logging.Logger = get_logger()


class DoclingChunkerOperator(AbstractOperator):
    """
    Operator for chunking documents using Docling's HybridChunker.
    Follows the structure of IngestLocalOperator with AbstractOperator as parent class.

    This operator uses Docling's hybrid chunking approach which combines:
    - Hierarchical chunking (respects document structure)
    - Semantic chunking (groups related content)

    Reference: https://docling-project.github.io/docling/concepts/chunking/
    """

    short_name: str = OperatorConstants.DOCLING_CHUNKER
    category: OperatorCategory = OperatorCategory.Functional

    def __init__(self, config: dict[str, Any]) -> None:
        """
        Initialize the operator with configuration.

        Args:
            config: Configuration dictionary containing:
                - doc_column: Name of the column containing document content (default: "content")
                - chunk_size: Target size for chunks in tokens (default: 512)
                - chunk_overlap: Number of overlapping tokens between chunks (default: 128)
                - retain_original_content: Whether to keep original content column (default: True)
                - tokenizer: Tokenizer to use for chunking (default: "sentence-transformers/all-MiniLM-L6-v2")
        """
        super().__init__(config)
        self.doc_column: str = config.get(OperatorConstants.DOC_COLUMN, OperatorConstants.DOC_COLUMN_DEFAULT)
        self.chunk_size: int = config.get(OperatorConstants.CHUNK_SIZE, OperatorConstants.CHUNK_SIZE_DEFAULT)
        self.chunk_overlap: int = config.get("chunk_overlap", 128)
        self.retain_original_content: bool = config.get("retain_original_content", True)
        self.tokenizer: str = config.get("tokenizer", "sentence-transformers/all-MiniLM-L6-v2")
        self.common_log_arguments: dict[str, Any] = {
            DatasiftConstants.JOB_ID: self.job_id,
            DatasiftConstants.JOB_RUN_ID: self.job_run_id,
        }
    
        # Validate input parameters
        self._validate_input_parameters()

        # Initialize the HybridChunker
        self.chunker: HybridChunker | None = None
        self._initialize_chunker()
    
    def _validate_input_parameters(self) -> None:
        """
        Validate input parameters for the Docling chunker operator.
        
        Raises:
            ValueError: If required parameters are missing or invalid
        """
        # Validate doc_column
        if not self.doc_column:
            raise ValueError("doc_column is required")
        if not isinstance(self.doc_column, str) or not self.doc_column.strip():
            raise ValueError("doc_column must be a non-empty string")
        
        # Validate chunk_size
        if not isinstance(self.chunk_size, int):
            raise ValueError("chunk_size must be an integer")
        if self.chunk_size < 100:
            raise ValueError("chunk_size must be at least 100 tokens")
        if self.chunk_size > 2048:
            raise ValueError("chunk_size must not exceed 2048 tokens")
        
        # Validate chunk_overlap
        if not isinstance(self.chunk_overlap, int):
            raise ValueError("chunk_overlap must be an integer")
        if self.chunk_overlap < 0:
            raise ValueError("chunk_overlap must be non-negative")
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be less than chunk_size")
        
        # Validate tokenizer
        if not self.tokenizer:
            raise ValueError("tokenizer is required")
        if not isinstance(self.tokenizer, str) or not self.tokenizer.strip():
            raise ValueError("tokenizer must be a non-empty string")


    def _initialize_chunker(self) -> None:
        """Initialize the Docling HybridChunker."""
        try:
            self.chunker = HybridChunker(
                tokenizer=self.tokenizer,
                max_tokens=self.chunk_size,
                merge_peers=True,  # Merge chunks at the same hierarchy level
            )
            logger.info(f"Initialized HybridChunker with tokenizer: {self.tokenizer}, max_tokens: {self.chunk_size}")
        except Exception as e:
            logger.error(f"Failed to initialize HybridChunker: {e!s}")
            raise

    def _chunk_document(self, docling_doc_json: str, doc_name: str | None = None) -> list[dict[str, Any]]:
        """
        Chunk a single document using Docling's HybridChunker.

        Args:
            docling_doc_json: Serialized DoclingDocument JSON from extract operator
            doc_name: Optional document name for logging

        Returns:
            List of chunk dictionaries with 'chunk', 'start_index', and 'metadata'
        """
        if not docling_doc_json:
            logger.warning(f"Empty docling_document for document: {doc_name}")
            return []

        try:
            # Deserialize the DoclingDocument from JSON
            doc: DoclingDocument = DoclingDocument.model_validate_json(docling_doc_json)

            # Chunk the document
            chunk_iter = self.chunker.chunk(dl_doc=doc)

            # Convert chunks to our format
            chunks: list[dict[str, Any]] = []
            for idx, chunk in enumerate(chunk_iter):
                chunk_dict: dict[str, Any] = {
                    "chunk": chunk.text,
                    "start_index": getattr(chunk, "start_index", idx * self.chunk_size),
                    "metadata": {
                        "chunk_id": idx,
                        "doc_name": doc_name,
                        "token_count": len(chunk.text.split()),  # Approximate token count
                    },
                }
                chunks.append(chunk_dict)

            logger.info(f"Created {len(chunks)} chunks for document: {doc_name}")
            return chunks

        except Exception as e:
            logger.error(f"Error chunking document {doc_name}: {e!s}")
            logger.debug(f"Exception details: {type(e).__name__}: {e!s}")
            # If chunking fails, return empty list (no fallback since we need proper DoclingDocument)
            return []

    def _create_docling_document_from_markdown(self, markdown_content: str, doc_name: str | None = None) -> str:
        """
        Create a serialized DoclingDocument from markdown content.
        This is a fallback for when docling_document column is not available.

        Args:
            markdown_content: Markdown text content
            doc_name: Document name

        Returns:
            Serialized DoclingDocument JSON string
        """
        from docling_core.types.doc.document import DoclingDocument
        from docling_core.types.doc.labels import DocItemLabel

        # Create a basic DoclingDocument
        doc: DoclingDocument = DoclingDocument(name=doc_name or "document")

        # Split markdown into paragraphs and add as text items
        paragraphs: list[str] = [p.strip() for p in markdown_content.split("\n\n") if p.strip()]

        for para in paragraphs:
            if para:
                # add_text expects text string and label
                doc.add_text(text=para, label=DocItemLabel.TEXT)

        # Serialize to JSON
        return doc.model_dump_json()

    def _simple_chunk_fallback(self, content: str, doc_name: str | None = None) -> list[dict[str, Any]]:
        """
        Fallback to simple character-based chunking if Docling chunking fails.

        Args:
            content: Document content
            doc_name: Optional document name

        Returns:
            List of chunk dictionaries
        """
        logger.warning(f"Using fallback simple chunking for document: {doc_name}")

        # Approximate characters per token (rough estimate: 4 chars per token)
        chars_per_chunk: int = self.chunk_size * 4
        overlap_chars: int = self.chunk_overlap * 4

        chunks: list[dict[str, Any]] = []
        start: int = 0
        chunk_id: int = 0

        while start < len(content):
            end: int = start + chars_per_chunk
            chunk_text: str = content[start:end]

            # Try to break at sentence boundary
            if end < len(content):
                last_period: int = chunk_text.rfind(".")
                last_newline: int = chunk_text.rfind("\n")
                break_point: int = max(last_period, last_newline)
                if break_point > 0:
                    end = start + break_point + 1
                    chunk_text = content[start:end]

            chunks.append(
                {
                    "chunk": chunk_text.strip(),
                    "start_index": start,
                    "metadata": {
                        "chunk_id": chunk_id,
                        "doc_name": doc_name,
                        "token_count": len(chunk_text.split()),
                        "fallback": True,
                    },
                }
            )

            start = end - overlap_chars
            chunk_id += 1

        logger.info(f"Created {len(chunks)} fallback chunks for document: {doc_name}")
        return chunks

    def transform(self, table: pa.Table) -> tuple[list[pa.Table], dict[str, Any]]:
        """
        Transform the input table by chunking document content.

        Args:
            table: PyArrow table containing document information with columns:
                - content: Document content (markdown from Docling extraction)
                - name: Document name (optional)
                - id: Document ID (optional)

        Returns:
            Tuple of (list of transformed tables, metadata dictionary)
        """
        # Initialize metadata using base method
        metadata: dict[str, Any] = self.create_base_metadata(total_docs_count=table.num_rows)
        metadata[Metrics.External.TOTAL_CHUNKS] = 0

        if table.num_rows == 0:
            return [table], metadata

        # Check if content column exists
        if self.doc_column not in table.column_names:
            error_msg: str = f"'{self.doc_column}' column not found in table"
            metadata[Metrics.External.NODE_STATUS] = ExecutionStatus.FAILED.value
            metadata[OperatorConstants.ERROR] = error_msg
            logger.error(error_msg, extra=self.common_log_arguments)
            return [table], metadata

        # Process documents and create chunks
        chunked_content_list: list[list[dict[str, Any]]] = []
        failed_indices: list[int] = []

        for idx in range(table.num_rows):
            try:
                # Get document information
                doc_name: str = table["name"][idx].as_py() if "name" in table.column_names else f"doc_{idx}"

                # Get markdown content from the content column
                content: Any = table[self.doc_column][idx].as_py()

                if not content:
                    logger.warning(
                        f"Empty content for document: {doc_name}",
                        extra=self.common_log_arguments,
                    )
                    chunked_content_list.append([])
                    failed_indices.append(idx)
                    self.record_failed_document(
                        metadata=metadata,
                        doc_id=str(idx),
                        doc_name=doc_name,
                        reason="Empty content",
                    )
                    continue

                # Create DoclingDocument from markdown content and chunk
                try:
                    docling_doc_json: str = self._create_docling_document_from_markdown(content, doc_name)
                    chunks: list[dict[str, Any]] = self._chunk_document(docling_doc_json, doc_name)
                except Exception as e:
                    logger.error(
                        f"Error creating DoclingDocument from markdown for {doc_name}: {e!s}",
                        extra=self.common_log_arguments,
                    )
                    chunked_content_list.append([])
                    failed_indices.append(idx)
                    self.record_failed_document(
                        metadata=metadata,
                        doc_id=str(idx),
                        doc_name=doc_name,
                        reason=f"Error creating DoclingDocument: {e!s}",
                    )
                    continue

                if chunks:
                    chunked_content_list.append(chunks)
                    metadata[Metrics.External.PROCESSED_DOCS] += 1
                    metadata[Metrics.External.TOTAL_CHUNKS] += len(chunks)
                else:
                    chunked_content_list.append([])
                    failed_indices.append(idx)
                    self.record_failed_document(
                        metadata=metadata,
                        doc_id=str(idx),
                        doc_name=doc_name,
                        reason="No chunks generated",
                    )

            except Exception as e:
                logger.error(
                    f"Error processing document at index {idx}: {e!s}",
                    extra=self.common_log_arguments,
                )
                chunked_content_list.append([])
                failed_indices.append(idx)
                doc_name = (
                    table[OperatorConstants.NAME][idx].as_py()
                    if OperatorConstants.NAME in table.column_names
                    else f"doc_{idx}"
                )
                self.record_failed_document(metadata=metadata, doc_id=str(idx), doc_name=doc_name, reason=str(e))

        # Add chunked_content column to table
        if chunked_content_list:
            # Convert list of dicts to JSON strings for PyArrow compatibility
            chunked_content_json: list[str | None] = [
                json.dumps(chunks) if chunks else None for chunks in chunked_content_list
            ]
            table = TransformUtils.add_column(table=table, name="chunked_content", content=chunked_content_json)
            logger.info(
                f"Added chunked_content column with {metadata[Metrics.External.TOTAL_CHUNKS]} total chunks",
                extra=self.common_log_arguments,
            )

        # Add hash column using DocIdHashOperator
        logger.info("Generating hash IDs for chunks", extra=self.common_log_arguments)
        hash_operator: DocIdHashOperator = DocIdHashOperator({OperatorConstants.DOC_COLUMN: self.doc_column})
        table_list: list[pa.Table]
        table_list, _ = hash_operator.transform(table)
        table = table_list[0]

        # Remove original content column if not retaining
        if not self.retain_original_content and self.doc_column in table.column_names:
            logger.info(
                f"Removing original content column: {self.doc_column}",
                extra=self.common_log_arguments,
            )
            table = table.drop_columns([self.doc_column])

        # Update metadata status
        node_status: str = ExecutionStatus.COMPLETED.value
        if metadata[Metrics.External.FAILED_DOCS_COUNT] > 0:
            node_status = ExecutionStatus.COMPLETED_WITH_ERRORS.value
        metadata[Metrics.External.NODE_STATUS] = node_status

        return [table], metadata

    def get_metadata(self) -> dict[str, Any]:
        """
        Get metadata about the operator including features and attributes.
        Follows the structure of IngestLocalOperator.get_metadata()

        Returns:
            Dictionary containing operator metadata
        """
        metadata_features: dict[str, dict[str, Any]] = {
            OperatorConstants.CHUNKED_CONTENT: {
                OperatorConstants.NAME: "Chunked Content",
                OperatorConstants.DESCRIPTION: "Document content split into semantic chunks",
                OperatorConstants.AVAILABLE_FOR_FILTER: True,
                OperatorConstants.AVAILABLE_FOR_VECTOR_DB: True,
                OperatorConstants.TYPE: OperatorConstants.TYPE_STRING,
                OperatorConstants.TAGS: [OperatorConstants.MANDATORY],
            },
            self.doc_id_hash: {
                OperatorConstants.NAME: "Hash ID",
                OperatorConstants.DESCRIPTION: "Hash ID of the document chunk",
                OperatorConstants.AVAILABLE_FOR_VECTOR_DB: True,
                OperatorConstants.MANDATORY_FOR_VECTOR_DB: True,
                OperatorConstants.TYPE: OperatorConstants.TYPE_STRING,
                OperatorConstants.IS_PRIMARY: True,
                OperatorConstants.TAGS: [
                    OperatorConstants.MANDATORY,
                    OperatorConstants.PRIMARY,
                ],
            },
        }

        return {
            OperatorConstants.CATEGORY: self.category.value,
            OperatorConstants.FEATURES: metadata_features,
            OperatorConstants.IS_OPERATOR_AVAILABLE: self.is_available(),
            OperatorConstants.ATTRIBUTES: {
                OperatorConstants.DOC_COLUMN: {
                    OperatorConstants.NAME: "Document Column",
                    OperatorConstants.DESCRIPTION: "Name of the column containing document content",
                    OperatorConstants.REQUIRED: False,
                    OperatorConstants.DEFAULT: OperatorConstants.DOC_COLUMN_DEFAULT,
                    OperatorConstants.TYPE: AttributeDataTypes.STRING,
                },
                OperatorConstants.CHUNK_SIZE: {
                    OperatorConstants.NAME: "Chunk Size",
                    OperatorConstants.DESCRIPTION: "Target size for chunks in tokens",
                    OperatorConstants.REQUIRED: False,
                    OperatorConstants.DEFAULT: OperatorConstants.CHUNK_SIZE_DEFAULT,
                    OperatorConstants.MIN_VALUE: 100,
                    OperatorConstants.MAX_VALUE: 2048,
                    OperatorConstants.TYPE: AttributeDataTypes.INTEGER,
                },
                "chunk_overlap": {
                    OperatorConstants.NAME: "Chunk Overlap",
                    OperatorConstants.DESCRIPTION: "Number of overlapping tokens between consecutive chunks",
                    OperatorConstants.REQUIRED: False,
                    OperatorConstants.DEFAULT: 128,
                    OperatorConstants.MIN_VALUE: 0,
                    OperatorConstants.MAX_VALUE: 512,
                    OperatorConstants.TYPE: AttributeDataTypes.INTEGER,
                },
                "retain_original_content": {
                    OperatorConstants.NAME: "Retain Original Content",
                    OperatorConstants.DESCRIPTION: "Whether to keep the original content column after chunking",
                    OperatorConstants.REQUIRED: False,
                    OperatorConstants.DEFAULT: True,
                    OperatorConstants.TYPE: AttributeDataTypes.BOOLEAN,
                },
                "tokenizer": {
                    OperatorConstants.NAME: "Tokenizer",
                    OperatorConstants.DESCRIPTION: "Tokenizer model to use for chunking",
                    OperatorConstants.REQUIRED: False,
                    OperatorConstants.DEFAULT: "sentence-transformers/all-MiniLM-L6-v2",
                    OperatorConstants.TYPE: AttributeDataTypes.STRING,
                },
            },
        }


def main() -> int:
    """
    Main function to test the docling_chunker_operator.
    """
    # ============ CONFIGURATION VARIABLES ============
    # Path to a file that has already been extracted with extract_docling_operator
    input_file: str = "tests/fixtures/invoices/TR-INV_044_1_1.1.pdf"

    # Chunking configuration
    chunk_size: int = 512
    chunk_overlap: int = 128
    # ================================================

    from pathlib import Path

    # First, extract the document using extract_docling_operator
    logger.info("Step 1: Extracting document content")
    from core.operators.universal.extract.extract_docling import ExtractDoclingOperator

    extract_config: dict[str, Any] = {
        "doc_column": "content",
        "extract_tables": True,
        "extract_images": True,
    }

    extract_operator: ExtractDoclingOperator = ExtractDoclingOperator(extract_config)

    # Read file
    input_path: Path = Path(input_file)
    binary_content: bytes
    with open(input_path, "rb") as f:
        binary_content = f.read()

    # Create PyArrow table for extraction
    extract_table: pa.Table = pa.table(
        {
            "id": [str(input_path)],
            "name": [input_path.name],
            "path": [str(input_path)],
            "binary_content": [binary_content],
        }
    )

    # Extract content
    result_tables: list[pa.Table]
    extract_metadata: dict[str, Any]
    result_tables, extract_metadata = extract_operator.transform(extract_table)
    extracted_table: pa.Table = result_tables[0]

    logger.info(f"Extraction complete: {extract_metadata}")
    logger.info(f"Extracted table columns: {extracted_table.column_names}")

    # Step 2: Chunk the extracted content
    logger.info("\nStep 2: Chunking document content")

    chunk_config: dict[str, Any] = {
        "doc_column": "content",
        "chunk_size": chunk_size,
        "chunk_overlap": chunk_overlap,
        "retain_original_content": True,
    }

    chunker_operator: DoclingChunkerOperator = DoclingChunkerOperator(chunk_config)

    # Chunk the content
    chunked_tables: list[pa.Table]
    chunk_metadata: dict[str, Any]
    chunked_tables, chunk_metadata = chunker_operator.transform(extracted_table)
    chunked_table: pa.Table = chunked_tables[0]

    # Log results
    logger.info("\nChunking complete!")
    logger.info(f"Metadata: {chunk_metadata}")
    logger.info(f"Result columns: {chunked_table.column_names}")

    if "chunked_content" in chunked_table.column_names:
        chunked_content: str | None = chunked_table["chunked_content"][0].as_py()
        if chunked_content:
            chunks: list[dict[str, Any]] = json.loads(chunked_content)
            logger.info(f"\nTotal chunks created: {len(chunks)}")
            logger.info(f"First chunk preview: {chunks[0]['chunk'][:200]}...")
            logger.info(f"First chunk metadata: {chunks[0]['metadata']}")

    if "doc_id_hash" in chunked_table.column_names:
        hash_id: str | None = chunked_table["doc_id_hash"][0].as_py()
        logger.info(f"Document hash: {hash_id}")

    return 0


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    exit(main())
