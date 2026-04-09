#!/usr/bin/env python3
"""
Unit tests for document_classifier operator.
Tests the operator with sample documents from the fixtures directory.
"""

import pytest
import pyarrow as pa
from pathlib import Path

from core.operators.quality.document_classifier import DocumentClassifierOperator


@pytest.mark.unit
@pytest.mark.skip(reason="Requires Ollama server running with granite4:latest model")
def test_document_classifier_basic():
    """Test the DocumentClassifierOperator with basic classification."""

    # Create sample documents with content
    sample_docs = [
        {
            "id": "doc1",
            "name": "invoice.txt",
            "content": "INVOICE\nInvoice Number: INV-001\nDate: 2024-01-15\nBill To: John Doe\nItem: Widget\nQuantity: 10\nPrice: $100\nTotal: $1000",
        },
        {
            "id": "doc2",
            "name": "contract.txt",
            "content": "CONTRACT AGREEMENT\nThis agreement is made between Party A and Party B.\nTerms and Conditions:\n1. Payment terms\n2. Delivery schedule\n3. Warranty provisions",
        },
        {
            "id": "doc3",
            "name": "receipt.txt",
            "content": "RECEIPT\nStore: ABC Store\nDate: 2024-01-20\nTransaction ID: TXN-12345\nItems purchased:\n- Coffee: $5.00\n- Sandwich: $8.00\nTotal: $13.00\nPayment Method: Credit Card",
        },
    ]

    # Create PyArrow table
    table = pa.table(
        {
            "id": [doc["id"] for doc in sample_docs],
            "name": [doc["name"] for doc in sample_docs],
            "content": [doc["content"] for doc in sample_docs],
        }
    )

    # Initialize operator
    config = {
        "provider": "ollama",
        "model_id": "granite4:latest",
        "document_types": {
            "invoice": "Business invoice with line items, totals, and payment terms",
            "receipt": "Payment receipt or transaction confirmation",
            "contract": "Legal contract or agreement document",
            "report": "Business or technical report",
            "letter": "Formal or informal letter",
        },
        "confidence_threshold": 7.0,
        "doc_column": "content",
        "output_column": "document_type",
        "include_confidence": True,
        "include_reasoning": True,
    }

    operator = DocumentClassifierOperator(config)

    # Transform the table
    result_tables, metadata = operator.transform(table)
    result_table = result_tables[0]

    # Assertions
    assert "document_type" in result_table.column_names, (
        "document_type column should exist"
    )
    assert "document_type_confidence" in result_table.column_names, (
        "confidence column should exist"
    )
    assert "document_type_reasoning" in result_table.column_names, (
        "reasoning column should exist"
    )

    # Check classifications
    doc_types = result_table["document_type"].to_pylist()
    confidences = result_table["document_type_confidence"].to_pylist()

    assert doc_types[0] == "invoice", "First document should be classified as invoice"
    assert doc_types[1] == "contract", (
        "Second document should be classified as contract"
    )
    assert doc_types[2] == "receipt", "Third document should be classified as receipt"

    # Check confidence scores
    for confidence in confidences:
        assert 1 <= confidence <= 10, (
            f"Confidence should be between 1 and 10, got {confidence}"
        )

    # Check metadata
    assert metadata["total_docs_count"] == 3, "Should have 3 documents"
    assert metadata["processed_docs"] == 3, "Should have processed 3 documents"


@pytest.mark.unit
@pytest.mark.skip(reason="Requires Ollama server running with granite4:latest model")
def test_document_classifier_without_content_column():
    """Test the DocumentClassifierOperator when content column doesn't exist (should fetch from binary)."""

    # Get test files
    fixtures_dir = (
        Path(__file__).parent.parent.parent.parent
        / "fixtures"
        / "customer_support_docs"
    )
    test_files = list(fixtures_dir.glob("*.txt"))[:2]

    if len(test_files) < 2:
        pytest.skip("Need at least 2 txt files for this test")

    # Prepare data without content column
    file_data = {"id": [], "name": [], "path": [], "binary_content": []}

    for file_path in test_files:
        with open(file_path, "rb") as f:
            binary_content = f.read()

        file_data["id"].append(str(file_path))
        file_data["name"].append(file_path.name)
        file_data["path"].append(str(file_path))
        file_data["binary_content"].append(binary_content)

    # Create PyArrow table without content column
    table = pa.table(file_data)

    # Initialize operator
    config = {
        "provider": "ollama",
        "model_id": "granite4:latest",
        "document_types": ["email", "letter", "form", "report", "other"],
        "confidence_threshold": 6.0,
        "doc_column": "content",
        "output_column": "document_type",
        "include_confidence": True,
        "include_reasoning": False,
    }

    operator = DocumentClassifierOperator(config)

    # Transform the table
    result_tables, metadata = operator.transform(table)
    result_table = result_tables[0]

    # Assertions
    assert "content" in result_table.column_names, "content column should be added"
    assert "document_type" in result_table.column_names, (
        "document_type column should exist"
    )
    assert "document_type_confidence" in result_table.column_names, (
        "confidence column should exist"
    )
    assert "document_type_reasoning" not in result_table.column_names, (
        "reasoning column should not exist"
    )

    # Check that content was extracted
    for idx in range(result_table.num_rows):
        content = result_table["content"][idx].as_py()
        assert content is not None, f"Content should not be None for row {idx}"
        assert len(content) > 0, f"Content should not be empty for row {idx}"

    # Check metadata
    assert metadata["processed_docs"] > 0, "Should have processed at least one document"


@pytest.mark.unit
def test_document_classifier_get_metadata():
    """Test the get_metadata method."""

    # Create operator with minimal config
    config = {
        "provider": "ollama",
        "model_id": "granite4:latest",
        "document_types": ["invoice", "receipt", "contract"],
    }

    operator = DocumentClassifierOperator(config)
    metadata = operator.get_metadata()

    # Assertions
    assert isinstance(metadata, dict), "Metadata should be a dictionary"
    assert "category" in metadata, "Metadata should have 'category' key"
    assert "features" in metadata, "Metadata should have 'features' key"
    assert "attributes" in metadata, "Metadata should have 'attributes' key"

    # Check features
    features = metadata["features"]
    assert "document_type" in features, "Features should include 'document_type'"
    assert "document_type_confidence" in features, "Features should include confidence"
    assert "document_type_reasoning" in features, "Features should include reasoning"

    # Check attributes
    attributes = metadata["attributes"]
    assert "provider" in attributes, "Attributes should include 'provider'"
    assert "model_id" in attributes, "Attributes should include 'model_id'"
    assert "document_types" in attributes, "Attributes should include 'document_types'"
    assert "confidence_threshold" in attributes, (
        "Attributes should include 'confidence_threshold'"
    )


@pytest.mark.unit
def test_document_classifier_validation():
    """Test the validation method."""

    # Test with valid config
    config = {
        "provider": "ollama",
        "model_id": "granite4:latest",
        "document_types": ["invoice", "receipt"],
    }

    operator = DocumentClassifierOperator(config)
    errors = []
    warnings = []
    operator.validate(errors, warnings, [])

    assert len(errors) == 0, "Should have no validation errors"


@pytest.mark.unit
def test_document_classifier_empty_table():
    """Test the DocumentClassifierOperator with empty table."""

    # Create empty table
    table = pa.table({"id": [], "name": [], "content": []})

    # Initialize operator
    config = {
        "provider": "ollama",
        "model_id": "granite4:latest",
        "document_types": ["invoice", "receipt"],
    }

    operator = DocumentClassifierOperator(config)

    # Transform the table
    result_tables, metadata = operator.transform(table)
    result_table = result_tables[0]

    # Assertions
    assert result_table.num_rows == 0, "Result table should be empty"
    assert metadata["total_docs_count"] == 0, "Should have 0 documents"


@pytest.mark.unit
def test_document_classifier_with_existing_classification():
    """Test that operator skips if document_type column already exists."""

    # Create table with existing document_type column
    table = pa.table(
        {
            "id": ["doc1"],
            "name": ["test.txt"],
            "content": ["Test content"],
            "document_type": ["invoice"],
        }
    )

    # Initialize operator
    config = {
        "provider": "ollama",
        "model_id": "granite4:latest",
        "document_types": ["invoice", "receipt"],
        "output_column": "document_type",
    }

    operator = DocumentClassifierOperator(config)

    # Transform the table
    result_tables, metadata = operator.transform(table)
    result_table = result_tables[0]

    # Assertions - should return original table unchanged
    assert result_table.num_rows == 1, "Should have 1 row"
    assert result_table["document_type"][0].as_py() == "invoice", (
        "Should keep existing classification"
    )


@pytest.mark.unit
@pytest.mark.skip(reason="Requires Ollama server running with granite4:latest model")
def test_document_classifier_list_document_types():
    """Test the DocumentClassifierOperator with list of document types (no descriptions)."""

    # Create sample document
    table = pa.table(
        {
            "id": ["doc1"],
            "name": ["invoice.txt"],
            "content": ["INVOICE\nInvoice Number: INV-001\nTotal: $1000"],
        }
    )

    # Initialize operator with list of types
    config = {
        "provider": "ollama",
        "model_id": "granite4:latest",
        "document_types": ["invoice", "receipt", "contract", "report"],
        "doc_column": "content",
        "output_column": "document_type",
        "include_confidence": True,
        "include_reasoning": False,
    }

    operator = DocumentClassifierOperator(config)

    # Transform the table
    result_tables, metadata = operator.transform(table)
    result_table = result_tables[0]

    # Assertions
    assert "document_type" in result_table.column_names, (
        "document_type column should exist"
    )
    assert result_table["document_type"][0].as_py() == "invoice", (
        "Should classify as invoice"
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

# Made with Bob
