#!/usr/bin/env python3
"""
Unit tests for IngestLocalOperator
Tests both metadata-only mode and legacy extraction mode
"""

import sys
import os
import tempfile
from pathlib import Path
import pytest

# Add the backend directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src" / "datasift_opensource" / "backend"))

import pyarrow as pa

from datasift_opensource.backend.core.operators.universal.ingest.ingest_local_folder import IngestLocalOperator


class TestIngestLocalOperator:
    """Test suite for IngestLocalOperator"""
    
    @pytest.fixture
    def temp_test_dir(self):
        """Create a temporary directory with test files"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files
            test_dir = Path(tmpdir)
            
            # Create a text file
            txt_file = test_dir / "test.txt"
            txt_file.write_text("This is a test text file.")
            
            # Create a PDF file (minimal valid PDF)
            pdf_file = test_dir / "test.pdf"
            pdf_content = b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj
2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj
3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
/Contents 4 0 R
>>
endobj
4 0 obj
<<
/Length 44
>>
stream
BT
/F1 12 Tf
100 700 Td
(Test PDF) Tj
ET
endstream
endobj
xref
0 5
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000214 00000 n 
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
306
%%EOF"""
            pdf_file.write_bytes(pdf_content)
            
            yield str(test_dir)
    
    def test_metadata_only_mode(self, temp_test_dir):
        """Test metadata-only mode with binary content storage"""
        config = {
            "input_folder": temp_test_dir,
            "store_binary_content": True,
            "max_files": 10
        }
        
        operator = IngestLocalOperator(config)
        tables, metadata = operator.transform(None)
        table = tables[0]
        
        # Verify table structure
        assert table.num_rows > 0, "Should have ingested files"
        assert "path" in table.column_names, "Should have path column"
        assert "binary_content" in table.column_names, "Should have binary_content column"
        assert "content" not in table.column_names, "Should NOT have content column in metadata-only mode"
        
        # Verify metadata
        assert "id" in table.column_names
        assert "name" in table.column_names
        assert "size" in table.column_names
        
        # Verify binary content is stored
        for idx in range(table.num_rows):
            binary_content = table["binary_content"][idx].as_py()
            assert binary_content is not None, "Binary content should be stored"
            assert len(binary_content) > 0, "Binary content should not be empty"
    
    def test_metadata_only_without_binary(self, temp_test_dir):
        """Test metadata-only mode without storing binary content"""
        config = {
            "input_folder": temp_test_dir,
            "store_binary_content": False,
            "max_files": 10
        }
        
        operator = IngestLocalOperator(config)
        tables, metadata = operator.transform(None)
        table = tables[0]
        
        # Verify table structure
        assert table.num_rows > 0, "Should have ingested files"
        assert "path" in table.column_names, "Should have path column"
        assert "binary_content" not in table.column_names, "Should NOT have binary_content when store_binary_content=False"
        assert "content" not in table.column_names, "Should NOT have content column"
    
    def test_file_filtering(self, temp_test_dir):
        """Test file filtering by extension"""
        # Test include filter
        config = {
            "input_folder": temp_test_dir,
            "include_filter": "txt",
            "extract_content": False,
            "store_binary_content": True,
            "max_files": 10
        }
        
        operator = IngestLocalOperator(config)
        tables, metadata = operator.transform(None)
        table = tables[0]
        
        # Verify only txt files are included
        for idx in range(table.num_rows):
            name = table["name"][idx].as_py()
            assert name.endswith(".txt"), "Should only include .txt files"
    
    def test_max_files_limit(self, temp_test_dir):
        """Test max_files limit"""
        config = {
            "input_folder": temp_test_dir,
            "extract_content": False,
            "store_binary_content": True,
            "max_files": 1
        }
        
        operator = IngestLocalOperator(config)
        tables, metadata = operator.transform(None)
        table = tables[0]
        
        # Should respect max_files limit
        assert table.num_rows <= 1, "Should respect max_files limit"
    
    def test_get_metadata(self):
        """Test get_metadata method"""
        # Test metadata-only mode with binary content
        config = {
            "store_binary_content": True
        }
        operator = IngestLocalOperator(config)
        metadata = operator.get_metadata()
        
        assert "features" in metadata
        assert "path" in metadata["features"]
        assert "binary_content" in metadata["features"]
        assert "attributes" in metadata
        assert "store_binary_content" in metadata["attributes"]
        
        # Test metadata-only mode without binary content
        config_no_binary = {
            "store_binary_content": False
        }
        operator_no_binary = IngestLocalOperator(config_no_binary)
        metadata_no_binary = operator_no_binary.get_metadata()
        
        assert "features" in metadata_no_binary
        assert "path" in metadata_no_binary["features"]
        assert "binary_content" not in metadata_no_binary["features"]


def test_ingest_local_operator_basic():
    """Basic test without fixtures for simple verification"""
    # Use the fixtures directory that should exist
    fixtures_dir = Path(__file__).parent.parent.parent / "fixtures" / "invoices"
    
    if not fixtures_dir.exists():
        pytest.skip(f"Fixtures directory not found: {fixtures_dir}")
    
    config = {
        "input_folder": str(fixtures_dir),
        "store_binary_content": True,
        "include_filter": "pdf",
        "max_files": 5
    }
    
    operator = IngestLocalOperator(config)
    tables, metadata = operator.transform(None)
    table = tables[0]
    
    # Basic assertions
    assert table.num_rows > 0, "Should have ingested PDF files"
    assert "path" in table.column_names
    assert "binary_content" in table.column_names
    assert "content" not in table.column_names


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])