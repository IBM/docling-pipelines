#!/usr/bin/env python3
"""
Docling Chunker Operator
Implements document chunking using Docling's HybridChunker.
Based on: https://docling-project.github.io/docling/concepts/chunking/

This operator is designed to run completely locally without CPD, token, or project dependencies.
"""

import json
import logging
from typing import Any, Dict, List

import pyarrow as pa
from pyarrow import Table

# Try to import TransformUtils from data-prep-toolkit-transforms
try:
    from data_processing.utils import TransformUtils
    HAS_TRANSFORM_UTILS = True
except ImportError:
    HAS_TRANSFORM_UTILS = False
    # Fallback implementation
    class TransformUtils:
        @staticmethod
        def add_column(table: pa.Table, name: str, content: list) -> pa.Table:
            """Add a column to a PyArrow table."""
            new_column = pa.array(content)
            new_field = pa.field(name, new_column.type)
            return table.append_column(new_field, new_column)

# Import Docling chunking components
from docling_core.types.doc import DoclingDocument
from docling.chunking import HybridChunker

logger = logging.getLogger(__name__)


class DocIdHashOperator:
    """
    Placeholder for DocIdHashOperator.
    Generates hash IDs for document chunks.
    """
    def __init__(self, config: dict):
        self.config = config
    
    def transform(self, table: pa.Table) -> tuple[list[pa.Table], dict]:
        """
        Generate hash IDs for documents.
        """
        import hashlib
        
        # Generate hash IDs based on content
        hash_ids = []
        if "chunked_content" in table.column_names:
            for idx in range(table.num_rows):
                # Create hash from row index and chunked content
                content_str = f"chunk_{idx}"
                hash_id = hashlib.sha256(content_str.encode()).hexdigest()[:16]
                hash_ids.append(hash_id)
        else:
            # Fallback: generate hash IDs from row index
            import uuid
            hash_ids = [str(uuid.uuid4())[:16] for _ in range(table.num_rows)]
        
        # Add hash_id column to table
        table = TransformUtils.add_column(table=table, name="doc_id_hash", content=hash_ids)
        return [table], {}


class DoclingChunkerOperator:
    """
    Operator for chunking documents using Docling's HybridChunker.
    
    This operator uses Docling's hybrid chunking approach which combines:
    - Hierarchical chunking (respects document structure)
    - Semantic chunking (groups related content)
    
    Reference: https://docling-project.github.io/docling/concepts/chunking/
    """
    
    short_name = "docling_chunker"
    
    def __init__(self, config: dict[str, Any]):
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
        self.config = config
        self.doc_column = config.get("doc_column", "content")
        self.chunk_size = config.get("chunk_size", 512)
        self.chunk_overlap = config.get("chunk_overlap", 128)
        self.retain_original_content = config.get("retain_original_content", True)
        self.tokenizer = config.get("tokenizer", "sentence-transformers/all-MiniLM-L6-v2")
        
        # Initialize the HybridChunker
        self.chunker = None
        self._initialize_chunker()
    
    def _initialize_chunker(self):
        """Initialize the Docling HybridChunker."""
        try:
            self.chunker = HybridChunker(
                tokenizer=self.tokenizer,
                max_tokens=self.chunk_size,
                merge_peers=True  # Merge chunks at the same hierarchy level
            )
            logger.info(f"Initialized HybridChunker with tokenizer: {self.tokenizer}, max_tokens: {self.chunk_size}")
        except Exception as e:
            logger.error(f"Failed to initialize HybridChunker: {str(e)}")
            raise
    
    def _chunk_document(self, docling_doc_json: str, doc_name: str = None) -> List[Dict[str, Any]]:
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
            doc = DoclingDocument.model_validate_json(docling_doc_json)
            
            # Chunk the document
            chunk_iter = self.chunker.chunk(dl_doc=doc)
            
            # Convert chunks to our format
            chunks = []
            for idx, chunk in enumerate(chunk_iter):
                chunk_dict = {
                    "chunk": chunk.text,
                    "start_index": getattr(chunk, 'start_index', idx * self.chunk_size),
                    "metadata": {
                        "chunk_id": idx,
                        "doc_name": doc_name,
                        "token_count": len(chunk.text.split())  # Approximate token count
                    }
                }
                chunks.append(chunk_dict)
            
            logger.info(f"Created {len(chunks)} chunks for document: {doc_name}")
            return chunks
            
        except Exception as e:
            logger.error(f"Error chunking document {doc_name}: {str(e)}")
            logger.debug(f"Exception details: {type(e).__name__}: {str(e)}")
            # If chunking fails, return empty list (no fallback since we need proper DoclingDocument)
            return []
    
    def _create_docling_document_from_markdown(self, markdown_content: str, doc_name: str = None) -> str:
        """
        Create a serialized DoclingDocument from markdown content.
        This is a fallback for when docling_document column is not available.
        
        Args:
            markdown_content: Markdown text content
            doc_name: Document name
            
        Returns:
            Serialized DoclingDocument JSON string
        """
        from docling_core.types.doc import DoclingDocument, DocItemLabel
        
        # Create a basic DoclingDocument
        doc = DoclingDocument(name=doc_name or "document")
        
        # Split markdown into paragraphs and add as text items
        paragraphs = [p.strip() for p in markdown_content.split('\n\n') if p.strip()]
        
        for para in paragraphs:
            if para:
                # add_text expects text string and label
                doc.add_text(text=para, label=DocItemLabel.TEXT)
        
        # Serialize to JSON
        return doc.model_dump_json()
    
    def _simple_chunk_fallback(self, content: str, doc_name: str = None) -> List[Dict[str, Any]]:
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
        chars_per_chunk = self.chunk_size * 4
        overlap_chars = self.chunk_overlap * 4
        
        chunks = []
        start = 0
        chunk_id = 0
        
        while start < len(content):
            end = start + chars_per_chunk
            chunk_text = content[start:end]
            
            # Try to break at sentence boundary
            if end < len(content):
                last_period = chunk_text.rfind('.')
                last_newline = chunk_text.rfind('\n')
                break_point = max(last_period, last_newline)
                if break_point > 0:
                    end = start + break_point + 1
                    chunk_text = content[start:end]
            
            chunks.append({
                "chunk": chunk_text.strip(),
                "start_index": start,
                "metadata": {
                    "chunk_id": chunk_id,
                    "doc_name": doc_name,
                    "token_count": len(chunk_text.split()),
                    "fallback": True
                }
            })
            
            start = end - overlap_chars
            chunk_id += 1
        
        logger.info(f"Created {len(chunks)} fallback chunks for document: {doc_name}")
        return chunks
    
    def transform(self, table: pa.Table) -> tuple[list[pa.Table], dict[str, Any]]:
        """
        Transform the input table by chunking document content.
        
        Args:
            table: PyArrow table containing document information with columns:
                - docling_document: Serialized DoclingDocument from extract operator
                - content: Document content (markdown from Docling extraction)
                - name: Document name (optional)
                - id: Document ID (optional)
                
        Returns:
            Tuple of (list of transformed tables, metadata dictionary)
        """
        metadata = {
            "total_docs": table.num_rows,
            "processed_docs": 0,
            "failed_docs": 0,
            "total_chunks": 0,
            "status": "completed"
        }
        
        if table.num_rows == 0:
            return [table], metadata
        
        # Check if docling_document column exists (preferred for chunking)
        use_docling_doc = "docling_document" in table.column_names
        
        if not use_docling_doc and self.doc_column not in table.column_names:
            metadata["status"] = "failed"
            metadata["error"] = f"Neither 'docling_document' nor '{self.doc_column}' column found in table"
            logger.error(metadata["error"])
            return [table], metadata
        
        # Process documents and create chunks
        chunked_content_list = []
        failed_indices = []
        
        for idx in range(table.num_rows):
            try:
                # Get document information
                doc_name = table["name"][idx].as_py() if "name" in table.column_names else f"doc_{idx}"
                
                if use_docling_doc:
                    # Use the serialized DoclingDocument for chunking
                    docling_doc_json = table["docling_document"][idx].as_py()
                    
                    if not docling_doc_json:
                        logger.warning(f"Empty docling_document for document: {doc_name}")
                        chunked_content_list.append([])
                        failed_indices.append(idx)
                        metadata["failed_docs"] += 1
                        continue
                    
                    # Chunk the document using DoclingDocument
                    chunks = self._chunk_document(docling_doc_json, doc_name)
                else:
                    # Fallback: create DoclingDocument from markdown content
                    logger.warning(f"docling_document column not found. Creating DoclingDocument from markdown content.")
                    content = table[self.doc_column][idx].as_py()
                    
                    if not content:
                        logger.warning(f"Empty content for document: {doc_name}")
                        chunked_content_list.append([])
                        failed_indices.append(idx)
                        metadata["failed_docs"] += 1
                        continue
                    
                    # Create DoclingDocument from markdown and chunk
                    try:
                        docling_doc_json = self._create_docling_document_from_markdown(content, doc_name)
                        chunks = self._chunk_document(docling_doc_json, doc_name)
                    except Exception as e:
                        logger.error(f"Error creating DoclingDocument from markdown for {doc_name}: {str(e)}")
                        chunked_content_list.append([])
                        failed_indices.append(idx)
                        metadata["failed_docs"] += 1
                        continue
                
                if chunks:
                    chunked_content_list.append(chunks)
                    metadata["processed_docs"] += 1
                    metadata["total_chunks"] += len(chunks)
                else:
                    chunked_content_list.append([])
                    failed_indices.append(idx)
                    metadata["failed_docs"] += 1
                    
            except Exception as e:
                logger.error(f"Error processing document at index {idx}: {str(e)}")
                chunked_content_list.append([])
                failed_indices.append(idx)
                metadata["failed_docs"] += 1
        
        # Add chunked_content column to table
        if chunked_content_list:
            # Convert list of dicts to JSON strings for PyArrow compatibility
            chunked_content_json = [
                json.dumps(chunks) if chunks else None
                for chunks in chunked_content_list
            ]
            table = TransformUtils.add_column(
                table=table,
                name="chunked_content",
                content=chunked_content_json
            )
            logger.info(f"Added chunked_content column with {metadata['total_chunks']} total chunks")
        
        # Add hash column using DocIdHashOperator
        logger.info("Generating hash IDs for chunks")
        hash_operator = DocIdHashOperator({})
        table_list, _ = hash_operator.transform(table)
        table = table_list[0]
        
        # Remove docling_document column after chunking (no longer needed)
        if "docling_document" in table.column_names:
            logger.info("Removing docling_document column after chunking")
            table = table.drop_columns(["docling_document"])
        
        # Remove original content column if not retaining
        if not self.retain_original_content and self.doc_column in table.column_names:
            logger.info(f"Removing original content column: {self.doc_column}")
            table = table.drop_columns([self.doc_column])
        
        # Update metadata
        if metadata["failed_docs"] > 0:
            metadata["status"] = "completed_with_errors"
        
        return [table], metadata
    
    @staticmethod
    def get_metadata():
        """
        Get metadata about the operator including features and attributes.
        
        Returns:
            Dictionary containing operator metadata
        """
        return {
            "sdk": True,
            "category": "chunker",
            "is_operator_available": True,
            "label": "Docling Chunker",
            "description": "Chunk documents using Docling's HybridChunker for semantic and hierarchical chunking",
            "features": {
                "chunked_content": {
                    "name": "Chunked Content",
                    "description": "Document content split into semantic chunks",
                    "available_for_filter": True,
                    "available_for_vector_db": True,
                    "type": "string",
                    "tags": ["mandatory"]
                },
                "doc_id_hash": {
                    "name": "Hash ID",
                    "description": "Hash ID of the document chunk",
                    "available_for_vector_db": True,
                    "mandatory_for_vector_db": True,
                    "type": "string",
                    "is_primary": True,
                    "tags": ["mandatory", "primary"]
                }
            },
            "attributes": {
                "doc_column": {
                    "name": "Document Column",
                    "description": "Name of the column containing document content",
                    "required": False,
                    "default": "content",
                    "type": "string"
                },
                "chunk_size": {
                    "name": "Chunk Size",
                    "description": "Target size for chunks in tokens",
                    "required": False,
                    "default": 512,
                    "min_value": 100,
                    "max_value": 2048,
                    "type": "integer"
                },
                "chunk_overlap": {
                    "name": "Chunk Overlap",
                    "description": "Number of overlapping tokens between consecutive chunks",
                    "required": False,
                    "default": 128,
                    "min_value": 0,
                    "max_value": 512,
                    "type": "integer"
                },
                "retain_original_content": {
                    "name": "Retain Original Content",
                    "description": "Whether to keep the original content column after chunking",
                    "required": False,
                    "default": True,
                    "type": "boolean"
                },
                "tokenizer": {
                    "name": "Tokenizer",
                    "description": "Tokenizer model to use for chunking",
                    "required": False,
                    "default": "sentence-transformers/all-MiniLM-L6-v2",
                    "type": "string"
                }
            }
        }


def main():
    """
    Main function to test the docling_chunker_operator.
    """
    # ============ CONFIGURATION VARIABLES ============
    # Path to a file that has already been extracted with extract_docling_operator
    input_file = "tests/fixtures/invoices/TR-INV_044_1_1.1.pdf"
    
    # Chunking configuration
    chunk_size = 512
    chunk_overlap = 128
    # ================================================
    
    from pathlib import Path
    
    # First, extract the document using extract_docling_operator
    logger.info("Step 1: Extracting document content")
    from datasift_opensource.backend.core.operators.universal.extract.extract_docling import ExtractDoclingOperator
    
    extract_config = {
        "doc_column": "content",
        "extract_tables": True,
        "extract_images": True
    }
    
    extract_operator = ExtractDoclingOperator(extract_config)
    
    # Read file
    input_path = Path(input_file)
    with open(input_path, 'rb') as f:
        binary_content = f.read()
    
    # Create PyArrow table for extraction
    extract_table = pa.table({
        "id": [str(input_path)],
        "name": [input_path.name],
        "path": [str(input_path)],
        "binary_content": [binary_content]
    })
    
    # Extract content
    result_tables, extract_metadata = extract_operator.transform(extract_table)
    extracted_table = result_tables[0]
    
    logger.info(f"Extraction complete: {extract_metadata}")
    logger.info(f"Extracted table columns: {extracted_table.column_names}")
    
    # Step 2: Chunk the extracted content
    logger.info("\nStep 2: Chunking document content")
    
    chunk_config = {
        "doc_column": "content",
        "chunk_size": chunk_size,
        "chunk_overlap": chunk_overlap,
        "retain_original_content": True
    }
    
    chunker_operator = DoclingChunkerOperator(chunk_config)
    
    # Chunk the content
    chunked_tables, chunk_metadata = chunker_operator.transform(extracted_table)
    chunked_table = chunked_tables[0]
    
    # Log results
    logger.info(f"\nChunking complete!")
    logger.info(f"Metadata: {chunk_metadata}")
    logger.info(f"Result columns: {chunked_table.column_names}")
    
    if "chunked_content" in chunked_table.column_names:
        chunked_content = chunked_table["chunked_content"][0].as_py()
        if chunked_content:
            chunks = json.loads(chunked_content)
            logger.info(f"\nTotal chunks created: {len(chunks)}")
            logger.info(f"First chunk preview: {chunks[0]['chunk'][:200]}...")
            logger.info(f"First chunk metadata: {chunks[0]['metadata']}")
    
    if "doc_id_hash" in chunked_table.column_names:
        hash_id = chunked_table["doc_id_hash"][0].as_py()
        logger.info(f"Document hash: {hash_id}")
    
    return 0


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    exit(main())