"""Tests for LLM entity extraction adapters (LLMEntityAdapter base and its subclasses)."""

import json
from unittest.mock import MagicMock, patch

import pytest

from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.operators.extract.adapters.outbound.entity_extraction.litellm_entity_adapter import (
    LiteLLMEntityAdapter,
)
from docpipe.core.operators.extract.adapters.outbound.entity_extraction.watsonx_entity_adapter import (
    WatsonxEntityAdapter,
)
from docpipe.exceptions.docpipe_exceptions import DocpipeException


@pytest.fixture
def mock_llm_adapter():
    """Create a mock LLM adapter from factory."""
    with patch("docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_inference_adapter") as mock_factory:
        mock_instance = MagicMock()
        mock_factory.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def litellm_config():
    """Configuration for litellm provider."""
    return {
        OperatorConstants.Config.PROVIDER: "litellm",
        OperatorConstants.Config.MODEL_NAME: "openai/granite4:latest",
        "temperature": 0.0,
        "max_tokens": 4096,
        "max_doc_chars": 8000,
        "entity_provider_config": {
            "api_base": "http://localhost:11434/v1",
            "api_key": "<ollama_key>",
        },
    }


@pytest.fixture
def watsonx_config():
    """Configuration for watsonx provider."""
    return {
        OperatorConstants.Config.PROVIDER: "watsonx",
        OperatorConstants.Config.MODEL_NAME: "ibm/granite-13b-chat-v2",
        "temperature": 0.0,
        "max_tokens": 4096,
        "max_doc_chars": 8000,
        "entity_provider_config": {
            "api_key": "test-api-key",  # pragma: allowlist secret
            "project_id": "test-project-id",
            "url": "https://us-south.ml.cloud.ibm.com",
        },
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


class TestLLMEntityAdapterInitialization:
    """Tests for adapter initialization."""

    def test_initialization_with_litellm(self, mock_llm_adapter, litellm_config):
        """Test initialization with litellm provider."""
        adapter = LiteLLMEntityAdapter(config=litellm_config)

        assert adapter.provider == "litellm"
        assert adapter.model_name == "openai/granite4:latest"
        assert adapter.temperature == 0.0
        assert adapter.max_tokens == 4096
        assert adapter.max_doc_chars == 8000
        assert adapter.ADAPTER_NAME == "litellm"
        assert adapter.ADAPTER_DISPLAY_NAME == "LiteLLM"

    def test_initialization_with_watsonx(self, mock_llm_adapter, watsonx_config):
        """Test initialization with watsonx provider."""
        adapter = WatsonxEntityAdapter(config=watsonx_config)

        assert adapter.provider == "watsonx"
        assert adapter.model_name == "ibm/granite-13b-chat-v2"

    def test_reject_direct_ollama_provider(self):
        """Test that direct ollama provider is rejected."""
        config = {
            OperatorConstants.Config.PROVIDER: "ollama",
            OperatorConstants.Config.MODEL_NAME: "llama3.2",
        }

        with pytest.raises(ValueError, match="Direct 'ollama' provider is deprecated"):
            LiteLLMEntityAdapter(config=config)

    def test_validation_requires_provider(self):
        """Test that provider is required."""
        config = {
            OperatorConstants.Config.MODEL_NAME: "some-model",
        }

        with pytest.raises(ValueError, match="'provider' is required"):
            LiteLLMEntityAdapter(config=config)

    def test_validation_requires_model_name(self, litellm_config):
        """Test that model_name is required."""
        config = litellm_config.copy()
        del config[OperatorConstants.Config.MODEL_NAME]

        with pytest.raises(ValueError, match="is required for LLM entity extraction"):
            LiteLLMEntityAdapter(config=config)


class TestLLMEntityAdapterSchemaBasedExtraction:
    """Tests for schema-based entity extraction."""

    def test_extract_entities_with_schema(self, mock_llm_adapter, litellm_config, sample_schema):
        """Test entity extraction with a predefined schema."""
        adapter = LiteLLMEntityAdapter(config=litellm_config)

        # Mock LLM response
        mock_response = json.dumps(
            {
                "invoice_number": "INV-2024-001",
                "total_amount": 1500.00,
                "date": "2024-01-15",
            }
        )
        mock_llm_adapter.chat.return_value = mock_response

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
        assert entities["total_amount"] == "1500.0"  # numerics normalised to str
        assert entities["date"] == "2024-01-15"

        # Verify LLM was called with correct parameters
        mock_llm_adapter.chat.assert_called_once()
        call_args = mock_llm_adapter.chat.call_args
        assert call_args.kwargs["temperature"] == 0.0
        assert call_args.kwargs["max_tokens"] == 4096
        assert "messages" in call_args.kwargs
        assert len(call_args.kwargs["messages"]) == 2


class TestLLMEntityAdapterSchemaFreeExtraction:
    """Tests for schema-free entity extraction."""

    def test_extract_entities_without_schema(self, mock_llm_adapter, litellm_config):
        """Test entity extraction without a predefined schema."""
        adapter = LiteLLMEntityAdapter(config=litellm_config)

        # Mock LLM response for schema-free extraction
        mock_response = json.dumps(
            {
                "person": "John Doe",
                "organization": "Acme Corp",
                "location": "New York",
            }
        )
        mock_llm_adapter.chat.return_value = mock_response

        result = adapter.extract_entities_single(
            doc_id="doc3",
            doc_name="document.txt",
            content="John Doe from Acme Corp visited New York",
            schema=None,
        )

        assert result[OperatorConstants.Extraction.SUCCESS] is True
        entities = result[OperatorConstants.Misc.ENTITIES]
        assert entities["person"] == "John Doe"
        assert entities["organization"] == "Acme Corp"
        assert entities["location"] == "New York"


class TestLLMEntityAdapterContentHandling:
    """Tests for content handling and truncation."""

    def test_content_truncation(self, mock_llm_adapter, litellm_config):
        """Test that content is truncated when exceeding max_doc_chars."""
        adapter = LiteLLMEntityAdapter(config=litellm_config)

        # Create content longer than max_doc_chars (8000)
        long_content = "A" * 10000

        mock_response = json.dumps({"entity": "value"})
        mock_llm_adapter.chat.return_value = mock_response

        result = adapter.extract_entities_single(
            doc_id="doc5",
            doc_name="long_doc.txt",
            content=long_content,
            schema=None,
        )

        assert result[OperatorConstants.Extraction.SUCCESS] is True

        # Verify truncated content was sent to LLM
        call_args = mock_llm_adapter.chat.call_args
        messages = call_args.kwargs["messages"]
        prompt = messages[1]["content"]
        # Content should be truncated to 8000 chars
        assert "A" * 8000 in prompt

    def test_bytes_to_string_conversion(self, mock_llm_adapter, litellm_config):
        """Test that bytes content is converted to string."""
        adapter = LiteLLMEntityAdapter(config=litellm_config)

        bytes_content = b"This is binary content"

        mock_response = json.dumps({"entity": "value"})
        mock_llm_adapter.chat.return_value = mock_response

        result = adapter.extract_entities_single(
            doc_id="doc6",
            doc_name="binary_doc.pdf",
            content=bytes_content,
            schema=None,
        )

        assert result[OperatorConstants.Extraction.SUCCESS] is True

        # Verify string content was sent to LLM
        call_args = mock_llm_adapter.chat.call_args
        messages = call_args.kwargs["messages"]
        prompt = messages[1]["content"]
        assert "This is binary content" in prompt


class TestLLMEntityAdapterJSONParsing:
    """Tests for JSON parsing from LLM responses."""

    def test_parse_clean_json_response(self, mock_llm_adapter, litellm_config):
        """Test parsing clean JSON response."""
        adapter = LiteLLMEntityAdapter(config=litellm_config)

        mock_response = json.dumps({"name": "John", "age": 30})
        mock_llm_adapter.chat.return_value = mock_response

        result = adapter.extract_entities_single(
            doc_id="doc8",
            doc_name="doc.txt",
            content="Content",
            schema=None,
        )

        assert result[OperatorConstants.Extraction.SUCCESS] is True
        entities = result[OperatorConstants.Misc.ENTITIES]
        assert entities["name"] == "John"
        assert entities["age"] == "30"  # numerics normalised to str

    def test_parse_json_with_markdown_fences(self, mock_llm_adapter, litellm_config):
        """Test parsing JSON wrapped in markdown code fences."""
        adapter = LiteLLMEntityAdapter(config=litellm_config)

        mock_response = "```json\n" + json.dumps({"key": "value"}) + "\n```"
        mock_llm_adapter.chat.return_value = mock_response

        result = adapter.extract_entities_single(
            doc_id="doc9",
            doc_name="doc.txt",
            content="Content",
            schema=None,
        )

        assert result[OperatorConstants.Extraction.SUCCESS] is True
        entities = result[OperatorConstants.Misc.ENTITIES]
        assert entities["key"] == "value"

    def test_parse_invalid_json_returns_empty_dict(self, mock_llm_adapter, litellm_config):
        """Test that invalid JSON returns empty dict instead of failing."""
        adapter = LiteLLMEntityAdapter(config=litellm_config)

        mock_response = "This is not JSON at all!"
        mock_llm_adapter.chat.return_value = mock_response

        result = adapter.extract_entities_single(
            doc_id="doc12",
            doc_name="doc.txt",
            content="Content",
            schema=None,
        )

        assert result[OperatorConstants.Extraction.SUCCESS] is True
        entities = result[OperatorConstants.Misc.ENTITIES]
        assert entities == {}


class TestLLMEntityAdapterErrorHandling:
    """Tests for error handling."""

    def test_llm_api_error(self, mock_llm_adapter, litellm_config):
        """Test handling of LLM API errors."""
        adapter = LiteLLMEntityAdapter(config=litellm_config)

        # Simulate API error
        mock_llm_adapter.chat.side_effect = Exception("API rate limit exceeded")

        result = adapter.extract_entities_single(
            doc_id="doc13",
            doc_name="doc.txt",
            content="Content",
            schema=None,
        )

        assert result[OperatorConstants.Extraction.SUCCESS] is False
        assert result[OperatorConstants.Misc.ENTITIES] == {}
        assert "API rate limit exceeded" in result[OperatorConstants.Extraction.ERROR]


class TestLLMEntityAdapterMultiProvider:
    """Tests for multi-provider support."""

    def test_watsonx_provider_initialization(self, mock_llm_adapter, watsonx_config):
        """Test that watsonx provider is initialized correctly."""
        with patch(
            "docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_inference_adapter"
        ) as mock_factory:
            mock_factory.return_value = mock_llm_adapter
            _ = WatsonxEntityAdapter(config=watsonx_config)

            # Verify factory was called with correct parameters
            mock_factory.assert_called_once()
            call_args = mock_factory.call_args
            assert call_args.kwargs["provider"] == "watsonx"
            assert call_args.kwargs["model_id"] == "ibm/granite-13b-chat-v2"
            assert "api_key" in call_args.kwargs["provider_config"]

    def test_litellm_provider_initialization(self, mock_llm_adapter, litellm_config):
        """Test that litellm provider is initialized correctly."""
        with patch(
            "docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_inference_adapter"
        ) as mock_factory:
            mock_factory.return_value = mock_llm_adapter
            _ = LiteLLMEntityAdapter(config=litellm_config)

            # Verify factory was called with correct parameters
            mock_factory.assert_called_once()
            call_args = mock_factory.call_args
            assert call_args.kwargs["provider"] == "litellm"
            assert call_args.kwargs["model_id"] == "openai/granite4:latest"
            assert "api_base" in call_args.kwargs["provider_config"]


class TestLLMEntityAdapterValidation:
    """Tests for LLM adapter validation during initialization."""

    def test_adapter_validation_called_on_init(self, litellm_config):
        """Test that validate() is called during adapter initialization."""
        with patch(
            "docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_inference_adapter"
        ) as mock_factory:
            # Setup mock adapter with validate method
            mock_adapter = MagicMock()
            mock_adapter.validate.return_value = {
                "valid": True,
                "errors": [],
                "warnings": [],
            }
            mock_factory.return_value = mock_adapter

            # Create adapter - should call validate during initialization
            adapter = LiteLLMEntityAdapter(config=litellm_config)

            # Verify validate was called
            mock_adapter.validate.assert_called_once()
            assert adapter.provider == "litellm"
            assert adapter.model_name == "openai/granite4:latest"

    def test_adapter_validation_failure_raises_error(self, litellm_config):
        """Test that validation failures raise DocpipeException."""
        with patch(
            "docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_inference_adapter"
        ) as mock_factory:
            # Setup mock adapter with failing validation
            mock_adapter = MagicMock()
            mock_adapter.validate.return_value = {
                "valid": False,
                "errors": ["API key is required"],
                "warnings": [],
            }
            mock_factory.return_value = mock_adapter

            # Attempt to create adapter should raise DocpipeException
            with pytest.raises(DocpipeException, match="API key is required"):
                LiteLLMEntityAdapter(config=litellm_config)

    def test_adapter_validation_with_warnings(self, litellm_config):
        """Test that warnings don't block adapter initialization."""
        with patch(
            "docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_inference_adapter"
        ) as mock_factory:
            # Setup mock adapter with warnings
            mock_adapter = MagicMock()
            mock_adapter.validate.return_value = {
                "valid": True,
                "errors": [],
                "warnings": ["Consider setting api_base"],
            }
            mock_factory.return_value = mock_adapter

            # Create adapter - should succeed despite warnings
            adapter = LiteLLMEntityAdapter(config=litellm_config)

            # Verify validate was called and adapter was created successfully
            mock_adapter.validate.assert_called_once()
            assert adapter.provider == "litellm"
            assert adapter.model_name == "openai/granite4:latest"
            # Note: Warning logging happens in LLMEntityAdapter._validate_adapter()


class TestLLMEntityAdapterGetConfigSchema:
    """Tests for get_config_schema static method on the provider subclasses."""

    def test_litellm_get_config_schema_returns_llm_entity_config_class(self):
        from docpipe.core.operators.extract.adapters.outbound.entity_extraction.llm_entity_config import LLMEntityConfig

        schema_cls = LiteLLMEntityAdapter.get_config_schema()
        assert schema_cls is LLMEntityConfig

    def test_watsonx_get_config_schema_returns_watsonx_entity_config_class(self):
        from docpipe.core.operators.extract.adapters.outbound.entity_extraction.llm_entity_config import (
            WatsonxEntityConfig,
        )

        schema_cls = WatsonxEntityAdapter.get_config_schema()
        assert schema_cls is WatsonxEntityConfig

    def test_litellm_config_schema_is_pydantic_model(self):
        from pydantic import BaseModel

        schema_cls = LiteLLMEntityAdapter.get_config_schema()
        assert issubclass(schema_cls, BaseModel)

    def test_litellm_config_schema_has_expected_fields(self):
        schema_cls = LiteLLMEntityAdapter.get_config_schema()
        fields = schema_cls.model_fields
        assert "model_id" in fields
        assert "api_base" in fields
        assert "api_key" in fields
        assert "temperature" in fields
        assert "max_tokens" in fields


class TestLLMEntityAdapterBuildJsonTemplate:
    """Tests for _build_json_template and _template_from_columns methods."""

    def test_build_template_from_fields_format(self, mock_llm_adapter, litellm_config):
        adapter = LiteLLMEntityAdapter(config=litellm_config)
        schema = {
            "fields": [
                {"name": "invoice_number", "type": "string"},
                {"name": "total", "type": "number"},
            ]
        }
        template = adapter._build_json_template(schema=schema)
        assert isinstance(template, dict)

    def test_build_template_from_columns_format(self, mock_llm_adapter, litellm_config):
        adapter = LiteLLMEntityAdapter(config=litellm_config)
        schema = {"columns": {"invoice_number": "string", "total": "number"}}
        template = adapter._build_json_template(schema=schema)
        assert "invoice_number" in template
        assert "total" in template

    def test_build_template_from_flat_format(self, mock_llm_adapter, litellm_config):
        adapter = LiteLLMEntityAdapter(config=litellm_config)
        schema = {"invoice_number": "string", "total": "number"}
        template = adapter._build_json_template(schema=schema)
        assert "invoice_number" in template
        assert "total" in template

    def test_build_template_empty_schema_returns_empty_dict(self, mock_llm_adapter, litellm_config):
        adapter = LiteLLMEntityAdapter(config=litellm_config)
        template = adapter._build_json_template(schema={})
        assert template == {}

    def test_template_from_columns_dot_notation_nesting(self, mock_llm_adapter, litellm_config):
        adapter = LiteLLMEntityAdapter(config=litellm_config)
        result = adapter._template_from_columns({"address.street": "string", "address.city": "string"})
        assert "address" in result
        assert "street" in result["address"]
        assert "city" in result["address"]

    def test_template_from_columns_simple_keys(self, mock_llm_adapter, litellm_config):
        adapter = LiteLLMEntityAdapter(config=litellm_config)
        result = adapter._template_from_columns({"name": "string", "age": "integer"})
        assert result == {"name": None, "age": None}


class TestLLMEntityAdapterNormaliseResponse:
    """Tests for _normalise_response method."""

    def test_strips_key_whitespace(self, mock_llm_adapter, litellm_config):
        adapter = LiteLLMEntityAdapter(config=litellm_config)
        result = adapter._normalise_response({" name ": "John", "  age  ": 30})
        assert "name" in result
        assert "age" in result

    def test_converts_int_to_string(self, mock_llm_adapter, litellm_config):
        adapter = LiteLLMEntityAdapter(config=litellm_config)
        result = adapter._normalise_response({"count": 42})
        assert result["count"] == "42"

    def test_converts_float_to_string(self, mock_llm_adapter, litellm_config):
        adapter = LiteLLMEntityAdapter(config=litellm_config)
        result = adapter._normalise_response({"amount": 15.5})
        assert result["amount"] == "15.5"

    def test_preserves_none(self, mock_llm_adapter, litellm_config):
        adapter = LiteLLMEntityAdapter(config=litellm_config)
        result = adapter._normalise_response({"field": None})
        assert result["field"] is None

    def test_preserves_bool(self, mock_llm_adapter, litellm_config):
        adapter = LiteLLMEntityAdapter(config=litellm_config)
        result = adapter._normalise_response({"flag": True})
        assert result["flag"] is True

    def test_handles_list(self, mock_llm_adapter, litellm_config):
        adapter = LiteLLMEntityAdapter(config=litellm_config)
        result = adapter._normalise_response([{"val": 1}, {"val": 2}])
        assert result == [{"val": "1"}, {"val": "2"}]

    def test_handles_nested_dict(self, mock_llm_adapter, litellm_config):
        adapter = LiteLLMEntityAdapter(config=litellm_config)
        result = adapter._normalise_response({"vendor": {"name": "Acme", "id": 99}})
        assert result["vendor"]["name"] == "Acme"
        assert result["vendor"]["id"] == "99"

    def test_passes_through_string(self, mock_llm_adapter, litellm_config):
        adapter = LiteLLMEntityAdapter(config=litellm_config)
        result = adapter._normalise_response("plain string")
        assert result == "plain string"
