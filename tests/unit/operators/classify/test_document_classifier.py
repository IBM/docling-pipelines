#!/usr/bin/env python3
"""
Unit tests for document_classifier operator.
Tests the operator with sample documents from the fixtures directory.
"""

import json
from pathlib import Path
from unittest.mock import patch

import pyarrow as pa
import pytest

from datasift.core.operators.quality.classification.document_classifier import DocumentClassifierOperator
from datasift.exceptions.datasift_exceptions import DatasiftException, ExternalServiceError


@pytest.mark.unit
@patch("datasift.integrations.ollama.client.OllamaClient.is_server_running", return_value=True)
@patch("datasift.integrations.ollama.client.OllamaClient.is_model_available", return_value=True)
def test_document_classifier_basic(mock_model, mock_server):
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

    with patch(
        "datasift.core.operators.quality.classification.adapters.outbound.ollama_adapter.OllamaClient.run",
        side_effect=mock_responses,
    ):
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

    with (
        patch(
            "datasift.integrations.ollama.client.OllamaClient.is_server_running",
            return_value=True,
        ),
        patch(
            "datasift.integrations.ollama.client.OllamaClient.is_model_available",
            return_value=True,
        ),
        patch(
            "datasift.core.operators.quality.classification.adapters.outbound.ollama_adapter.OllamaClient.run",
            side_effect=mock_responses,
        ),
    ):
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
@patch("datasift.integrations.ollama.client.OllamaClient.is_server_running", return_value=True)
@patch("datasift.integrations.ollama.client.OllamaClient.is_model_available", return_value=True)
def test_document_classifier_get_metadata(mock_model, mock_server):
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
@patch("datasift.integrations.ollama.client.OllamaClient.is_server_running", return_value=True)
@patch("datasift.integrations.ollama.client.OllamaClient.is_model_available", return_value=True)
def test_document_classifier_validation(mock_model, mock_server):
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
@patch("datasift.integrations.ollama.client.OllamaClient.is_server_running", return_value=True)
@patch("datasift.integrations.ollama.client.OllamaClient.is_model_available", return_value=True)
def test_document_classifier_empty_table(mock_model, mock_server):
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
@patch("datasift.integrations.ollama.client.OllamaClient.is_server_running", return_value=True)
@patch("datasift.integrations.ollama.client.OllamaClient.is_model_available", return_value=True)
def test_document_classifier_with_existing_classification(mock_model, mock_server):
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
    result_tables, _metadata = operator.transform(table)
    result_table = result_tables[0]

    # Assertions - should return original table unchanged
    assert result_table.num_rows == 1, "Should have 1 row"
    assert result_table["document_type"][0].as_py() == "invoice", "Should keep existing classification"


@pytest.mark.unit
@patch("datasift.integrations.ollama.client.OllamaClient.is_server_running", return_value=True)
@patch("datasift.integrations.ollama.client.OllamaClient.is_model_available", return_value=True)
def test_document_classifier_list_document_types(mock_model, mock_server):
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

    with patch(
        "datasift.core.operators.quality.classification.adapters.outbound.ollama_adapter.OllamaClient.run",
        return_value=mock_response,
    ):
        operator = DocumentClassifierOperator(config)

        # Transform the table
        result_tables, _metadata = operator.transform(table)
        result_table = result_tables[0]

        # Assertions
        assert "document_type" in result_table.column_names, "document_type column should exist"
        assert result_table["document_type"][0].as_py() == "invoice", "Should classify as invoice"


@pytest.mark.unit
class TestOllamaClassificationAdapter:
    """Test class for Ollama classification adapter."""

    def test_ollama_adapter_basic_classification(self):
        """Test Ollama adapter with basic classification."""
        sample_docs = [
            {
                "id": "doc1",
                "name": "invoice.txt",
                "content": "INVOICE\nInvoice Number: INV-001\nTotal: $1000",
            }
        ]

        table = pa.table(
            {
                "id": [doc["id"] for doc in sample_docs],
                "name": [doc["name"] for doc in sample_docs],
                "content": [doc["content"] for doc in sample_docs],
            }
        )

        config = {
            "provider": "ollama",
            "model_id": "granite4:latest",
            "document_types": ["invoice", "receipt", "contract"],
            "confidence_threshold": 7.0,
            "doc_column": "content",
            "output_column": "document_type",
            "include_confidence": True,
            "include_reasoning": True,
        }

        mock_response = json.dumps(
            {
                "document_type": "invoice",
                "confidence": 9,
                "reasoning": "Document contains invoice number and total amount.",
            }
        )

        with (
            patch(
                "datasift.integrations.ollama.client.OllamaClient.is_server_running",
                return_value=True,
            ),
            patch(
                "datasift.integrations.ollama.client.OllamaClient.is_model_available",
                return_value=True,
            ),
            patch(
                "datasift.core.operators.quality.classification.adapters.outbound.ollama_adapter.OllamaClient.run",
                return_value=mock_response,
            ),
        ):
            operator = DocumentClassifierOperator(config)
            result_tables, metadata = operator.transform(table)
            result_table = result_tables[0]

            assert "document_type" in result_table.column_names
            assert result_table["document_type"][0].as_py() == "invoice"
            assert metadata["processed_docs"] == 1

    def test_ollama_adapter_server_not_running(self):
        """Test Ollama adapter when server is not running."""
        config = {
            "provider": "ollama",
            "model_id": "granite4:latest",
            "document_types": ["invoice", "receipt"],
        }

        with (
            patch(
                "datasift.integrations.ollama.client.OllamaClient.is_server_running",
                return_value=False,
            ),
            patch(
                "datasift.integrations.ollama.client.OllamaClient.is_model_available",
                return_value=True,
            ),
        ):
            # Should raise DatasiftException (fail-fast initialization)
            with pytest.raises(DatasiftException, match="Ollama server is not running"):
                DocumentClassifierOperator(config)

    def test_ollama_adapter_model_not_available(self):
        """Test Ollama adapter when model is not available."""
        config = {
            "provider": "ollama",
            "model_id": "nonexistent-model",
            "document_types": ["invoice", "receipt"],
        }

        with (
            patch(
                "datasift.integrations.ollama.client.OllamaClient.is_server_running",
                return_value=True,
            ),
            patch(
                "datasift.integrations.ollama.client.OllamaClient.is_model_available",
                return_value=False,
            ),
        ):
            # Should raise DatasiftException (fail-fast initialization)
            with pytest.raises(DatasiftException, match="is not available in Ollama"):
                DocumentClassifierOperator(config)


@pytest.mark.unit
class TestLiteLLMClassificationAdapter:
    """Test class for LiteLLM classification adapter."""

    def test_litellm_adapter_basic_classification(self):
        """Test LiteLLM adapter with basic classification."""
        sample_docs = [
            {
                "id": "doc1",
                "name": "contract.txt",
                "content": "CONTRACT AGREEMENT\nThis agreement is made between Party A and Party B.",
            }
        ]

        table = pa.table(
            {
                "id": [doc["id"] for doc in sample_docs],
                "name": [doc["name"] for doc in sample_docs],
                "content": [doc["content"] for doc in sample_docs],
            }
        )

        config = {
            "provider": "litellm",
            "model_id": "openai/gpt-4",
            "provider_config": {
                "api_base": "http://localhost:11434/v1",
                "api_key": "${api_key}",
            },
            "document_types": ["invoice", "receipt", "contract"],
            "confidence_threshold": 7.0,
            "doc_column": "content",
            "output_column": "document_type",
            "include_confidence": True,
            "include_reasoning": True,
        }

        mock_response = json.dumps(
            {
                "document_type": "contract",
                "confidence": 8,
                "reasoning": "Document is a legal agreement between two parties.",
            }
        )

        with patch(
            "datasift.integrations.litellm.client.LiteLLMLLMClient.chat",
            return_value=mock_response,
        ):
            operator = DocumentClassifierOperator(config)
            result_tables, metadata = operator.transform(table)
            result_table = result_tables[0]

            assert "document_type" in result_table.column_names
            assert result_table["document_type"][0].as_py() == "contract"
            assert metadata["processed_docs"] == 1

    def test_litellm_adapter_missing_model_id(self):
        """Test LiteLLM adapter with missing model_id."""
        config = {
            "provider": "litellm",
            "document_types": ["invoice", "receipt"],
        }

        with pytest.raises(ValueError, match="model_id is required for LiteLLM adapter"):
            DocumentClassifierOperator(config)

    def test_litellm_adapter_with_custom_api_base(self):
        """Test LiteLLM adapter with custom API base."""
        sample_docs = [
            {
                "id": "doc1",
                "name": "receipt.txt",
                "content": "RECEIPT\nStore: ABC Store\nTotal: $13.00",
            }
        ]

        table = pa.table(
            {
                "id": [doc["id"] for doc in sample_docs],
                "name": [doc["name"] for doc in sample_docs],
                "content": [doc["content"] for doc in sample_docs],
            }
        )

        config = {
            "provider": "litellm",
            "model_id": "gpt-3.5-turbo",
            "provider_config": {
                "api_base": "http://localhost:11434/v1",
                "api_key": "${api_key}",
            },
            "document_types": ["invoice", "receipt", "contract"],
            "doc_column": "content",
            "output_column": "document_type",
        }

        mock_response = json.dumps(
            {
                "document_type": "receipt",
                "confidence": 9,
                "reasoning": "Document is a payment receipt.",
            }
        )

        with patch(
            "datasift.integrations.litellm.client.LiteLLMLLMClient.chat",
            return_value=mock_response,
        ):
            operator = DocumentClassifierOperator(config)
            result_tables, _metadata = operator.transform(table)
            result_table = result_tables[0]

            assert result_table["document_type"][0].as_py() == "receipt"


@pytest.mark.unit
class TestWatsonxClassificationAdapter:
    """Test class for Watsonx classification adapter."""

    def test_watsonx_adapter_basic_classification(self):
        """Test Watsonx adapter with basic classification."""
        sample_docs = [
            {
                "id": "doc1",
                "name": "report.txt",
                "content": "QUARTERLY REPORT\nQ4 2024 Financial Summary",
            }
        ]

        table = pa.table(
            {
                "id": [doc["id"] for doc in sample_docs],
                "name": [doc["name"] for doc in sample_docs],
                "content": [doc["content"] for doc in sample_docs],
            }
        )

        config = {
            "provider": "watsonx",
            "model_id": "ibm/granite-3-8b-instruct",
            "provider_config": {
                "api_base": "https://us-south.ml.cloud.ibm.com",
                "container_kind": "project",
            },
            "document_types": ["invoice", "receipt", "contract", "report"],
            "confidence_threshold": 7.0,
            "doc_column": "content",
            "output_column": "document_type",
            "include_confidence": True,
            "include_reasoning": True,
        }

        mock_api_response = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": json.dumps(
                            {
                                "document_type": "report",
                                "confidence": 8,
                                "reasoning": "Document is a quarterly financial report.",
                            }
                        ),
                    }
                }
            ]
        }

        with (
            patch.dict(
                "os.environ",
                {
                    "WATSONX_API_KEY": "test-api-key",  # pragma: allowlist secret
                    "WATSONX_CONTAINER_ID": "test-project-id",
                },
            ),
            patch(
                "datasift.utils.infrastructure.iam_token_manager.IAMTokenManager.get_token",
                return_value="test-token",
            ),
            patch(
                "datasift.integrations.rest_client.RestClient.call_rest_json",
                return_value=mock_api_response,
            ),
        ):
            operator = DocumentClassifierOperator(config)
            result_tables, metadata = operator.transform(table)
            result_table = result_tables[0]

            assert "document_type" in result_table.column_names
            assert result_table["document_type"][0].as_py() == "report"
            assert metadata["processed_docs"] == 1

    def test_watsonx_adapter_missing_required_params(self):
        """Test Watsonx adapter with missing required parameters."""
        config = {
            "provider": "watsonx",
            "model_id": "ibm/granite-3-8b-instruct",
            "provider_config": {
                "api_base": "https://us-south.ml.cloud.ibm.com",
            },
            "document_types": ["invoice", "receipt"],
        }

        with (
            patch.dict(
                "os.environ",
                {
                    "WATSONX_API_KEY": "test-api-key",  # pragma: allowlist secret
                    "WATSONX_CONTAINER_ID": "test-container-id",
                },
            ),
            pytest.raises(DatasiftException, match=r"container_kind.*required for watsonx provider"),
        ):
            DocumentClassifierOperator(config)

    def test_watsonx_adapter_with_space_container(self):
        """Test Watsonx adapter with space container kind."""
        sample_docs = [
            {
                "id": "doc1",
                "name": "letter.txt",
                "content": "Dear Sir/Madam,\nThis is a formal letter.",
            }
        ]

        table = pa.table(
            {
                "id": [doc["id"] for doc in sample_docs],
                "name": [doc["name"] for doc in sample_docs],
                "content": [doc["content"] for doc in sample_docs],
            }
        )

        config = {
            "provider": "watsonx",
            "model_id": "ibm/granite-3-8b-instruct",
            "provider_config": {
                "api_base": "https://us-south.ml.cloud.ibm.com",
                "container_kind": "space",
            },
            "document_types": ["invoice", "letter", "report"],
            "doc_column": "content",
            "output_column": "document_type",
        }

        mock_api_response = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": json.dumps(
                            {
                                "document_type": "letter",
                                "confidence": 9,
                                "reasoning": "Document is a formal letter.",
                            }
                        ),
                    }
                }
            ]
        }

        with (
            patch.dict(
                "os.environ",
                {
                    "WATSONX_API_KEY": "test-api-key",  # pragma: allowlist secret
                    "WATSONX_CONTAINER_ID": "test-space-id",
                },
            ),
            patch(
                "datasift.utils.infrastructure.iam_token_manager.IAMTokenManager.get_token",
                return_value="test-token",
            ),
            patch(
                "datasift.integrations.rest_client.RestClient.call_rest_json",
                return_value=mock_api_response,
            ),
        ):
            operator = DocumentClassifierOperator(config)
            result_tables, _metadata = operator.transform(table)
            result_table = result_tables[0]

            assert result_table["document_type"][0].as_py() == "letter"

    def test_watsonx_adapter_token_refresh(self):
        """Test Watsonx adapter token refresh on error."""
        sample_docs = [
            {
                "id": "doc1",
                "name": "invoice.txt",
                "content": "INVOICE\nInvoice Number: INV-001",
            }
        ]

        table = pa.table(
            {
                "id": [doc["id"] for doc in sample_docs],
                "name": [doc["name"] for doc in sample_docs],
                "content": [doc["content"] for doc in sample_docs],
            }
        )

        config = {
            "provider": "watsonx",
            "model_id": "ibm/granite-3-8b-instruct",
            "provider_config": {
                "api_base": "https://us-south.ml.cloud.ibm.com",
                "container_kind": "project",
            },
            "document_types": ["invoice", "receipt"],
            "doc_column": "content",
            "output_column": "document_type",
        }

        with (
            patch.dict(
                "os.environ",
                {
                    "WATSONX_API_KEY": "test-api-key",  # pragma: allowlist secret
                    "WATSONX_CONTAINER_ID": "test-project-id",
                },
            ),
            patch(
                "datasift.integrations.rest_client.RestClient.call_rest_json",
                side_effect=ExternalServiceError(message="Token expired"),
            ),
        ):
            operator = DocumentClassifierOperator(config)
            result_tables, metadata = operator.transform(table)
            result_table = result_tables[0]

            # Should handle error gracefully
            assert result_table.num_rows == 1
            # Check that failed_docs is a list with one entry
            assert len(metadata["failed_docs"]) == 1


@pytest.mark.unit
@patch("datasift.integrations.ollama.client.OllamaClient.is_server_running", return_value=True)
@patch("datasift.integrations.ollama.client.OllamaClient.is_model_available", return_value=True)
def test_document_classifier_progress_tracking(mock_model, mock_server):
    """Test that document classifier reports progress in metadata."""
    from datasift.core.constants import Metrics

    # Create test table with content
    table = pa.table(
        {
            "id": ["doc1", "doc2", "doc3"],
            "name": ["test1.txt", "test2.txt", "test3.txt"],
            "content": ["Invoice content", "Receipt content", "Contract content"],
        }
    )

    # Configure operator
    config = {
        "provider": "ollama",
        "model_id": "test-model",
        "document_types": ["invoice", "receipt", "contract"],
        "job_id": "test-job",
        "job_run_id": "test-run",
        "node_id": "test-node",
        "batch_id": "test-batch",
    }

    # Mock the classification responses
    mock_responses = [
        json.dumps({"document_type": "invoice", "confidence": 9}),
        json.dumps({"document_type": "receipt", "confidence": 8}),
        json.dumps({"document_type": "contract", "confidence": 9}),
    ]

    with patch(
        "datasift.core.operators.quality.classification.adapters.outbound.ollama_adapter.OllamaClient.run",
        side_effect=mock_responses,
    ):
        operator = DocumentClassifierOperator(config)
        _, metadata = operator.transform(table)

        # Check that metadata contains progress fields
        assert Metrics.External.TOTAL_DOCS in metadata
        assert Metrics.External.PROCESSED_DOCS in metadata
        assert metadata[Metrics.External.TOTAL_DOCS] == 3
        assert metadata[Metrics.External.PROCESSED_DOCS] == 3


@pytest.mark.unit
@patch("datasift.integrations.ollama.client.OllamaClient.is_server_running", return_value=True)
@patch("datasift.integrations.ollama.client.OllamaClient.is_model_available", return_value=True)
def test_document_classifier_batch_progress(mock_model, mock_server):
    """Test that document classifier updates progress during batch processing."""
    from datasift.core.constants import Metrics

    # Create larger test table
    num_docs = 10
    table = pa.table(
        {
            "id": [f"doc{i}" for i in range(num_docs)],
            "name": [f"test{i}.txt" for i in range(num_docs)],
            "content": [f"Test content {i}" for i in range(num_docs)],
        }
    )

    # Configure operator with parallel processing
    config = {
        "provider": "ollama",
        "model_id": "test-model",
        "document_types": ["invoice", "receipt"],
        "max_workers": 2,
        "job_id": "test-job",
        "job_run_id": "test-run",
        "node_id": "test-node",
        "batch_id": "test-batch",
    }

    # Mock responses for all documents
    mock_responses = [json.dumps({"document_type": "invoice", "confidence": 8})] * num_docs

    with patch(
        "datasift.core.operators.quality.classification.adapters.outbound.ollama_adapter.OllamaClient.run",
        side_effect=mock_responses,
    ):
        operator = DocumentClassifierOperator(config)
        _, metadata = operator.transform(table)

        # Check progress tracking
        assert metadata[Metrics.External.TOTAL_DOCS] == num_docs
        assert metadata[Metrics.External.PROCESSED_DOCS] >= 0
        assert metadata[Metrics.External.PROCESSED_DOCS] <= num_docs

        # Check that failed docs are tracked
        assert Metrics.External.FAILED_DOCS_COUNT in metadata


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
