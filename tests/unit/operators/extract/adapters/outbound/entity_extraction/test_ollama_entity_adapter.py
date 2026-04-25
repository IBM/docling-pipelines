"""Tests for OllamaEntityAdapter - verifying the empty entities fix."""

import json
from unittest.mock import MagicMock, patch

import pytest

from common.constants.operator_constants import OperatorConstants
from core.operators.extract.adapters.outbound.entity_extraction.ollama_entity_adapter import (
    OllamaEntityAdapter,
)


@pytest.fixture
def mock_ollama_client():
    """Create a mock Ollama client."""
    with patch("common.clients.ollama_client.OllamaClient") as mock_class:
        mock_instance = MagicMock()
        mock_class.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def basic_config():
    """Basic configuration for Ollama entity adapter."""
    return {
        OperatorConstants.Config.MODEL_NAME: "llama3.2",
        "temperature": 0.0,
        "max_tokens": 4096,
        "max_doc_chars": 8000,
    }


@pytest.fixture
def sample_schema():
    """Sample schema for entity extraction."""
    return {
        "document_type": "invoice",
        "document_description": "Invoice document",
        "fields": [
            {
                "name": "invoice_number",
                "type": "string",
                "description": "Invoice number",
            },
            {
                "name": "total_amount",
                "type": "number",
                "description": "Total amount",
            },
            {
                "name": "date",
                "type": "string",
                "description": "Invoice date",
            },
        ],
    }


class TestOllamaEntityAdapterResponseParsing:
    """Tests for response parsing - verifying the empty entities fix."""

    def test_extract_entities_with_clean_json_response(
        self, mock_ollama_client, basic_config, sample_schema
    ):
        """Test that clean JSON response is parsed correctly."""
        adapter = OllamaEntityAdapter(config=basic_config)

        # Mock Ollama client to return clean JSON string
        mock_response = json.dumps(
            {
                "invoice_number": "INV-2024-001",
                "total_amount": 1500.00,
                "date": "2024-01-15",
            }
        )
        mock_ollama_client.chat.return_value = mock_response

        result = adapter.extract_entities_single(
            doc_id="doc1",
            doc_name="invoice.pdf",
            content="Invoice #INV-2024-001 dated 2024-01-15 for $1500.00",
            schema=sample_schema,
        )

        # Verify the fix: entities should be extracted correctly
        assert result[OperatorConstants.Extraction.SUCCESS] is True
        assert result[OperatorConstants.Extraction.ERROR] is None
        entities = result[OperatorConstants.Misc.ENTITIES]
        assert entities["invoice_number"] == "INV-2024-001"
        assert entities["total_amount"] == 1500.00
        assert entities["date"] == "2024-01-15"

        # Verify chat was called with correct parameters
        mock_ollama_client.chat.assert_called_once()
        call_args = mock_ollama_client.chat.call_args
        messages = call_args.kwargs["messages"]
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"

    def test_extract_entities_with_markdown_wrapped_json(
        self, mock_ollama_client, basic_config, sample_schema
    ):
        """Test that JSON wrapped in markdown code fences is parsed correctly."""
        adapter = OllamaEntityAdapter(config=basic_config)

        # Mock response with markdown code fences
        mock_response = (
            "```json\n"
            + json.dumps({"invoice_number": "INV-001", "total_amount": 100.0})
            + "\n```"
        )
        mock_ollama_client.chat.return_value = mock_response

        result = adapter.extract_entities_single(
            doc_id="doc2",
            doc_name="invoice.pdf",
            content="Invoice content",
            schema=sample_schema,
        )

        # Verify entities are extracted despite markdown wrapping
        assert result[OperatorConstants.Extraction.SUCCESS] is True
        entities = result[OperatorConstants.Misc.ENTITIES]
        assert entities["invoice_number"] == "INV-001"
        assert entities["total_amount"] == 100.0

    def test_extract_entities_with_extra_text(
        self, mock_ollama_client, basic_config, sample_schema
    ):
        """Test that JSON with extra text before/after is parsed correctly."""
        adapter = OllamaEntityAdapter(config=basic_config)

        # Mock response with extra text
        mock_response = (
            "Here is the result:\n"
            + json.dumps({"invoice_number": "INV-002"})
            + "\nDone!"
        )
        mock_ollama_client.chat.return_value = mock_response

        result = adapter.extract_entities_single(
            doc_id="doc3",
            doc_name="invoice.pdf",
            content="Invoice content",
            schema=sample_schema,
        )

        # Verify entities are extracted despite extra text
        assert result[OperatorConstants.Extraction.SUCCESS] is True
        entities = result[OperatorConstants.Misc.ENTITIES]
        assert entities["invoice_number"] == "INV-002"

    def test_extract_entities_schema_free_mode(self, mock_ollama_client, basic_config):
        """Test schema-free extraction mode."""
        adapter = OllamaEntityAdapter(config=basic_config)

        # Mock response for schema-free extraction
        mock_response = json.dumps(
            {
                "person": "John Doe",
                "organization": "Acme Corp",
                "location": "New York",
            }
        )
        mock_ollama_client.chat.return_value = mock_response

        result = adapter.extract_entities_single(
            doc_id="doc4",
            doc_name="document.txt",
            content="John Doe from Acme Corp visited New York",
            schema=None,
        )

        # Verify schema-free extraction works
        assert result[OperatorConstants.Extraction.SUCCESS] is True
        entities = result[OperatorConstants.Misc.ENTITIES]
        assert entities["person"] == "John Doe"
        assert entities["organization"] == "Acme Corp"
        assert entities["location"] == "New York"

    def test_extract_entities_with_invalid_json_returns_empty_dict(
        self, mock_ollama_client, basic_config
    ):
        """Test that invalid JSON returns empty dict instead of failing."""
        adapter = OllamaEntityAdapter(config=basic_config)

        # Mock response with invalid JSON
        mock_response = "This is not JSON at all!"
        mock_ollama_client.chat.return_value = mock_response

        result = adapter.extract_entities_single(
            doc_id="doc5",
            doc_name="doc.txt",
            content="Content",
            schema=None,
        )

        # Should succeed but return empty entities
        assert result[OperatorConstants.Extraction.SUCCESS] is True
        entities = result[OperatorConstants.Misc.ENTITIES]
        assert entities == {}

    def test_extract_entities_handles_bytes_content(
        self, mock_ollama_client, basic_config
    ):
        """Test that bytes content is converted to string."""
        adapter = OllamaEntityAdapter(config=basic_config)

        bytes_content = b"Invoice content"
        mock_response = json.dumps({"invoice_number": "INV-003"})
        mock_ollama_client.chat.return_value = mock_response

        result = adapter.extract_entities_single(
            doc_id="doc6",
            doc_name="invoice.pdf",
            content=bytes_content,
            schema=None,
        )

        # Verify bytes are handled correctly
        assert result[OperatorConstants.Extraction.SUCCESS] is True
        entities = result[OperatorConstants.Misc.ENTITIES]
        assert entities["invoice_number"] == "INV-003"

    def test_extract_entities_error_handling(self, mock_ollama_client, basic_config):
        """Test error handling when Ollama client fails."""
        adapter = OllamaEntityAdapter(config=basic_config)

        # Simulate Ollama client error
        mock_ollama_client.chat.side_effect = Exception("Ollama connection failed")

        result = adapter.extract_entities_single(
            doc_id="doc7",
            doc_name="doc.txt",
            content="Content",
            schema=None,
        )

        # Should return error result
        assert result[OperatorConstants.Extraction.SUCCESS] is False
        assert result[OperatorConstants.Misc.ENTITIES] == {}
        assert "Ollama connection failed" in result[OperatorConstants.Extraction.ERROR]
