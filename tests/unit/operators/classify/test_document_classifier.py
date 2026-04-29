#!/usr/bin/env python3
"""
Unit tests for document_classifier operator.
Tests the operator with sample documents from the fixtures directory.
"""

import json
from pathlib import Path
from unittest.mock import Mock, patch

import pyarrow as pa
import pytest

from datasift.core.operators.quality.document_classifier import DocumentClassifierOperator
from datasift.exceptions.datasift_exceptions import DatasiftException


@pytest.mark.unit
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
        "provider_config": {},  # Empty for ollama (uses defaults)
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

    # Mock responses for each document
    mock_responses = [
        json.dumps(
            {
                "document_type": "invoice",
                "confidence": 9,
                "reasoning": "Document contains invoice number, date, bill to information, line items with quantities and prices, and total amount.",
            }
        ),
        json.dumps(
            {
                "document_type": "contract",
                "confidence": 8,
                "reasoning": "Document is a legal agreement between two parties with terms and conditions including payment terms, delivery schedule, and warranty provisions.",
            }
        ),
        json.dumps(
            {
                "document_type": "receipt",
                "confidence": 9,
                "reasoning": "Document is a payment receipt with store name, transaction ID, itemized purchases with prices, total amount, and payment method.",
            }
        ),
    ]

    # Mock the Ollama client
    with patch("ollama.Client") as mock_client_class:
        mock_client = Mock()
        # Mock the chat method to return different responses for each call
        mock_client.chat.side_effect = [{"message": {"content": resp}} for resp in mock_responses]
        # Mock list method for validation
        mock_client.list.return_value = Mock(models=[Mock(model="granite4:latest")])
        mock_client_class.return_value = mock_client

        operator = DocumentClassifierOperator(config)

        # Transform the table
        result_tables, metadata = operator.transform(table)
        result_table = result_tables[0]

        # Assertions
        assert "document_type" in result_table.column_names, "document_type column should exist"
        assert "document_type_confidence" in result_table.column_names, "confidence column should exist"
        assert "document_type_reasoning" in result_table.column_names, "reasoning column should exist"

        # Check classifications
        doc_types = result_table["document_type"].to_pylist()
        confidences = result_table["document_type_confidence"].to_pylist()

        assert doc_types[0] == "invoice", "First document should be classified as invoice"
        assert doc_types[1] == "contract", "Second document should be classified as contract"
        assert doc_types[2] == "receipt", "Third document should be classified as receipt"

        # Check confidence scores
        for confidence in confidences:
            assert 1 <= confidence <= 10, f"Confidence should be between 1 and 10, got {confidence}"

        # Check metadata
        assert metadata["total_docs_count"] == 3, "Should have 3 documents"
        assert metadata["processed_docs"] == 3, "Should have processed 3 documents"


@pytest.mark.unit
def test_document_classifier_without_content_column():
    """Test the DocumentClassifierOperator when content column doesn't exist (should fetch from binary)."""

    # Get test files
    fixtures_dir = Path(__file__).parent.parent.parent.parent / "fixtures" / "customer_support_docs"
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
        "provider_config": {},
        "model_id": "granite4:latest",
        "document_types": ["email", "letter", "form", "report", "other"],
        "confidence_threshold": 6.0,
        "doc_column": "content",
        "output_column": "document_type",
        "include_confidence": True,
        "include_reasoning": False,
    }

    # Mock responses for documents
    mock_responses = [
        json.dumps(
            {
                "document_type": "email",
                "confidence": 8,
                "reasoning": "Document appears to be an email communication.",
            }
        ),
        json.dumps(
            {
                "document_type": "letter",
                "confidence": 7,
                "reasoning": "Document appears to be a formal letter.",
            }
        ),
    ]

    # Mock the Ollama client
    with patch("ollama.Client") as mock_client_class:
        mock_client = Mock()
        # Mock the chat method to return different responses for each call
        mock_client.chat.side_effect = [{"message": {"content": resp}} for resp in mock_responses]
        # Mock list method for validation
        mock_client.list.return_value = Mock(models=[Mock(model="granite4:latest")])
        mock_client_class.return_value = mock_client

        operator = DocumentClassifierOperator(config)

        # Transform the table
        result_tables, metadata = operator.transform(table)
        result_table = result_tables[0]

        # Assertions
        assert "content" in result_table.column_names, "content column should be added"
        assert "document_type" in result_table.column_names, "document_type column should exist"
        assert "document_type_confidence" in result_table.column_names, "confidence column should exist"
        assert "document_type_reasoning" not in result_table.column_names, "reasoning column should not exist"

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
        "provider_config": {},
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
    assert "confidence_threshold" in attributes, "Attributes should include 'confidence_threshold'"


@pytest.mark.unit
def test_document_classifier_validation():
    """Test the validation method."""

    # Test with valid config
    config = {
        "provider": "ollama",
        "provider_config": {},
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
        "provider_config": {},
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
        "provider_config": {},
        "model_id": "granite4:latest",
        "document_types": ["invoice", "receipt"],
        "output_column": "document_type",
    }

    operator = DocumentClassifierOperator(config)

    # Transform the table
    result_tables, _ = operator.transform(table)
    result_table = result_tables[0]

    # Assertions - should return original table unchanged
    assert result_table.num_rows == 1, "Should have 1 row"
    assert result_table["document_type"][0].as_py() == "invoice", "Should keep existing classification"


@pytest.mark.unit
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
        "provider_config": {},
        "model_id": "granite4:latest",
        "document_types": ["invoice", "receipt", "contract", "report"],
        "doc_column": "content",
        "output_column": "document_type",
        "include_confidence": True,
        "include_reasoning": False,
    }

    # Mock response for the document
    mock_response = json.dumps(
        {
            "document_type": "invoice",
            "confidence": 9,
            "reasoning": "Document contains invoice number and total amount.",
        }
    )

    # Mock the Ollama client
    with patch("ollama.Client") as mock_client_class:
        mock_client = Mock()
        # Mock the chat method
        mock_client.chat.return_value = {"message": {"content": mock_response}}
        # Mock list method for validation
        mock_client.list.return_value = Mock(models=[Mock(model="granite4:latest")])
        mock_client_class.return_value = mock_client

        operator = DocumentClassifierOperator(config)

        # Transform the table
        result_tables, _ = operator.transform(table)
        result_table = result_tables[0]

        # Assertions
        assert "document_type" in result_table.column_names, "document_type column should exist"
        assert result_table["document_type"][0].as_py() == "invoice", "Should classify as invoice"


@pytest.mark.unit
def test_document_classifier_watsonx_provider_config():
    """Test DocumentClassifierOperator with watsonx provider configuration."""

    # Create sample document
    table = pa.table(
        {
            "id": ["doc1"],
            "name": ["invoice.txt"],
            "content": ["INVOICE\nInvoice Number: INV-001\nTotal: $1000"],
        }
    )

    # Initialize operator with watsonx provider
    config = {
        "provider": "watsonx",
        "provider_config": {
            "api_base": "https://us-south.ml.cloud.ibm.com/ml/v1",
            "api_key": "test-api-key",  # pragma: allowlist secret
            "container_id": "test-project-id",
            "container_kind": "project",
            "request_timeout": 120,
        },
        "model_id": "ibm/granite-3-8b-instruct",
        "document_types": ["invoice", "receipt", "contract"],
        "doc_column": "content",
        "output_column": "document_type",
        "include_confidence": True,
        "include_reasoning": True,
    }

    # Mock response in OpenAI Chat Completions API format (verified from actual watsonx response)
    mock_response = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "document_type": "invoice",
                            "confidence": 10,
                            "reasoning": "Document contains invoice number and total amount.",
                        }
                    )
                }
            }
        ]
    }

    # Mock RestClient for watsonx API calls
    with patch("datasift.core.operators.quality.document_classifier.RestClient") as mock_rest_class:
        mock_rest_instance = Mock()
        mock_rest_instance.call_rest_json.return_value = mock_response
        mock_rest_class.return_value = mock_rest_instance

        operator = DocumentClassifierOperator(config)

        # Verify configuration was set correctly
        assert operator.provider == "watsonx"
        assert operator.model_id == "ibm/granite-3-8b-instruct"
        assert operator.api_base == "https://us-south.ml.cloud.ibm.com/ml/v1"
        assert operator.container_id == "test-project-id"
        assert operator.container_kind == "project"
        assert operator.request_timeout == 120

        # Transform the table
        result_tables, metadata = operator.transform(table)
        result_table = result_tables[0]

        # Assertions
        assert "document_type" in result_table.column_names
        assert "document_type_confidence" in result_table.column_names
        assert "document_type_reasoning" in result_table.column_names
        assert result_table["document_type"][0].as_py() == "invoice"
        assert result_table["document_type_confidence"][0].as_py() == 10
        assert metadata["processed_docs"] == 1


@pytest.mark.unit
def test_document_classifier_watsonx_missing_model_id():
    """Test that watsonx provider requires model_id."""

    config = {
        "provider": "watsonx",
        "provider_config": {
            "api_base": "https://us-south.ml.cloud.ibm.com/ml/v1",
            "api_key": "test-api-key",  # pragma: allowlist secret
            "container_id": "test-project-id",
            "container_kind": "project",
        },
        "document_types": ["invoice", "receipt"],
        # model_id is missing - should raise exception
    }

    with pytest.raises(DatasiftException, match="model_id is required for watsonx provider"):
        DocumentClassifierOperator(config)


@pytest.mark.unit
def test_document_classifier_watsonx_missing_api_base():
    """Test that watsonx provider requires api_base in provider_config."""

    config = {
        "provider": "watsonx",
        "provider_config": {
            # api_base is missing
            "api_key": "test-api-key",  # pragma: allowlist secret
            "container_id": "test-project-id",
        },
        "model_id": "ibm/granite-3-8b-instruct",
        "document_types": ["invoice", "receipt"],
    }

    with pytest.raises(
        DatasiftException,
        match="api_base is required in provider_config for watsonx provider",
    ):
        DocumentClassifierOperator(config)


@pytest.mark.unit
def test_document_classifier_watsonx_missing_api_key():
    """Test that watsonx provider requires api_key in provider_config."""

    config = {
        "provider": "watsonx",
        "provider_config": {
            "api_base": "https://us-south.ml.cloud.ibm.com/ml/v1",
            # api_key is missing
            "container_id": "test-project-id",
        },
        "model_id": "ibm/granite-3-8b-instruct",
        "document_types": ["invoice", "receipt"],
    }

    with pytest.raises(
        DatasiftException,
        match="api_key is required in provider_config for watsonx provider",
    ):
        DocumentClassifierOperator(config)


@pytest.mark.unit
def test_document_classifier_watsonx_missing_container_id():
    """Test that watsonx provider requires container_id in provider_config."""

    config = {
        "provider": "watsonx",
        "provider_config": {
            "api_base": "https://us-south.ml.cloud.ibm.com/ml/v1",
            "api_key": "test-api-key",  # pragma: allowlist secret
            # container_id is missing
        },
        "model_id": "ibm/granite-3-8b-instruct",
        "document_types": ["invoice", "receipt"],
    }

    with pytest.raises(
        DatasiftException,
        match="container_id is required in provider_config for watsonx provider",
    ):
        DocumentClassifierOperator(config)


@pytest.mark.unit
def test_document_classifier_watsonx_validation():
    """Test validation method for watsonx provider."""

    # Test with valid config
    config = {
        "provider": "watsonx",
        "provider_config": {
            "api_base": "https://us-south.ml.cloud.ibm.com/ml/v1",
            "api_key": "test-api-key",  # pragma: allowlist secret
            "container_id": "test-project-id",
        },
        "model_id": "ibm/granite-3-8b-instruct",
        "document_types": ["invoice", "receipt"],
    }

    operator = DocumentClassifierOperator(config)
    errors = []
    warnings = []
    operator.validate(errors, warnings, [])

    assert len(errors) == 0, "Should have no validation errors with valid config"


@pytest.mark.unit
def test_document_classifier_provider_config_empty_for_ollama():
    """Test that ollama provider works with empty provider_config."""

    table = pa.table(
        {
            "id": ["doc1"],
            "name": ["test.txt"],
            "content": ["Test content"],
        }
    )

    config = {
        "provider": "ollama",
        "provider_config": {},  # Empty config is fine for ollama
        "model_id": "granite4:latest",
        "document_types": ["invoice", "receipt"],
    }

    mock_response = json.dumps(
        {
            "document_type": "invoice",
            "confidence": 8,
            "reasoning": "Test reasoning",
        }
    )

    with patch("ollama.Client") as mock_client_class:
        mock_client = Mock()
        mock_client.chat.return_value = {"message": {"content": mock_response}}
        mock_client.list.return_value = Mock(models=[Mock(model="granite4:latest")])
        mock_client_class.return_value = mock_client

        operator = DocumentClassifierOperator(config)
        result_tables, metadata = operator.transform(table)

        assert metadata["processed_docs"] == 1
        assert result_tables[0]["document_type"][0].as_py() == "invoice"


@pytest.mark.unit
def test_document_classifier_watsonx_default_container_kind():
    """Test that watsonx provider defaults container_kind to 'project'."""

    config = {
        "provider": "watsonx",
        "provider_config": {
            "api_base": "https://us-south.ml.cloud.ibm.com/ml/v1",
            "api_key": "test-api-key",  # pragma: allowlist secret
            "container_id": "test-project-id",
            # container_kind not specified - should default to "project"
        },
        "model_id": "ibm/granite-3-8b-instruct",
        "document_types": ["invoice"],
    }

    operator = DocumentClassifierOperator(config)
    assert operator.container_kind == "project", "Should default to 'project'"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
