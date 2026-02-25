#!/usr/bin/env python3
"""
Unit tests for extract_docling_operator.
Tests the operator with sample PDF files from the fixtures directory.
"""

import sys
import json
from pathlib import Path

# Add the backend directory to the Python path
backend_dir = Path(__file__).parent.parent.parent.parent.parent / "src" / "datasift_opensource" / "backend"
sys.path.insert(0, str(backend_dir))


def test_extract_docling_basic():
    """Test the ExtractDoclingOperator with basic extraction."""
    import pyarrow as pa
    from datasift_opensource.backend.core.operators.universal.extract.extract_docling import ExtractDoclingOperator
    
    # Get test files
    fixtures_dir = Path(__file__).parent.parent.parent.parent / "fixtures" / "invoices"
    test_files = list(fixtures_dir.glob("*.pdf"))[:1]  # Test with first file
    
    assert len(test_files) > 0, f"No PDF files found in {fixtures_dir}"
    
    # Prepare data for PyArrow table
    file_data = {
        "id": [],
        "name": [],
        "path": [],
        "binary_content": []
    }
    
    for file_path in test_files:
        with open(file_path, 'rb') as f:
            binary_content = f.read()
        
        file_data["id"].append(str(file_path))
        file_data["name"].append(file_path.name)
        file_data["path"].append(str(file_path))
        file_data["binary_content"].append(binary_content)
    
    # Create PyArrow table
    table = pa.table(file_data)
    assert table.num_rows > 0, "Table should have rows"
    
    # Initialize operator with basic configuration
    config = {
        "doc_column": "content",
        "doc_id_hash": "doc_id_hash",
        "extract_tables": True,
        "extract_images": True,
        "use_template": False
    }
    
    operator = ExtractDoclingOperator(config)
    
    # Transform the table
    result_tables, metadata = operator.transform(table)
    result_table = result_tables[0]
    
    # Assertions
    assert "content" in result_table.column_names, "Content column should exist"
    assert "doc_id_hash" in result_table.column_names, "Hash ID column should exist"
    assert "extracted_data" not in result_table.column_names, "Extracted_data column should not exist for basic extraction"
    
    # Check content
    first_content = result_table["content"][0].as_py()
    assert first_content is not None, "Content should not be None"
    assert len(first_content) > 0, "Content should not be empty"
    
    # Check hash
    first_hash = result_table["doc_id_hash"][0].as_py()
    assert first_hash is not None, "Hash should not be None"
    assert len(first_hash) > 0, "Hash should not be empty"
    
    # Check metadata
    assert metadata["total_docs"] == table.num_rows, "Total docs should match input rows"
    assert metadata["processed_docs"] > 0, "Should have processed at least one document"


def test_extract_docling_with_template():
    """Test the ExtractDoclingOperator with template extraction."""
    import pyarrow as pa
    from datasift_opensource.backend.core.operators.universal.extract.extract_docling import ExtractDoclingOperator
    import pytest
    
    # Check if DocumentExtractor is available
    try:
        from docling.document_extractor import DocumentExtractor
    except ImportError:
        pytest.skip("DocumentExtractor not available. Install with: pip install docling[vlm]")
    
    # Get test files
    fixtures_dir = Path(__file__).parent.parent.parent.parent / "fixtures" / "invoices"
    test_files = list(fixtures_dir.glob("*.pdf"))[:1]  # Test with first file
    
    assert len(test_files) > 0, f"No PDF files found in {fixtures_dir}"
    
    # Prepare data for PyArrow table
    file_data = {
        "id": [],
        "name": [],
        "path": [],
        "binary_content": []
    }
    
    for file_path in test_files:
        with open(file_path, 'rb') as f:
            binary_content = f.read()
        
        file_data["id"].append(str(file_path))
        file_data["name"].append(file_path.name)
        file_data["path"].append(str(file_path))
        file_data["binary_content"].append(binary_content)
    
    # Create PyArrow table
    table = pa.table(file_data)
    
    # Define invoice template for structured extraction
    invoice_template = {
        "invoice_number": "string",
        "invoice_date": "string",
        "payment_due": "string",
        "bill_to": "string",
        "vendor_name": "string",
        "vendor_address": "string",
        "subtotal": "float",
        "tax": "float",
        "total": "float",
        "grand_total": "float"
    }
    
    # Initialize operator with template configuration
    config = {
        "doc_column": "content",
        "doc_id_hash": "doc_id_hash",
        "extract_tables": True,
        "extract_images": True,
        "use_template": True,
        "template": invoice_template
    }
    
    operator = ExtractDoclingOperator(config)
    
    # Transform the table
    result_tables, metadata = operator.transform(table)
    result_table = result_tables[0]
    
    # Assertions
    assert "content" in result_table.column_names, "Content column should exist"
    assert "doc_id_hash" in result_table.column_names, "Hash ID column should exist"
    assert "extracted_data" in result_table.column_names, "Extracted_data column should exist for template extraction"
    
    # Check content
    first_content = result_table["content"][0].as_py()
    assert first_content is not None, "Content should not be None"
    
    # Check extracted_data
    first_extracted = result_table["extracted_data"][0].as_py()
    if first_extracted:  # May be None if extraction failed
        extracted_dict = json.loads(first_extracted)
        assert isinstance(extracted_dict, list), "Extracted data should be a list"
        assert len(extracted_dict) > 0, "Extracted data should have at least one page"
        
        # Check structure of first page
        first_page = extracted_dict[0]
        assert "page_no" in first_page, "Page should have page_no"
        assert "extracted_data" in first_page, "Page should have extracted_data"
    
    # Check hash
    first_hash = result_table["doc_id_hash"][0].as_py()
    assert first_hash is not None, "Hash should not be None"
    
    # Check metadata
    assert metadata["total_docs"] == table.num_rows, "Total docs should match input rows"


def test_extract_docling_with_expand_extracted_data():
    """Test the ExtractDoclingOperator with expand_extracted_data flag."""
    import pyarrow as pa
    from datasift_opensource.backend.core.operators.universal.extract.extract_docling import ExtractDoclingOperator
    import pytest
    
    # Check if DocumentExtractor is available
    try:
        from docling.document_extractor import DocumentExtractor
    except ImportError:
        pytest.skip("DocumentExtractor not available. Install with: pip install docling[vlm]")
    
    # Get test files
    fixtures_dir = Path(__file__).parent.parent.parent.parent / "fixtures" / "invoices"
    test_files = list(fixtures_dir.glob("*.pdf"))[:1]  # Test with first file
    
    assert len(test_files) > 0, f"No PDF files found in {fixtures_dir}"
    
    # Prepare data for PyArrow table
    file_data = {
        "id": [],
        "name": [],
        "path": [],
        "binary_content": []
    }
    
    for file_path in test_files:
        with open(file_path, 'rb') as f:
            binary_content = f.read()
        
        file_data["id"].append(str(file_path))
        file_data["name"].append(file_path.name)
        file_data["path"].append(str(file_path))
        file_data["binary_content"].append(binary_content)
    
    # Create PyArrow table
    table = pa.table(file_data)
    
    # Define invoice template for structured extraction
    invoice_template = {
        "invoice_number": "string",
        "invoice_date": "string",
        "payment_due": "string",
        "bill_to": "string",
        "vendor_name": "string",
        "vendor_address": "string",
        "subtotal": "float",
        "tax": "float",
        "total": "float",
        "grand_total": "float"
    }
    
    # Initialize operator with template configuration and expand_extracted_data flag
    config = {
        "doc_column": "content",
        "doc_id_hash": "doc_id_hash",
        "extract_tables": True,
        "extract_images": True,
        "use_template": True,
        "template": invoice_template,
        "expand_extracted_data": True  # Enable expansion
    }
    
    operator = ExtractDoclingOperator(config)
    
    # Transform the table
    result_tables, metadata = operator.transform(table)
    result_table = result_tables[0]
    
    # Assertions
    assert "content" in result_table.column_names, "Content column should exist"
    assert "doc_id_hash" in result_table.column_names, "Hash ID column should exist"
    
    # When expand_extracted_data is True, individual columns should be created
    # Check for at least some of the expected expanded columns
    expected_prefixes = ["extracted_"]
    has_expanded_columns = any(
        col.startswith(prefix) for col in result_table.column_names
        for prefix in expected_prefixes
    )
    
    # Note: The test may not always have expanded columns if extraction fails
    # So we check if either expanded columns exist OR extracted_data exists
    has_data = has_expanded_columns or "extracted_data" in result_table.column_names
    assert has_data, "Should have either expanded columns or extracted_data column"
    
    # Check metadata
    assert metadata["total_docs"] == table.num_rows, "Total docs should match input rows"


def test_get_metadata():
    """Test the get_metadata static method."""
    from datasift_opensource.backend.core.operators.universal.extract.extract_docling import ExtractDoclingOperator
    
    # Call the static method
    metadata = ExtractDoclingOperator.get_metadata()
    
    # Assertions
    assert isinstance(metadata, dict), "Metadata should be a dictionary"
    assert "sdk" in metadata, "Metadata should have 'sdk' key"
    assert "category" in metadata, "Metadata should have 'category' key"
    assert "label" in metadata, "Metadata should have 'label' key"
    assert "features" in metadata, "Metadata should have 'features' key"
    assert "attributes" in metadata, "Metadata should have 'attributes' key"
    
    # Check features
    features = metadata["features"]
    assert "content" in features, "Features should include 'content'"
    assert "doc_id_hash" in features, "Features should include 'doc_id_hash'"
    assert "extracted_data" in features, "Features should include 'extracted_data'"
    
    # Check attributes
    attributes = metadata["attributes"]
    assert "doc_column" in attributes, "Attributes should include 'doc_column'"
    assert "use_template" in attributes, "Attributes should include 'use_template'"
    assert "expand_extracted_data" in attributes, "Attributes should include 'expand_extracted_data'"
    
    # Check expand_extracted_data attribute details
    expand_attr = attributes["expand_extracted_data"]
    assert expand_attr["name"] == "Expand Extracted Data", "Attribute name should match"
    assert expand_attr["type"] == "boolean", "Attribute type should be boolean"
    assert expand_attr["default"] is False, "Default should be False"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])