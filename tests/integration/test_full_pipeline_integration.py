#!/usr/bin/env python3
"""
Integration tests for the complete pipeline: IngestLocal -> ExtractDocling -> SemanticChunker
Tests the full document processing workflow from file ingestion to chunked content
"""

from pathlib import Path
import pytest
import pyarrow as pa

from datasift_opensource.backend.core.operators.universal.ingest.ingest_local_folder import IngestLocalOperator
from datasift_opensource.backend.operators.universal.extract.extract_docling_operator import ExtractDoclingOperator
from datasift_opensource.backend.core.operators.universal.chunker.semantic_chunker import SemanticChunkerOperator


class TestFullPipelineIntegration:
    """Integration tests for the complete document processing pipeline"""
    
    @pytest.fixture
    def fixtures_dir(self):
        """Get the fixtures directory"""
        fixtures_path = Path(__file__).parent.parent / "fixtures" / "invoices"
        if not fixtures_path.exists():
            pytest.skip(f"Fixtures directory not found: {fixtures_path}")
        return str(fixtures_path)
    
    def test_ingest_extract_chunk_pipeline(self, fixtures_dir):
        """Test the complete pipeline: Ingest -> Extract -> Chunk"""
        # Step 1: Ingest metadata
        print("\n=== Step 1: Ingest ===")
        ingest_config = {
            "input_folder": fixtures_dir,
            "include_filter": "pdf",
            "store_binary_content": True,
            "max_files": 2
        }
        
        ingest_op = IngestLocalOperator(ingest_config)
        ingest_tables, ingest_metadata = ingest_op.transform(None)
        ingest_table = ingest_tables[0]
        
        print(f"Ingested {ingest_table.num_rows} documents")
        print(f"Columns: {ingest_table.column_names}")
        
        # Verify ingest output
        assert ingest_table.num_rows > 0, "Should have ingested files"
        assert "path" in ingest_table.column_names
        assert "binary_content" in ingest_table.column_names
        assert "content" not in ingest_table.column_names
        
        # Step 2: Extract content with Docling (without template)
        print("\n=== Step 2: Extract ===")
        extract_config = {
            "doc_column": "content",
            "extract_tables": True,
            "extract_images": False,
            "use_template": False  # No template extraction
        }
        
        extract_op = ExtractDoclingOperator(extract_config)
        extract_tables, extract_metadata = extract_op.transform(ingest_table)
        extract_table = extract_tables[0]
        
        print(f"Extracted content from {extract_table.num_rows} documents")
        print(f"Columns: {extract_table.column_names}")
        print(f"Processed: {extract_metadata.get('processed_docs', 0)}")
        print(f"Failed: {extract_metadata.get('failed_docs', 0)}")
        
        # Verify extract output
        assert extract_table.num_rows > 0, "Should have extracted content"
        assert "content" in extract_table.column_names
        assert "doc_id_hash" in extract_table.column_names
        
        # Verify content was extracted
        content_count = 0
        for idx in range(extract_table.num_rows):
            content = extract_table["content"][idx].as_py()
            if content and len(content) > 0:
                content_count += 1
                print(f"  Document {idx}: {len(content)} characters")
        
        assert content_count > 0, "Should have extracted content from at least one document"
        
        # Step 3: Chunk the extracted content
        print("\n=== Step 3: Chunk ===")
        chunk_config = {
            "doc_column": "content",
            "chunk_type": "simple",
            "chunk_size": 1000,
            "chunk_overlap": 200,
            "retain_original_content": True
        }
        
        chunk_op = SemanticChunkerOperator(chunk_config)
        chunk_tables, chunk_metadata = chunk_op.transform(extract_table)
        chunk_table = chunk_tables[0]
        
        print(f"Chunked into {chunk_table.num_rows} chunks")
        print(f"Columns: {chunk_table.column_names}")
        
        # Verify chunk output
        assert chunk_table.num_rows > 0, "Should have created chunks"
        assert "chunked_content" in chunk_table.column_names or "content" in chunk_table.column_names
        
        # Verify chunks were created
        print(f"\nTotal chunks created: {chunk_table.num_rows}")
        
        # Summary
        print("\n=== Pipeline Summary ===")
        print(f"Documents ingested: {ingest_table.num_rows}")
        print(f"Documents extracted: {extract_metadata.get('processed_docs', 0)}")
        print(f"Total chunks: {chunk_table.num_rows}")
        print(f"Average chunks per document: {chunk_table.num_rows / ingest_table.num_rows:.1f}")
    
    def test_pipeline_with_path_only(self, fixtures_dir):
        """Test pipeline with path-only ingest (no binary content stored)"""
        # Step 1: Ingest with path only
        print("\n=== Step 1: Ingest (Path Only) ===")
        ingest_config = {
            "input_folder": fixtures_dir,
            "include_filter": "pdf",
            "store_binary_content": False,  # Path only
            "max_files": 1
        }
        
        ingest_op = IngestLocalOperator(ingest_config)
        ingest_tables, _ = ingest_op.transform(None)
        ingest_table = ingest_tables[0]
        
        assert ingest_table.num_rows > 0
        assert "path" in ingest_table.column_names
        assert "binary_content" not in ingest_table.column_names
        
        # Step 2: Extract using paths
        print("\n=== Step 2: Extract (From Paths) ===")
        extract_config = {
            "doc_column": "content",
            "extract_tables": False,
            "extract_images": False
        }
        
        extract_op = ExtractDoclingOperator(extract_config)
        extract_tables, _ = extract_op.transform(ingest_table)
        extract_table = extract_tables[0]
        
        assert extract_table.num_rows > 0
        assert "content" in extract_table.column_names
        
        # Step 3: Chunk
        print("\n=== Step 3: Chunk ===")
        chunk_config = {
            "doc_column": "content",
            "chunk_size": 500,
            "chunk_overlap": 100
        }
        
        chunk_op = SemanticChunkerOperator(chunk_config)
        chunk_tables, _ = chunk_op.transform(extract_table)
        chunk_table = chunk_tables[0]
        
        assert chunk_table.num_rows > 0
        print(f"Created {chunk_table.num_rows} chunks from path-only ingest")
    
    def test_pipeline_metadata_preservation(self, fixtures_dir):
        """Test that metadata is preserved through the entire pipeline"""
        # Ingest
        ingest_config = {
            "input_folder": fixtures_dir,
            "include_filter": "pdf",
            "store_binary_content": True,
            "max_files": 1
        }
        
        ingest_op = IngestLocalOperator(ingest_config)
        ingest_tables, _ = ingest_op.transform(None)
        ingest_table = ingest_tables[0]
        
        original_columns = set(ingest_table.column_names)
        original_rows = ingest_table.num_rows
        
        # Extract
        extract_config = {"doc_column": "content"}
        extract_op = ExtractDoclingOperator(extract_config)
        extract_tables, _ = extract_op.transform(ingest_table)
        extract_table = extract_tables[0]
        
        # Verify original metadata preserved after extract
        assert original_columns.issubset(set(extract_table.column_names))
        assert extract_table.num_rows == original_rows
        
        # Chunk
        chunk_config = {
            "doc_column": "content",
            "chunk_size": 1000
        }
        chunk_op = SemanticChunkerOperator(chunk_config)
        chunk_tables, _ = chunk_op.transform(extract_table)
        chunk_table = chunk_tables[0]
        
        # After chunking, we may have more rows (chunks), but original metadata should still be present
        assert chunk_table.num_rows >= original_rows
        print(f"Metadata preserved through pipeline: {original_rows} docs -> {chunk_table.num_rows} chunks")


def test_quick_pipeline():
    """Quick pipeline test without fixtures"""
    fixtures_dir = Path(__file__).parent.parent / "fixtures" / "invoices"
    
    if not fixtures_dir.exists():
        pytest.skip(f"Fixtures directory not found: {fixtures_dir}")
    
    # Quick end-to-end test
    ingest_op = IngestLocalOperator({
        "input_folder": str(fixtures_dir),
        "store_binary_content": True,
        "include_filter": "pdf",
        "max_files": 1
    })
    ingest_tables, _ = ingest_op.transform(None)
    
    extract_op = ExtractDoclingOperator({"doc_column": "content"})
    extract_tables, _ = extract_op.transform(ingest_tables[0])
    
    chunk_op = SemanticChunkerOperator({
        "doc_column": "content",
        "chunk_size": 500
    })
    chunk_tables, _ = chunk_op.transform(extract_tables[0])
    
    assert chunk_tables[0].num_rows > 0
    print(f"Quick pipeline test: Created {chunk_tables[0].num_rows} chunks")


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "-s"])