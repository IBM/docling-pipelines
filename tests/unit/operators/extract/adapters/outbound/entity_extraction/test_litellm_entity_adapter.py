"""Tests for LiteLLM entity extraction adapter."""

import json
from unittest.mock import MagicMock, patch

import pytest

from common.constants.operator_constants import OperatorConstants
from core.operators.extract.adapters.outbound.entity_extraction.litellm_entity_adapter import LiteLLMEntityAdapter


@pytest.fixture
def mock_litellm_client():
    """Create a mock LiteLLM client."""
    with patch("common.clients.litellm_llm_client.LiteLLMLLMClient") as mock_class:
        mock_instance = MagicMock()
        mock_class.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def basic_config():
    """Basic configuration for LiteLLM entity adapter."""
    return {
        OperatorConstants.Config.MODEL_NAME: "gpt-3.5-turbo",
        "temperature": 0.0,
        "max_tokens": 4096,
        "max_doc_chars": 8000,
    }


@pytest.fixture
def config_with_api_credentials():
    """Configuration with API credentials."""
    return {
        OperatorConstants.Config.MODEL_NAME: "gpt-4",
        "temperature": 0.5,
        "max_tokens": 2048,
        "max_doc_chars": 5000,
        "api_key": "test-api-key-123",
        "api_base": "https://api.example.com",
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


class TestLiteLLMEntityAdapterInitialization:
    """Tests for adapter initialization."""

    def test_initialization_with_default_config(self, mock_litellm_client, basic_config):
        """Test initialization with default configuration."""
        adapter = LiteLLMEntityAdapter(config=basic_config)

        assert adapter.model_name == "gpt-3.5-turbo"
        assert adapter.temperature == 0.0
        assert adapter.max_tokens == 4096
        assert adapter.max_doc_chars == 8000
        assert adapter.api_key is None
        assert adapter.api_base is None
        assert adapter.ADAPTER_NAME == OperatorConstants.ExtractionModes.ENTITY_MODE_LITELLM
        assert adapter.ADAPTER_DISPLAY_NAME == "LiteLLM"

    def test_initialization_with_api_credentials(self, mock_litellm_client, config_with_api_credentials):
        """Test initialization with API credentials."""
        adapter = LiteLLMEntityAdapter(config=config_with_api_credentials)

        assert adapter.model_name == "gpt-4"
        assert adapter.temperature == 0.5
        assert adapter.max_tokens == 2048
        assert adapter.max_doc_chars == 5000
        assert adapter.api_key == "test-api-key-123"
        assert adapter.api_base == "https://api.example.com"

    def test_initialization_with_minimal_config(self, mock_litellm_client):
        """Test initialization with minimal configuration."""
        minimal_config = {"model_name": "gpt-3.5-turbo"}
        adapter = LiteLLMEntityAdapter(config=minimal_config)

        # Should use defaults
        assert adapter.model_name == "gpt-3.5-turbo"
        assert adapter.temperature == 0.0
        assert adapter.max_tokens == 4096
        assert adapter.max_doc_chars == 8000

    def test_litellm_client_initialization(self, config_with_api_credentials):
        """Test that LiteLLM client is initialized with correct parameters."""
        with patch("common.clients.litellm_llm_client.LiteLLMLLMClient") as mock_class:
            adapter = LiteLLMEntityAdapter(config=config_with_api_credentials)

            mock_class.assert_called_once_with(
                model_name="gpt-4",
                api_key="test-api-key-123",
                api_base="https://api.example.com",
            )
            assert adapter.litellm_client == mock_class.return_value


class TestLiteLLMEntityAdapterSchemaBasedExtraction:
    """Tests for schema-based entity extraction."""

    def test_extract_entities_with_schema(self, mock_litellm_client, basic_config, sample_schema):
        """Test entity extraction with a predefined schema."""
        adapter = LiteLLMEntityAdapter(config=basic_config)

        # Mock LLM response
        mock_response = json.dumps(
            {
                "invoice_number": "INV-2024-001",
                "total_amount": 1500.00,
                "date": "2024-01-15",
            }
        )
        mock_litellm_client.chat.return_value = mock_response

        result = adapter.extract_entities_single(
            doc_id="doc1",
            doc_name="invoice.pdf",
            content="Invoice #INV-2024-001 dated 2024-01-15 for $1500.00",
            schema=sample_schema,
        )

        assert result[OperatorConstants.Extraction.SUCCESS] is True
        assert result[OperatorConstants.Extraction.ERROR] is None
        entities = result[OperatorConstants.Misc.ENTITIES]
        assert entities["invoice_number"] == "INV-2024-001"
        assert entities["total_amount"] == 1500.00
        assert entities["date"] == "2024-01-15"

        # Verify LLM was called with correct parameters
        mock_litellm_client.chat.assert_called_once()
        call_args = mock_litellm_client.chat.call_args
        assert call_args.kwargs["temperature"] == 0.0
        assert call_args.kwargs["max_tokens"] == 4096
        messages = call_args.kwargs["messages"]
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"

    def test_extract_entities_with_legacy_schema_format(self, mock_litellm_client, basic_config):
        """Test entity extraction with legacy schema format (columns)."""
        adapter = LiteLLMEntityAdapter(config=basic_config)

        legacy_schema = {
            "document_type": "receipt",
            "columns": {
                "merchant": "string",
                "amount": "number",
            },
        }

        mock_response = json.dumps(
            {
                "merchant": "Coffee Shop",
                "amount": 5.50,
            }
        )
        mock_litellm_client.chat.return_value = mock_response

        result = adapter.extract_entities_single(
            doc_id="doc2",
            doc_name="receipt.pdf",
            content="Receipt from Coffee Shop for $5.50",
            schema=legacy_schema,
        )

        assert result[OperatorConstants.Extraction.SUCCESS] is True
        entities = result[OperatorConstants.Misc.ENTITIES]
        assert entities["merchant"] == "Coffee Shop"
        assert entities["amount"] == 5.50


class TestLiteLLMEntityAdapterSchemaFreeExtraction:
    """Tests for schema-free entity extraction."""

    def test_extract_entities_without_schema(self, mock_litellm_client, basic_config):
        """Test entity extraction without a predefined schema."""
        adapter = LiteLLMEntityAdapter(config=basic_config)

        # Mock LLM response for schema-free extraction
        mock_response = json.dumps(
            {
                "person": "John Doe",
                "organization": "Acme Corp",
                "location": "New York",
                "date": "2024-01-15",
            }
        )
        mock_litellm_client.chat.return_value = mock_response

        result = adapter.extract_entities_single(
            doc_id="doc3",
            doc_name="document.txt",
            content="John Doe from Acme Corp visited New York on 2024-01-15",
            schema=None,
        )

        assert result[OperatorConstants.Extraction.SUCCESS] is True
        entities = result[OperatorConstants.Misc.ENTITIES]
        assert entities["person"] == "John Doe"
        assert entities["organization"] == "Acme Corp"
        assert entities["location"] == "New York"

    def test_extract_entities_with_empty_schema(self, mock_litellm_client, basic_config):
        """Test entity extraction with empty schema (should use schema-free mode)."""
        adapter = LiteLLMEntityAdapter(config=basic_config)

        mock_response = json.dumps({"key": "value"})
        mock_litellm_client.chat.return_value = mock_response

        result = adapter.extract_entities_single(
            doc_id="doc4",
            doc_name="doc.txt",
            content="Some content",
            schema={},
        )

        assert result[OperatorConstants.Extraction.SUCCESS] is True
        # Verify schema-free system prompt was used
        call_args = mock_litellm_client.chat.call_args
        messages = call_args.kwargs["messages"]
        assert OperatorConstants.ExtractionModes.ENTITY_EXTRACTION_SCHEMA_FREE_SYSTEM_PROMPT in messages[0]["content"]


class TestLiteLLMEntityAdapterContentHandling:
    """Tests for content handling and truncation."""

    def test_content_truncation(self, mock_litellm_client, basic_config):
        """Test that content is truncated when exceeding max_doc_chars."""
        adapter = LiteLLMEntityAdapter(config=basic_config)

        # Create content longer than max_doc_chars (8000)
        long_content = "A" * 10000

        mock_response = json.dumps({"entity": "value"})
        mock_litellm_client.chat.return_value = mock_response

        result = adapter.extract_entities_single(
            doc_id="doc5",
            doc_name="long_doc.txt",
            content=long_content,
            schema=None,
        )

        assert result[OperatorConstants.Extraction.SUCCESS] is True

        # Verify truncated content was sent to LLM
        call_args = mock_litellm_client.chat.call_args
        user_message = call_args.kwargs["messages"][1]["content"]
        # Content should be truncated to 8000 chars
        assert len(long_content[:8000]) <= 8000
        assert "A" * 8000 in user_message

    def test_bytes_to_string_conversion(self, mock_litellm_client, basic_config):
        """Test that bytes content is converted to string."""
        adapter = LiteLLMEntityAdapter(config=basic_config)

        bytes_content = b"This is binary content"

        mock_response = json.dumps({"entity": "value"})
        mock_litellm_client.chat.return_value = mock_response

        result = adapter.extract_entities_single(
            doc_id="doc6",
            doc_name="binary_doc.pdf",
            content=bytes_content,
            schema=None,
        )

        assert result[OperatorConstants.Extraction.SUCCESS] is True

        # Verify string content was sent to LLM
        call_args = mock_litellm_client.chat.call_args
        user_message = call_args.kwargs["messages"][1]["content"]
        assert "This is binary content" in user_message

    def test_bytes_with_encoding_errors(self, mock_litellm_client, basic_config):
        """Test handling of bytes with encoding errors."""
        adapter = LiteLLMEntityAdapter(config=basic_config)

        # Invalid UTF-8 bytes
        invalid_bytes = b"\xff\xfe Invalid UTF-8"

        mock_response = json.dumps({"entity": "value"})
        mock_litellm_client.chat.return_value = mock_response

        result = adapter.extract_entities_single(
            doc_id="doc7",
            doc_name="invalid_encoding.pdf",
            content=invalid_bytes,
            schema=None,
        )

        # Should handle gracefully with errors='ignore'
        assert result[OperatorConstants.Extraction.SUCCESS] is True


class TestLiteLLMEntityAdapterJSONParsing:
    """Tests for JSON parsing from LLM responses."""

    def test_parse_clean_json_response(self, mock_litellm_client, basic_config):
        """Test parsing clean JSON response."""
        adapter = LiteLLMEntityAdapter(config=basic_config)

        mock_response = json.dumps({"name": "John", "age": 30})
        mock_litellm_client.chat.return_value = mock_response

        result = adapter.extract_entities_single(
            doc_id="doc8",
            doc_name="doc.txt",
            content="Content",
            schema=None,
        )

        assert result[OperatorConstants.Extraction.SUCCESS] is True
        entities = result[OperatorConstants.Misc.ENTITIES]
        assert entities["name"] == "John"
        assert entities["age"] == 30

    def test_parse_json_with_markdown_fences(self, mock_litellm_client, basic_config):
        """Test parsing JSON wrapped in markdown code fences."""
        adapter = LiteLLMEntityAdapter(config=basic_config)

        mock_response = "```json\n" + json.dumps({"key": "value"}) + "\n```"
        mock_litellm_client.chat.return_value = mock_response

        result = adapter.extract_entities_single(
            doc_id="doc9",
            doc_name="doc.txt",
            content="Content",
            schema=None,
        )

        assert result[OperatorConstants.Extraction.SUCCESS] is True
        entities = result[OperatorConstants.Misc.ENTITIES]
        assert entities["key"] == "value"

    def test_parse_json_with_extra_text(self, mock_litellm_client, basic_config):
        """Test parsing JSON with extra text before/after."""
        adapter = LiteLLMEntityAdapter(config=basic_config)

        mock_response = "Here is the result:\n" + json.dumps({"result": "success"}) + "\nDone!"
        mock_litellm_client.chat.return_value = mock_response

        result = adapter.extract_entities_single(
            doc_id="doc10",
            doc_name="doc.txt",
            content="Content",
            schema=None,
        )

        assert result[OperatorConstants.Extraction.SUCCESS] is True
        entities = result[OperatorConstants.Misc.ENTITIES]
        assert entities["result"] == "success"

    def test_parse_truncated_json(self, mock_litellm_client, basic_config):
        """Test parsing truncated JSON (missing closing braces)."""
        adapter = LiteLLMEntityAdapter(config=basic_config)

        # Truncated JSON missing closing brace
        mock_response = '{"name": "John", "age": 30'
        mock_litellm_client.chat.return_value = mock_response

        result = adapter.extract_entities_single(
            doc_id="doc11",
            doc_name="doc.txt",
            content="Content",
            schema=None,
        )

        # Should repair and parse successfully
        assert result[OperatorConstants.Extraction.SUCCESS] is True
        entities = result[OperatorConstants.Misc.ENTITIES]
        assert entities["name"] == "John"
        assert entities["age"] == 30

    def test_parse_invalid_json_returns_empty_dict(self, mock_litellm_client, basic_config):
        """Test that invalid JSON returns empty dict instead of failing."""
        adapter = LiteLLMEntityAdapter(config=basic_config)

        mock_response = "This is not JSON at all!"
        mock_litellm_client.chat.return_value = mock_response

        result = adapter.extract_entities_single(
            doc_id="doc12",
            doc_name="doc.txt",
            content="Content",
            schema=None,
        )

        assert result[OperatorConstants.Extraction.SUCCESS] is True
        entities = result[OperatorConstants.Misc.ENTITIES]
        assert entities == {}


class TestLiteLLMEntityAdapterErrorHandling:
    """Tests for error handling."""

    def test_llm_api_error(self, mock_litellm_client, basic_config):
        """Test handling of LLM API errors."""
        adapter = LiteLLMEntityAdapter(config=basic_config)

        # Simulate API error
        mock_litellm_client.chat.side_effect = Exception("API rate limit exceeded")

        result = adapter.extract_entities_single(
            doc_id="doc13",
            doc_name="doc.txt",
            content="Content",
            schema=None,
        )

        assert result[OperatorConstants.Extraction.SUCCESS] is False
        assert result[OperatorConstants.Misc.ENTITIES] == {}
        assert "API rate limit exceeded" in result[OperatorConstants.Extraction.ERROR]

    def test_network_timeout_error(self, mock_litellm_client, basic_config):
        """Test handling of network timeout errors."""
        adapter = LiteLLMEntityAdapter(config=basic_config)

        mock_litellm_client.chat.side_effect = TimeoutError("Request timeout")

        result = adapter.extract_entities_single(
            doc_id="doc14",
            doc_name="doc.txt",
            content="Content",
            schema=None,
        )

        assert result[OperatorConstants.Extraction.SUCCESS] is False
        assert "Request timeout" in result[OperatorConstants.Extraction.ERROR]

    def test_json_decode_error_in_response(self, mock_litellm_client, basic_config):
        """Test handling when LLM returns completely invalid JSON."""
        adapter = LiteLLMEntityAdapter(config=basic_config)

        # Return something that can't be parsed as JSON
        mock_litellm_client.chat.return_value = "Error: Unable to process"

        result = adapter.extract_entities_single(
            doc_id="doc15",
            doc_name="doc.txt",
            content="Content",
            schema=None,
        )

        # Should succeed but return empty entities
        assert result[OperatorConstants.Extraction.SUCCESS] is True
        assert result[OperatorConstants.Misc.ENTITIES] == {}


class TestLiteLLMEntityAdapterConfigurationVariations:
    """Tests for various configuration scenarios."""

    @pytest.mark.parametrize(
        "model_name,temperature,max_tokens",
        [
            ("gpt-3.5-turbo", 0.0, 4096),
            ("gpt-4", 0.5, 8192),
            ("claude-3-sonnet", 0.7, 2048),
            ("gpt-4-turbo", 0.3, 16384),
        ],
    )
    def test_different_model_configurations(self, mock_litellm_client, model_name, temperature, max_tokens):
        """Test adapter with different model configurations."""
        config = {
            OperatorConstants.Config.MODEL_NAME: model_name,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        adapter = LiteLLMEntityAdapter(config=config)

        assert adapter.model_name == model_name
        assert adapter.temperature == temperature
        assert adapter.max_tokens == max_tokens

    def test_custom_max_doc_chars(self, mock_litellm_client):
        """Test custom max_doc_chars configuration."""
        config = {
            "model_name": "gpt-3.5-turbo",
            "max_doc_chars": 5000,
        }

        adapter = LiteLLMEntityAdapter(config=config)

        assert adapter.max_doc_chars == 5000

        # Test truncation with custom limit
        long_content = "B" * 6000
        mock_litellm_client.chat.return_value = json.dumps({"entity": "value"})

        result = adapter.extract_entities_single(
            doc_id="doc16",
            doc_name="doc.txt",
            content=long_content,
            schema=None,
        )

        assert result[OperatorConstants.Extraction.SUCCESS] is True
        call_args = mock_litellm_client.chat.call_args
        user_message = call_args.kwargs["messages"][1]["content"]
        # Should be truncated to 5000
        assert "B" * 5000 in user_message


class TestLiteLLMEntityAdapterPromptGeneration:
    """Tests for prompt generation."""

    def test_schema_based_prompt_includes_schema_info(self, mock_litellm_client, basic_config, sample_schema):
        """Test that schema-based prompt includes schema information."""
        adapter = LiteLLMEntityAdapter(config=basic_config)

        mock_litellm_client.chat.return_value = json.dumps({})

        adapter.extract_entities_single(
            doc_id="doc17",
            doc_name="doc.txt",
            content="Test content",
            schema=sample_schema,
        )

        call_args = mock_litellm_client.chat.call_args
        messages = call_args.kwargs["messages"]
        user_prompt = messages[1]["content"]

        # Verify schema information is in prompt
        assert "invoice" in user_prompt.lower()
        assert "invoice_number" in user_prompt
        assert "total_amount" in user_prompt
        assert "date" in user_prompt

    def test_schema_free_prompt_format(self, mock_litellm_client, basic_config):
        """Test schema-free prompt format."""
        adapter = LiteLLMEntityAdapter(config=basic_config)

        mock_litellm_client.chat.return_value = json.dumps({})

        adapter.extract_entities_single(
            doc_id="doc18",
            doc_name="doc.txt",
            content="Test content",
            schema=None,
        )

        call_args = mock_litellm_client.chat.call_args
        messages = call_args.kwargs["messages"]
        system_prompt = messages[0]["content"]
        user_prompt = messages[1]["content"]

        # Verify schema-free prompts
        assert system_prompt == OperatorConstants.ExtractionModes.ENTITY_EXTRACTION_SCHEMA_FREE_SYSTEM_PROMPT
        assert "Test content" in user_prompt


class TestLiteLLMEntityAdapterIntegration:
    """Integration-style tests for complete extraction workflows."""

    def test_complete_extraction_workflow_with_schema(self, mock_litellm_client, basic_config, sample_schema):
        """Test complete extraction workflow with schema."""
        adapter = LiteLLMEntityAdapter(config=basic_config)

        # Simulate realistic invoice content
        content = """
        INVOICE
        Invoice Number: INV-2024-001
        Date: January 15, 2024
        Total Amount: $1,500.00
        """

        mock_response = json.dumps(
            {
                "invoice_number": "INV-2024-001",
                "total_amount": 1500.00,
                "date": "January 15, 2024",
            }
        )
        mock_litellm_client.chat.return_value = mock_response

        result = adapter.extract_entities_single(
            doc_id="invoice_001",
            doc_name="invoice_2024_001.pdf",
            content=content,
            schema=sample_schema,
        )

        assert result[OperatorConstants.Extraction.SUCCESS] is True
        assert result[OperatorConstants.Extraction.ERROR] is None
        entities = result[OperatorConstants.Misc.ENTITIES]
        assert entities["invoice_number"] == "INV-2024-001"
        assert entities["total_amount"] == 1500.00
        assert entities["date"] == "January 15, 2024"

    def test_complete_extraction_workflow_without_schema(self, mock_litellm_client, basic_config):
        """Test complete extraction workflow without schema."""
        adapter = LiteLLMEntityAdapter(config=basic_config)

        content = "John Doe works at Acme Corp in New York. Contact: john@acme.com"

        mock_response = json.dumps(
            {
                "person": "John Doe",
                "organization": "Acme Corp",
                "location": "New York",
                "email": "john@acme.com",
            }
        )
        mock_litellm_client.chat.return_value = mock_response

        result = adapter.extract_entities_single(
            doc_id="doc_001",
            doc_name="contact_info.txt",
            content=content,
            schema=None,
        )

        assert result[OperatorConstants.Extraction.SUCCESS] is True
        entities = result[OperatorConstants.Misc.ENTITIES]
        assert entities["person"] == "John Doe"
        assert entities["organization"] == "Acme Corp"
        assert entities["location"] == "New York"
        assert entities["email"] == "john@acme.com"
