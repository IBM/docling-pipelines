#!/usr/bin/env python3
"""
Unit tests for Watsonx classification adapter.
"""

import json
from unittest.mock import patch

import pyarrow as pa
import pytest

from datasift.core.operators.quality.classification.document_classifier import DocumentClassifierOperator
from datasift.exceptions.datasift_exceptions import DatasiftException, ExternalServiceError


@pytest.mark.unit
class TestWatsonxClassificationAdapter:
    """Test class for Watsonx classification adapter."""

    def test_watsonx_adapter_basic_classification(self, monkeypatch):
        """Test Watsonx adapter with basic classification."""
        # Set required environment variables
        monkeypatch.setenv("WATSONX_API_KEY", "test-api-key")
        monkeypatch.setenv("WATSONX_CONTAINER_ID", "test-project-id")

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

        # Missing container_kind in provider_config
        with pytest.raises(DatasiftException, match="container_kind is required for watsonx provider"):
            DocumentClassifierOperator(config)

    def test_watsonx_adapter_with_space_container(self, monkeypatch):
        """Test Watsonx adapter with space container kind."""
        # Set required environment variables
        monkeypatch.setenv("WATSONX_API_KEY", "test-api-key")
        monkeypatch.setenv("WATSONX_CONTAINER_ID", "test-space-id")

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

    def test_watsonx_adapter_token_refresh(self, monkeypatch):
        """Test Watsonx adapter token refresh on error."""
        # Set required environment variables
        monkeypatch.setenv("WATSONX_API_KEY", "test-api-key")
        monkeypatch.setenv("WATSONX_CONTAINER_ID", "test-project-id")

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
            patch(
                "datasift.integrations.docling.vlm_pipeline_options_provider.WatsonxPipelineOptionsProvider._get_iam_access_token",
                return_value="test-token",
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

    def test_watsonx_adapter_multiple_documents(self, monkeypatch):
        """Test Watsonx adapter with multiple documents."""
        # Set required environment variables
        monkeypatch.setenv("WATSONX_API_KEY", "test-api-key")
        monkeypatch.setenv("WATSONX_CONTAINER_ID", "test-project-id")

        sample_docs = [
            {
                "id": "doc1",
                "name": "invoice.txt",
                "content": "INVOICE\nInvoice Number: INV-001",
            },
            {
                "id": "doc2",
                "name": "contract.txt",
                "content": "CONTRACT AGREEMENT\nBetween Party A and Party B",
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
            "provider": "watsonx",
            "model_id": "ibm/granite-3-8b-instruct",
            "provider_config": {
                "api_base": "https://us-south.ml.cloud.ibm.com",
                "container_kind": "project",
            },
            "document_types": ["invoice", "contract", "report"],
            "doc_column": "content",
            "output_column": "document_type",
        }

        mock_responses = [
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": json.dumps(
                                {
                                    "document_type": "invoice",
                                    "confidence": 9,
                                    "reasoning": "",
                                }
                            ),
                        }
                    }
                ]
            },
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": json.dumps(
                                {
                                    "document_type": "contract",
                                    "confidence": 8,
                                    "reasoning": "",
                                }
                            ),
                        }
                    }
                ]
            },
        ]

        with (
            patch(
                "datasift.utils.infrastructure.iam_token_manager.IAMTokenManager.get_token",
                return_value="test-token",
            ),
            patch(
                "datasift.integrations.rest_client.RestClient.call_rest_json",
                side_effect=mock_responses,
            ),
        ):
            operator = DocumentClassifierOperator(config)
            result_tables, metadata = operator.transform(table)
            result_table = result_tables[0]

            assert result_table["document_type"][0].as_py() == "invoice"
            assert result_table["document_type"][1].as_py() == "contract"
            assert metadata["processed_docs"] == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
