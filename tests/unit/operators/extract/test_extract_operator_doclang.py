#!/usr/bin/env python3
"""
Unit tests for ExtractOperator doclang format support.
Tests verify that doclang format output matches expected values.
"""

from pathlib import Path

import pytest


def _validate_doclang_structure(doclang_xml: str) -> None:
    """
    Validate doclang XML structure and content.

    Checks:
    1. XML structure (tags, substantial content)
    2. Document elements (text, heading, table, location)
    3. Semantic content from invoice
    4. Structure counts with tolerance

    Args:
        doclang_xml: The doclang XML string to validate

    Raises:
        AssertionError: If validation fails
    """
    # 1. XML Structure
    assert doclang_xml.startswith("<doclang"), "DocLang should start with <doclang> tag"
    assert "</doclang>" in doclang_xml, "DocLang should contain closing </doclang> tag"
    assert len(doclang_xml) > 1000, f"DocLang content should be substantial (>1000 chars), got {len(doclang_xml)}"

    # 2. Document Elements
    assert "<text>" in doclang_xml, "DocLang should contain <text> elements"
    assert "<heading" in doclang_xml, "DocLang should contain <heading> elements"
    assert "<table>" in doclang_xml, "DocLang should contain <table> elements"
    assert "<location" in doclang_xml, "DocLang should contain <location> tags"

    # 3. Semantic Content (from invoice)
    expected_content = [
        "INVOICE NUMBER",
        "0298878900",
        "STRATFORD",
        "GRAND TOTAL",
        "15,163",
    ]
    for content in expected_content:
        assert content in doclang_xml, f"DocLang should contain '{content}'"

    # Date check: docling may encode the comma as a Unicode fullwidth comma (\uff0c)
    # depending on the version, so check the date parts independently
    assert "Feb 10" in doclang_xml, "DocLang should contain 'Feb 10'"
    assert "2020" in doclang_xml, "DocLang should contain '2020'"

    # 4. Structure Counts (with tolerance)
    text_count = doclang_xml.count("<text>")
    assert 15 <= text_count <= 30, f"Text element count should be between 15-30, got {text_count}"


@pytest.fixture(autouse=True)
def cleanup_after_test():
    """Module-local autouse fixture for memory cleanup after each test."""
    import gc

    yield

    # Explicit garbage collection after each test
    gc.collect()

    # Clear safe repository-owned caches/singletons if present
    try:
        from docpipe.integrations.docling.client import DoclingClient

        if hasattr(DoclingClient, "_instance"):
            DoclingClient._instance = None
    except (ImportError, AttributeError):
        pass


@pytest.mark.unit
@pytest.mark.slow
def test_extract_operator_doclang_format_exact_match():
    """Test that doclang format output has correct structure and content."""
    import pyarrow as pa

    from docpipe.core.operators.extract.extract_operator import ExtractOperator

    # Load test PDF
    test_file = Path("tests/fixtures/invoices/TR-INV_001_3_2.1.pdf")
    if not test_file.exists():
        pytest.skip(f"Test file not found: {test_file}")

    with Path(test_file).open("rb") as f:
        binary_content = f.read()

    # Create PyArrow table
    file_data = {
        "id": [str(test_file)],
        "name": [test_file.name],
        "path": [str(test_file)],
        "binary_content": [binary_content],
    }
    table = pa.table(file_data)

    # Initialize operator with doclang format
    config = {
        "text_extraction": {
            "provider": "docling_library",
            "doc_column": "doc_content",
            "provider_config": {
                "additional_formats": ["doclang"],
            },
        },
        "max_workers": 2,
    }

    operator = ExtractOperator(config=config)

    # Transform the table
    result_tables, metadata = operator.transform(table)
    result_table = result_tables[0]

    # Verify column exists
    assert "content_doclang" in result_table.column_names, "DocLang content column should exist"

    # Get actual doclang content
    actual_doclang = result_table["content_doclang"][0].as_py()

    # Validate structure using helper function
    _validate_doclang_structure(actual_doclang)

    # Verify metadata
    assert metadata["documents_in_scope"] == 1
    assert metadata["processed_docs"] == 1

    print("\nDocLang format test passed!")
    print(f"Content length: {len(actual_doclang)} characters")
    print(f"Text elements: {actual_doclang.count('<text>')}")
    print(f"Heading elements: {actual_doclang.count('<heading')}")
    print(f"Sample (first 300 chars):\n{actual_doclang[:300]}")


@pytest.mark.unit
@pytest.mark.slow
def test_extract_operator_doclang_structure_validation():
    """Test that doclang format contains expected structural elements."""
    import pyarrow as pa

    from docpipe.core.operators.extract.extract_operator import ExtractOperator

    # Load test PDF
    test_file = Path("tests/fixtures/invoices/TR-INV_001_3_2.1.pdf")
    if not test_file.exists():
        pytest.skip(f"Test file not found: {test_file}")

    with Path(test_file).open("rb") as f:
        binary_content = f.read()

    # Create PyArrow table
    file_data = {
        "id": [str(test_file)],
        "name": [test_file.name],
        "path": [str(test_file)],
        "binary_content": [binary_content],
    }
    table = pa.table(file_data)

    # Initialize operator
    config = {
        "text_extraction": {
            "provider": "docling_library",
            "doc_column": "doc_content",
            "provider_config": {
                "additional_formats": ["doclang"],
            },
        },
        "max_workers": 2,
    }

    operator = ExtractOperator(config=config)
    result_tables, _ = operator.transform(table)
    result_table = result_tables[0]

    # Get doclang content
    doclang_content = result_table["content_doclang"][0].as_py()

    # Verify XML structure (doclang tag may include version attribute e.g. <doclang version="0.6">)
    assert doclang_content.startswith("<doclang"), "Should start with <doclang> tag"
    assert "</doclang>" in doclang_content, "Should have closing tag"

    # Verify contains document elements
    assert "<text>" in doclang_content, "Should contain text elements"
    assert "<heading" in doclang_content, "Should contain heading elements"
    assert "<location" in doclang_content, "Should contain location tags"

    # Verify contains actual content from the invoice
    assert "INVOICE" in doclang_content, "Should contain invoice text"
    assert "STRATFORD" in doclang_content, "Should contain address text"

    print("\nDocLang structure validation passed!")
    print(f"Contains {doclang_content.count('<text>')} text elements")
    print(f"Contains {doclang_content.count('<heading')} heading elements")
    print(f"Contains {doclang_content.count('<location')} location tags")


@pytest.mark.unit
@pytest.mark.slow
def test_extract_operator_doclang_not_generated_by_default():
    """Test that doclang column is not created when not in additional_formats."""
    import pyarrow as pa

    from docpipe.core.operators.extract.extract_operator import ExtractOperator

    # Load test PDF
    test_file = Path("tests/fixtures/invoices/TR-INV_001_3_2.1.pdf")
    if not test_file.exists():
        pytest.skip(f"Test file not found: {test_file}")

    with Path(test_file).open("rb") as f:
        binary_content = f.read()

    # Create PyArrow table
    file_data = {
        "id": [str(test_file)],
        "name": [test_file.name],
        "path": [str(test_file)],
        "binary_content": [binary_content],
    }
    table = pa.table(file_data)

    # Initialize operator WITHOUT doclang in additional_formats
    config = {
        "text_extraction": {
            "provider": "docling_library",
            "doc_column": "doc_content",
            "provider_config": {
                "additional_formats": ["html", "json"],  # No doclang
            },
        },
        "max_workers": 2,
    }

    operator = ExtractOperator(config=config)
    result_tables, _ = operator.transform(table)
    result_table = result_tables[0]

    # Verify doclang column does NOT exist
    assert "content_doclang" not in result_table.column_names, "DocLang column should not exist when not requested"
    assert "content_html" in result_table.column_names, "HTML column should exist"
    assert "content_json" in result_table.column_names, "JSON column should exist"

    print("\nDocLang not generated by default - test passed!")
