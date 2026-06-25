"""Tests for DoclingEntityAdapter - custom model configuration validation and usage."""

from unittest.mock import MagicMock, patch

import pytest

from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.operators.extract.adapters.outbound.entity_extraction.docling_entity_adapter import (
    DoclingEntityAdapter,
)


@pytest.fixture
def mock_document_extractor():
    """Create a mock DocumentExtractor."""
    with patch("docling.document_extractor.DocumentExtractor") as mock_class:
        mock_instance = MagicMock()
        mock_class.return_value = mock_instance

        # Mock extraction result
        mock_result = MagicMock()
        mock_page = MagicMock()
        mock_page.page_no = 1
        mock_page.extracted_data = {"test": "data"}
        mock_page.raw_text = "Test content"
        mock_page.errors = []
        mock_result.pages = [mock_page]
        mock_instance.extract.return_value = mock_result

        yield mock_class


@pytest.fixture
def basic_config():
    """Basic configuration without custom model."""
    return {
        "doc_column": "content",
        "output_column": "entities",
    }


@pytest.fixture
def inline_model_config():
    """Configuration with inline model."""
    return {
        "vlm_pipeline": {
            "model_type": "inline",
            "inline_model": {
                "repo_id": "numind/NuExtract-2.0-2B",
                "inference_framework": "transformers",
                "scale": 2.0,
                "temperature": 0.0,
                "max_new_tokens": 4096,
                "load_in_8bit": True,
                "torch_dtype": "bfloat16",
                "response_format": "markdown",  # Valid Docling response format
                "prompt": "",
            },
        }
    }


class TestDoclingEntityAdapterValidation:
    """Tests for configuration validation."""

    def test_validate_inline_model_config_valid(self, inline_model_config):
        """Test validation of valid inline model configuration."""
        adapter = DoclingEntityAdapter(config=inline_model_config)
        # Should not raise
        assert adapter.vlm_pipeline is not None
        assert adapter.vlm_pipeline["model_type"] == "inline"

    def test_validate_missing_model_type(self):
        """Test error when model_type is missing."""
        config = {"vlm_pipeline": {"inline_model": {"repo_id": "test/model"}}}
        # Should not raise - model_type is optional
        adapter = DoclingEntityAdapter(config=config)
        assert adapter.vlm_pipeline is not None

    def test_validate_invalid_model_type(self):
        """Test error when model_type is invalid."""
        config = {"vlm_pipeline": {"model_type": "invalid_type", "inline_model": {"repo_id": "test/model"}}}
        with pytest.raises(ValueError, match=r"model_type.*must be 'inline'"):
            DoclingEntityAdapter(config=config)

    def test_validate_inline_missing_repo_id(self):
        """Test error when repo_id is missing for inline model."""
        config = {"vlm_pipeline": {"model_type": "inline", "inline_model": {}}}
        with pytest.raises(ValueError, match=r"repo_id.*is required"):
            DoclingEntityAdapter(config=config)

    def test_validate_inline_invalid_repo_id_type(self):
        """Test error when repo_id is not a string."""
        config = {"vlm_pipeline": {"model_type": "inline", "inline_model": {"repo_id": 123}}}
        with pytest.raises(ValueError, match=r"repo_id.*must be a string"):
            DoclingEntityAdapter(config=config)

    def test_validate_vlm_pipeline_not_dict(self):
        """Test error when vlm_pipeline is not a dictionary."""
        config = {"vlm_pipeline": "not a dict"}
        with pytest.raises(ValueError, match=r"vlm_pipeline.*must be a dictionary"):
            DoclingEntityAdapter(config=config)

    def test_validate_model_type_not_string(self):
        """Test error when model_type is not a string."""
        config = {"vlm_pipeline": {"model_type": 123, "inline_model": {"repo_id": "test/model"}}}
        with pytest.raises(ValueError, match=r"model_type.*must be a string"):
            DoclingEntityAdapter(config=config)

    def test_validate_inline_model_not_dict(self):
        """Test error when inline_model is not a dictionary."""
        config = {"vlm_pipeline": {"model_type": "inline", "inline_model": "not a dict"}}
        with pytest.raises(ValueError, match=r"inline_model.*must be a dictionary"):
            DoclingEntityAdapter(config=config)

    def test_validate_inline_missing_inline_model(self):
        """Test error when inline_model is missing for inline type."""
        config = {"vlm_pipeline": {"model_type": "inline"}}
        with pytest.raises(ValueError, match=r"inline_model.*is required"):
            DoclingEntityAdapter(config=config)


class TestDoclingEntityAdapterInitialization:
    """Tests for adapter initialization."""

    def test_init_with_inline_model_config(self, inline_model_config):
        """Test initialization with inline model configuration."""
        adapter = DoclingEntityAdapter(config=inline_model_config)

        assert adapter.vlm_pipeline is not None
        assert adapter.vlm_pipeline["model_type"] == "inline"
        assert adapter.vlm_pipeline["inline_model"]["repo_id"] == "numind/NuExtract-2.0-2B"

    def test_init_without_custom_config(self, basic_config):
        """Test default initialization without custom model config (backward compatibility)."""
        adapter = DoclingEntityAdapter(config=basic_config)

        assert adapter.vlm_pipeline is None

    def test_init_with_minimal_inline_config(self):
        """Test initialization with minimal inline configuration."""
        config = {"vlm_pipeline": {"model_type": "inline", "inline_model": {"repo_id": "test/model"}}}
        adapter = DoclingEntityAdapter(config=config)

        assert adapter.vlm_pipeline is not None
        assert adapter.vlm_pipeline["inline_model"]["repo_id"] == "test/model"


class TestDoclingEntityAdapterVLMOptions:
    """Tests for VLM options building."""

    @patch("docling.pipeline.vlm_pipeline.VlmPipeline")
    @patch("docling.document_extractor.ExtractionFormatOption")
    @patch("docling.datamodel.pipeline_options.VlmPipelineOptions")
    @patch("docling.datamodel.pipeline_options_vlm_model.InlineVlmOptions")
    def test_build_vlm_options_inline(
        self, mock_inline_options, mock_pipeline_options, mock_extraction_option, mock_pipeline, inline_model_config
    ):
        """Test VLM options building for inline model."""
        adapter = DoclingEntityAdapter(config=inline_model_config)

        # Reset mock since it was called during initialization
        mock_inline_options.reset_mock()

        options = adapter._build_vlm_extraction_options(vlm_pipeline=adapter.vlm_pipeline)

        # Verify InlineVlmOptions was called with correct parameters
        mock_inline_options.assert_called_once()
        call_kwargs = mock_inline_options.call_args.kwargs
        assert call_kwargs["repo_id"] == "numind/NuExtract-2.0-2B"
        assert call_kwargs["inference_framework"] == "transformers"
        assert call_kwargs["scale"] == 2.0
        assert call_kwargs["temperature"] == 0.0
        assert call_kwargs["max_new_tokens"] == 4096
        assert call_kwargs["load_in_8bit"] is True
        assert call_kwargs["torch_dtype"] == "bfloat16"

        # Verify options structure
        assert options is not None
        assert len(options) == 2  # PDF and IMAGE formats

    @patch("docling.pipeline.vlm_pipeline.VlmPipeline")
    @patch("docling.document_extractor.ExtractionFormatOption")
    @patch("docling.datamodel.pipeline_options.VlmPipelineOptions")
    @patch("docling.datamodel.pipeline_options_vlm_model.InlineVlmOptions")
    def test_build_vlm_options_with_defaults(
        self, mock_inline_options, mock_pipeline_options, mock_extraction_option, mock_pipeline
    ):
        """Test that default values are applied correctly for inline model."""
        config = {
            "vlm_pipeline": {
                "model_type": "inline",
                "inline_model": {
                    "repo_id": "test/model"
                    # All other parameters should use defaults
                },
            }
        }
        adapter = DoclingEntityAdapter(config=config)

        adapter._build_vlm_extraction_options(vlm_pipeline=adapter.vlm_pipeline)

        # Verify defaults were applied
        call_kwargs = mock_inline_options.call_args.kwargs
        assert call_kwargs["repo_id"] == "test/model"
        assert call_kwargs["inference_framework"] == "transformers"  # default
        assert call_kwargs["scale"] == 2.0  # default
        assert call_kwargs["temperature"] == 0.0  # default
        assert call_kwargs["max_new_tokens"] == 4096  # default
        assert call_kwargs["load_in_8bit"] is True  # default
        assert call_kwargs["torch_dtype"] == "bfloat16"  # default
        assert call_kwargs["prompt"] == ""  # default
        assert call_kwargs["response_format"] == "markdown"  # default

    def test_build_vlm_options_without_config(self, basic_config):
        """Test that None is returned when no custom config is provided."""
        adapter = DoclingEntityAdapter(config=basic_config)

        options = adapter._build_vlm_extraction_options(vlm_pipeline=adapter.vlm_pipeline)

        assert options is None


class TestDoclingEntityAdapterExtraction:
    """Tests for entity extraction with custom models."""

    @patch("docling.datamodel.pipeline_options_vlm_model.InlineVlmOptions")
    @patch("docling.datamodel.pipeline_options.VlmPipelineOptions")
    @patch("docling.document_extractor.ExtractionFormatOption")
    @patch("docling.pipeline.vlm_pipeline.VlmPipeline")
    def test_extract_with_inline_model(
        self,
        mock_pipeline,
        mock_extraction_option,
        mock_pipeline_options,
        mock_inline_options,
        mock_document_extractor,
        inline_model_config,
    ):
        """Test extraction using inline model configuration."""
        adapter = DoclingEntityAdapter(config=inline_model_config)

        result = adapter.extract_entities_single(
            doc_id="doc1", doc_name="test.pdf", content=b"Test PDF content", schema={"document_type": "invoice"}
        )

        assert result[OperatorConstants.Extraction.SUCCESS] is True
        assert OperatorConstants.Misc.ENTITIES in result
        mock_document_extractor.assert_called_once()

    @patch("docling.document_extractor.DocumentExtractor")
    def test_extract_without_custom_config(self, mock_document_extractor, basic_config):
        """Test extraction without custom model config (default behavior)."""
        adapter = DoclingEntityAdapter(config=basic_config)

        result = adapter.extract_entities_single(
            doc_id="doc3", doc_name="test.pdf", content=b"Test PDF content", schema=None
        )

        assert result[OperatorConstants.Extraction.SUCCESS] is True
        mock_document_extractor.assert_called_once()

    @patch("docling.datamodel.pipeline_options_vlm_model.InlineVlmOptions")
    @patch("docling.datamodel.pipeline_options.VlmPipelineOptions")
    @patch("docling.document_extractor.ExtractionFormatOption")
    @patch("docling.pipeline.vlm_pipeline.VlmPipeline")
    def test_extract_handles_string_content(
        self,
        mock_pipeline,
        mock_extraction_option,
        mock_pipeline_options,
        mock_inline_options,
        mock_document_extractor,
        inline_model_config,
    ):
        """Test that string content is converted to bytes."""
        adapter = DoclingEntityAdapter(config=inline_model_config)

        result = adapter.extract_entities_single(
            doc_id="doc4", doc_name="test.txt", content="String content", schema=None
        )

        assert result[OperatorConstants.Extraction.SUCCESS] is True


class TestDoclingEntityAdapterErrorHandling:
    """Tests for error handling."""

    def test_extract_handles_import_error(self, basic_config):
        """Test handling of ImportError when DocumentExtractor is not available."""
        with patch("docling.document_extractor.DocumentExtractor", side_effect=ImportError("Module not found")):
            adapter = DoclingEntityAdapter(config=basic_config)

            result = adapter.extract_entities_single(
                doc_id="doc6", doc_name="test.pdf", content=b"Test content", schema=None
            )

            assert result[OperatorConstants.Extraction.SUCCESS] is False
            assert "DocumentExtractor not available" in result[OperatorConstants.Extraction.ERROR]

    def test_extract_handles_extraction_error(self, mock_document_extractor, basic_config):
        """Test handling of extraction errors."""
        mock_document_extractor.return_value.extract.side_effect = Exception("Extraction failed")

        adapter = DoclingEntityAdapter(config=basic_config)

        result = adapter.extract_entities_single(
            doc_id="doc7", doc_name="test.pdf", content=b"Test content", schema=None
        )

        assert result[OperatorConstants.Extraction.SUCCESS] is False
        assert "Extraction failed" in result[OperatorConstants.Extraction.ERROR]

    def test_build_vlm_options_handles_import_error(self, inline_model_config):
        """Test handling of ImportError when building VLM options."""
        with patch(
            "docling.datamodel.pipeline_options_vlm_model.InlineVlmOptions",
            side_effect=ImportError("VLM module not found"),
        ):
            adapter = DoclingEntityAdapter(config=inline_model_config)
            with pytest.raises(ValueError, match="Docling VLM dependencies not available"):
                adapter._build_vlm_extraction_options(vlm_pipeline=adapter.vlm_pipeline)

    def test_build_vlm_options_handles_configuration_error(self, inline_model_config):
        """Test handling of configuration errors when building VLM options."""
        with patch(
            "docling.datamodel.pipeline_options_vlm_model.InlineVlmOptions", side_effect=TypeError("Invalid parameter")
        ):
            adapter = DoclingEntityAdapter(config=inline_model_config)
            with pytest.raises(ValueError, match="Invalid VLM configuration"):
                adapter._build_vlm_extraction_options(vlm_pipeline=adapter.vlm_pipeline)


class TestDoclingEntityAdapterAdapterInfo:
    """Tests for adapter metadata."""

    def test_adapter_name(self):
        """Test adapter name constant."""
        assert DoclingEntityAdapter.ADAPTER_NAME == OperatorConstants.ExtractionModes.ENTITY_MODE_DOCLING

    def test_adapter_display_name(self):
        """Test adapter display name constant."""
        assert DoclingEntityAdapter.ADAPTER_DISPLAY_NAME == "Docling"
