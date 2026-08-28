#!/usr/bin/env python3
"""
Unit tests for document_class_utils module.
Tests conversion of document class JSON to Docling templates.
"""

import json
from pathlib import Path

import pytest

from docpipe.utils.document_class_utils import DocumentClassUtils


@pytest.fixture
def invoice_doc_class_path():
    """Path to invoice document class JSON."""
    return (
        Path(__file__).parent.parent.parent.parent.parent
        / "src"
        / "docpipe"
        / "core"
        / "document_classes"
        / "invoice.json"
    )


@pytest.fixture
def purchase_order_doc_class_path():
    """Path to purchase order document class JSON."""
    return (
        Path(__file__).parent.parent.parent.parent.parent
        / "src"
        / "docpipe"
        / "core"
        / "document_classes"
        / "purchase_order.json"
    )


def test_load_document_class(invoice_doc_class_path):
    """Test loading document class from JSON file."""
    doc_class = DocumentClassUtils.load_document_class(invoice_doc_class_path)

    assert "document_class_name" in doc_class
    assert doc_class["document_class_name"] == "Invoice"
    assert "document_class_schema" in doc_class
    assert "document" in doc_class["document_class_schema"]
    assert "target_tables" in doc_class["document_class_schema"]


def test_generate_docling_template_invoice(invoice_doc_class_path):
    """Test generating Docling template from invoice document class."""
    template = DocumentClassUtils.generate_docling_template(invoice_doc_class_path)

    # Check that template is generated
    assert isinstance(template, dict)
    assert len(template) > 0

    # Check expected fields exist
    assert "invoice_id" in template  # Note: invoice.json uses invoice_id not invoice_number
    assert "invoice_date" in template
    assert "customer_name" in template
    assert "vendor_name" in template
    assert "sub_total" in template
    assert "tax" in template
    assert "total" in template

    # Check types are correct based on target_tables
    assert template["invoice_id"] == "string"
    assert template["invoice_date"] == "string"  # date -> string for Docling
    assert template["sub_total"] == "float"  # decimal -> float
    assert template["tax"] == "float"
    assert template["total"] == "float"

    # Check nested line_items
    assert "line_items" in template
    assert isinstance(template["line_items"], dict)
    assert "amount" in template["line_items"]
    assert "description" in template["line_items"]
    assert "quantity" in template["line_items"]
    assert template["line_items"]["amount"] == "float"
    assert template["line_items"]["quantity"] == "int"  # long -> int


def test_generate_docling_template_without_nested(invoice_doc_class_path):
    """Test generating template without nested fields."""
    template = DocumentClassUtils.generate_docling_template(invoice_doc_class_path, include_nested=False)

    # Check that nested fields are excluded
    assert "line_items" not in template or not isinstance(template.get("line_items"), dict)

    # But top-level fields should still exist
    assert "invoice_id" in template
    assert "total" in template


def test_generate_docling_template_with_max_fields(invoice_doc_class_path):
    """Test limiting number of fields in template."""
    max_fields = 5
    template = DocumentClassUtils.generate_docling_template(invoice_doc_class_path, max_fields=max_fields)

    # Count only top-level fields
    _ = [k for k, v in template.items() if not isinstance(v, dict)]
    assert len(template) <= max_fields


def test_generate_template_with_examples(invoice_doc_class_path):
    """Test generating template with examples and descriptions."""
    result = DocumentClassUtils.generate_template_with_examples(invoice_doc_class_path)

    # Check structure
    assert "template" in result
    assert "examples" in result
    assert "descriptions" in result
    assert "document_type" in result
    assert "document_description" in result

    # Check template
    assert isinstance(result["template"], dict)
    assert len(result["template"]) > 0

    # Check examples
    assert isinstance(result["examples"], dict)
    assert "invoice_id" in result["examples"]
    assert isinstance(result["examples"]["invoice_id"], list)

    # Check descriptions
    assert isinstance(result["descriptions"], dict)
    assert "invoice_id" in result["descriptions"]

    # Check document metadata
    assert result["document_type"] == "Invoice"
    assert len(result["document_description"]) > 0


def test_generate_docling_template_purchase_order(purchase_order_doc_class_path):
    """Test generating template from purchase order document class."""
    template = DocumentClassUtils.generate_docling_template(purchase_order_doc_class_path)

    # Check purchase order specific fields
    assert "purchase_order_number" in template
    assert "purchase_order_date" in template
    assert "purchase_order_requested_delivery_date" in template
    assert "supplier_name" in template

    # Check types
    assert template["purchase_order_number"] == "string"
    assert template["purchase_order_date"] == "string"


def test_list_available_document_classes():
    """Test listing all available document classes."""
    doc_classes = DocumentClassUtils.list_available_document_classes()

    # Should find multiple document classes
    assert len(doc_classes) > 0

    # Check structure
    for doc_class in doc_classes:
        assert "file" in doc_class
        assert "name" in doc_class
        assert "id" in doc_class
        assert "description" in doc_class

    # Check that Invoice and Purchase Order are in the list
    names = [dc["name"] for dc in doc_classes]
    assert "Invoice" in names
    assert "Purchase Order" in names


def test_direct_class_method(invoice_doc_class_path):
    """Test using class method directly."""
    template = DocumentClassUtils.generate_docling_template(invoice_doc_class_path)

    assert isinstance(template, dict)
    assert len(template) > 0
    assert "invoice_id" in template


def test_type_mapping():
    """Test that type mapping is correct."""
    mapping = DocumentClassUtils.TYPE_MAPPING

    # Check expected mappings
    assert mapping["string"] == "string"
    assert mapping["date"] == "string"
    assert mapping["decimal"] == "float"
    assert mapping["float"] == "float"
    assert mapping["long"] == "int"
    assert mapping["int"] == "int"
    assert mapping["boolean"] == "boolean"


def test_nonexistent_file():
    """Test handling of nonexistent file."""
    with pytest.raises(FileNotFoundError):
        DocumentClassUtils.load_document_class("nonexistent.json")


def test_print_template_example(invoice_doc_class_path):
    """Print an example template for manual verification."""
    template = DocumentClassUtils.generate_docling_template(invoice_doc_class_path, max_fields=10)

    print("\n=== Generated Docling Template (Invoice, first 10 fields) ===")
    print(json.dumps(template, indent=2))

    result = DocumentClassUtils.generate_template_with_examples(invoice_doc_class_path)

    print("\n=== Template with Examples ===")
    print(f"Document Type: {result['document_type']}")
    print(f"Description: {result['document_description'][:100]}...")
    print("\nSample Fields with Examples:")
    for field_name in list(result["examples"].keys())[:5]:
        print(f"  {field_name}:")
        print(f"    Type: {result['template'].get(field_name, 'N/A')}")
        print(f"    Examples: {result['examples'][field_name]}")
        print(f"    Description: {result['descriptions'].get(field_name, 'N/A')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
