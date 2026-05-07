#!/usr/bin/env python3
"""
Unit tests for Ollama classification adapter.
"""

import json
from unittest.mock import Mock, patch

import pyarrow as pa
import pytest

from datasift.core.operators.quality.classification.document_classifier import DocumentClassifierOperator
from datasift.exceptions.datasift_exceptions import DatasiftException


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
                "datasift.core.operators.quality.classification.adapters.outbound.ollama_adapter.OllamaClient.is_server_running",
                return_value=True,
            ),
            patch(
                "datasift.core.operators.quality.classification.adapters.outbound.ollama_adapter.OllamaClient.is_model_available",
                return_value=True,
            ),
            patch(
                "datasift.core.operators.quality.classification.adapters.outbound.ollama_adapter.OllamaClient"
            ) as mock_client_class,
        ):
            mock_client = Mock()
            mock_client.run.return_value = mock_response
            mock_client_class.return_value = mock_client

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
                "datasift.core.operators.quality.classification.adapters.outbound.ollama_adapter.OllamaClient.is_server_running",
                return_value=False,
            ),
            patch(
                "datasift.core.operators.quality.classification.adapters.outbound.ollama_adapter.OllamaClient.is_model_available",
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
                "datasift.core.operators.quality.classification.adapters.outbound.ollama_adapter.OllamaClient.is_server_running",
                return_value=True,
            ),
            patch(
                "datasift.core.operators.quality.classification.adapters.outbound.ollama_adapter.OllamaClient.is_model_available",
                return_value=False,
            ),
        ):
            # Should raise DatasiftException (fail-fast initialization)
            with pytest.raises(DatasiftException, match="is not available in Ollama"):
                DocumentClassifierOperator(config)

    def test_ollama_adapter_multiple_documents(self):
        """Test Ollama adapter with multiple documents."""
        sample_docs = [
            {
                "id": "doc1",
                "name": "invoice.txt",
                "content": "INVOICE\nInvoice Number: INV-001\nTotal: $1000",
            },
            {
                "id": "doc2",
                "name": "receipt.txt",
                "content": "RECEIPT\nStore: ABC Store\nTotal: $50",
            },
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
            "doc_column": "content",
            "output_column": "document_type",
        }

        mock_responses = [
            json.dumps({"document_type": "invoice", "confidence": 9, "reasoning": ""}),
            json.dumps({"document_type": "receipt", "confidence": 8, "reasoning": ""}),
        ]

        with (
            patch(
                "datasift.core.operators.quality.classification.adapters.outbound.ollama_adapter.OllamaClient.is_server_running",
                return_value=True,
            ),
            patch(
                "datasift.core.operators.quality.classification.adapters.outbound.ollama_adapter.OllamaClient.is_model_available",
                return_value=True,
            ),
            patch(
                "datasift.core.operators.quality.classification.adapters.outbound.ollama_adapter.OllamaClient"
            ) as mock_client_class,
        ):
            mock_client = Mock()
            mock_client.run.side_effect = mock_responses
            mock_client_class.return_value = mock_client

            operator = DocumentClassifierOperator(config)
            result_tables, metadata = operator.transform(table)
            result_table = result_tables[0]

            assert result_table["document_type"][0].as_py() == "invoice"
            assert result_table["document_type"][1].as_py() == "receipt"
            assert metadata["processed_docs"] == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
