#!/usr/bin/env python3
"""
Unit tests for LiteLLM classification adapter.
"""

import json
from unittest.mock import patch

import pyarrow as pa
import pytest

from datasift.core.operators.quality.classification.document_classifier import DocumentClassifierOperator


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
            "model_id": "openai/llama3",
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

    def test_litellm_adapter_multiple_documents(self):
        """Test LiteLLM adapter with multiple documents."""
        sample_docs = [
            {
                "id": "doc1",
                "name": "invoice.txt",
                "content": "INVOICE\nInvoice Number: INV-001",
            },
            {
                "id": "doc2",
                "name": "report.txt",
                "content": "QUARTERLY REPORT\nQ4 2024 Summary",
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
            "provider": "litellm",
            "model_id": "openai/gpt-4",
            "provider_config": {
                "api_base": "http://localhost:11434/v1",
                "api_key": "${api_key}",
            },
            "document_types": ["invoice", "receipt", "report"],
            "doc_column": "content",
            "output_column": "document_type",
        }

        mock_responses = [
            json.dumps({"document_type": "invoice", "confidence": 9, "reasoning": ""}),
            json.dumps({"document_type": "report", "confidence": 8, "reasoning": ""}),
        ]

        with patch(
            "datasift.integrations.litellm.client.LiteLLMLLMClient.chat",
            side_effect=mock_responses,
        ):
            operator = DocumentClassifierOperator(config)
            result_tables, metadata = operator.transform(table)
            result_table = result_tables[0]

            assert result_table["document_type"][0].as_py() == "invoice"
            assert result_table["document_type"][1].as_py() == "report"
            assert metadata["processed_docs"] == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
