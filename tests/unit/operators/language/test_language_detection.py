"""
Unit tests for Language Detection Operator and Architecture Components

This test suite covers:
1. LanguageAdapterFactory registration and creation
2. LangdetectAdapter detect_language method
3. LanguageDetect operator with the new adapter system
4. Error handling when invalid provider is specified
"""

import pyarrow as pa
import pytest

# Import to trigger adapter registration
import docpipe.core.operators.quality.language_detection.adapters.outbound.langdetect_adapter  # noqa: F401
from docpipe.core.constants.constants import (
    ExecutionStatus,
    Metrics,
)
from docpipe.core.constants.operator_constants import (
    OperatorConstants,
)
from docpipe.core.operators.quality.language_detection.adapters.outbound.factories.language_adapter_factory import (
    LanguageAdapterFactory,
)
from docpipe.core.operators.quality.language_detection.adapters.outbound.langdetect_adapter import (
    LangdetectAdapter,
)
from docpipe.core.operators.quality.language_detection.domain.models import (
    LanguageDetectionResult,
)
from docpipe.core.operators.quality.language_detection.lang_id import (
    DEFAULT_LANGUAGE_PROVIDER,
    LanguageDetect,
)
from docpipe.core.operators.quality.language_detection.ports.outbound.language_service import (
    LanguageServicePort,
)
from docpipe.exceptions.docpipe_exceptions import (
    ExternalServiceError,
)


class TestLanguageAdapterFactory:
    """Test suite for LanguageAdapterFactory"""

    def test_factory_has_langdetect_registered(self):
        """Test that langdetect adapter is automatically registered"""
        available_adapters = LanguageAdapterFactory.list_adapters()
        assert "langdetect" in available_adapters

    def test_factory_create_case_insensitive(self):
        """Test that adapter creation is case-insensitive"""
        adapter1 = LanguageAdapterFactory.create("langdetect")
        adapter2 = LanguageAdapterFactory.create("LANGDETECT")
        adapter3 = LanguageAdapterFactory.create("LangDetect")

        assert isinstance(adapter1, LangdetectAdapter)
        assert isinstance(adapter2, LangdetectAdapter)
        assert isinstance(adapter3, LangdetectAdapter)

    def test_factory_create_invalid_adapter(self):
        """Test that creating invalid adapter raises ValueError"""
        with pytest.raises(ValueError, match="Unknown language detection adapter"):
            LanguageAdapterFactory.create("invalid_adapter")

    def test_factory_create_invalid_adapter_shows_available(self):
        """Test that error message includes available adapters"""
        try:
            LanguageAdapterFactory.create("nonexistent")
            pytest.fail("Should have raised ValueError")
        except ValueError as e:
            error_msg = str(e)
            assert "Available adapters:" in error_msg
            assert "langdetect" in error_msg

    def test_factory_list_adapters_returns_list(self):
        """Test that list_adapters returns a list of strings"""
        adapters = LanguageAdapterFactory.list_adapters()
        assert isinstance(adapters, list)
        assert all(isinstance(name, str) for name in adapters)
        assert len(adapters) > 0

    def test_factory_register_custom_adapter(self):
        """Test registering a custom adapter"""

        # Create a mock adapter class
        class MockAdapter(LanguageServicePort):
            ADAPTER_NAME = "mock_test_adapter"
            ADAPTER_DISPLAY_NAME = "Mock Test Adapter"

            def detect_language(self, text: str) -> LanguageDetectionResult:
                return LanguageDetectionResult("en", 1.0)

        # Register it
        LanguageAdapterFactory.register(MockAdapter)

        # Verify it's registered
        assert "mock_test_adapter" in LanguageAdapterFactory.list_adapters()

        # Verify we can create it
        adapter = LanguageAdapterFactory.create("mock_test_adapter")
        assert isinstance(adapter, MockAdapter)

    def test_factory_register_adapter_without_name_raises_error(self):
        """Test that registering adapter without ADAPTER_NAME raises ValueError"""

        class InvalidAdapter(LanguageServicePort):
            # Missing ADAPTER_NAME
            def detect_language(self, text: str) -> LanguageDetectionResult:
                return LanguageDetectionResult("en", 1.0)

        with pytest.raises(ValueError, match="must define ADAPTER_NAME"):
            LanguageAdapterFactory.register(InvalidAdapter)


class TestLangdetectAdapter:
    """Test suite for LangdetectAdapter"""

    @pytest.fixture
    def adapter(self):
        """Provide a LangdetectAdapter instance"""
        return LangdetectAdapter()

    def test_adapter_has_required_attributes(self, adapter):
        """Test that adapter has required class attributes"""
        assert hasattr(adapter, "ADAPTER_NAME")
        assert hasattr(adapter, "ADAPTER_DISPLAY_NAME")
        assert adapter.ADAPTER_NAME == "langdetect"
        assert adapter.ADAPTER_DISPLAY_NAME == "langdetect"

    def test_detect_language_english(self, adapter):
        """Test detecting English language"""
        text = "Hello, world! This is an English text."
        result = adapter.detect_language(text)

        assert result.language_code == "en"
        assert 0.0 <= result.confidence <= 1.0
        assert result.confidence > 0.9  # Should be highly confident

    def test_detect_language_french(self, adapter):
        """Test detecting French language"""
        text = "Bonjour, monde! Ceci est un texte français."
        result = adapter.detect_language(text)

        assert result.language_code == "fr"
        assert 0.0 <= result.confidence <= 1.0

    def test_detect_language_spanish(self, adapter):
        """Test detecting Spanish language"""
        text = "¡Hola, mundo! Este es un texto en español."
        result = adapter.detect_language(text)

        assert result.language_code == "es"
        assert 0.0 <= result.confidence <= 1.0

    def test_detect_language_empty_text_raises_error(self, adapter):
        """Test that empty text raises ValueError"""
        with pytest.raises(ValueError, match="Text cannot be empty"):
            adapter.detect_language("")

    def test_detect_language_whitespace_only_raises_error(self, adapter):
        """Test that whitespace-only text raises ValueError"""
        with pytest.raises(ValueError, match="Text cannot be empty"):
            adapter.detect_language("   \n\t  ")

    def test_detect_language_short_text(self, adapter):
        """Test detecting language from short text"""
        text = "Hello"
        result = adapter.detect_language(text)

        assert result.language_code is not None
        assert 0.0 <= result.confidence <= 1.0

    def test_detect_language_returns_highest_confidence(self, adapter):
        """Test that detect_language returns the most probable language"""
        # Use a clearly English text
        text = "The quick brown fox jumps over the lazy dog."
        result = adapter.detect_language(text)

        assert result.language_code == "en"
        assert result.confidence > 0.8

    def test_detect_language_result_representation(self, adapter):
        """Test LanguageDetectionResult string representation"""
        text = "Hello, world!"
        result = adapter.detect_language(text)

        repr_str = repr(result)
        assert "LanguageDetectionResult" in repr_str
        assert "language_code" in repr_str
        assert "confidence" in repr_str


class TestLanguageDetectOperator:
    """Test suite for LanguageDetect operator with adapter system"""

    @pytest.fixture
    def sample_config(self):
        """Provide sample configuration for the operator"""
        return {
            "doc_column": "content",
            OperatorConstants.Config.FILTER_UNKNOWN_LANGUAGE: False,
        }

    @pytest.fixture
    def sample_table(self):
        """Create a sample PyArrow table with multilingual content"""
        content = pa.array(
            [
                "Hello, world! This is an English text.",
                "Bonjour, monde! Ceci est un texte français.",
                "¡Hola, mundo! Este es un texto en español.",
            ]
        )
        names = pa.array(["english.txt", "french.txt", "spanish.txt"])
        doc_ids = pa.array(["1", "2", "3"])

        return pa.Table.from_arrays(
            [doc_ids, content, names],
            names=[
                OperatorConstants.Columns.ID,
                "content",
                OperatorConstants.Columns.NAME,
            ],
        )

    def test_operator_initialization_default_provider(self, sample_config):
        """Test that operator initializes with default fasttext provider"""
        operator = LanguageDetect(sample_config)

        assert operator.language_provider == DEFAULT_LANGUAGE_PROVIDER
        assert operator.language_adapter is not None

    def test_operator_initialization_explicit_provider(self):
        """Test that operator initializes with explicitly specified provider"""
        config = {
            "doc_column": "content",
            "language_provider": "langdetect",
        }
        operator = LanguageDetect(config)

        assert operator.language_provider == "langdetect"

    def test_operator_initialization_invalid_provider_raises_error(self):
        """Test that invalid provider raises ValueError during initialization"""
        config = {
            "doc_column": "content",
            "language_provider": "invalid_provider",
        }

        with pytest.raises(ValueError, match="Unknown language detection adapter"):
            LanguageDetect(config)

    def test_operator_metadata(self, sample_config):
        """Test that operator metadata is correctly defined"""
        operator = LanguageDetect(sample_config)
        metadata = operator.get_metadata()

        assert metadata[OperatorConstants.Misc.LABEL] == "Language Annotator"
        assert OperatorConstants.Config.FILTER_UNKNOWN_LANGUAGE in metadata[OperatorConstants.Config.ATTRIBUTES]
        assert OperatorConstants.Columns.LANGUAGE_NAME_COLUMN_KEY in metadata[OperatorConstants.Config.FEATURES]
        assert OperatorConstants.Columns.LANGUAGE_SCORE_COLUMN_KEY in metadata[OperatorConstants.Config.FEATURES]

    def test_operator_transform_basic(self, sample_config, sample_table):
        """Test basic language detection transformation"""
        operator = LanguageDetect(sample_config)
        result_tables, metadata = operator.transform(sample_table)

        assert len(result_tables) == 1
        result_table = result_tables[0]

        # Check that language columns were added
        assert OperatorConstants.Columns.LANGUAGE_NAME_COLUMN_KEY in result_table.column_names
        assert OperatorConstants.Columns.LANGUAGE_SCORE_COLUMN_KEY in result_table.column_names

        # Check that all rows were processed
        assert result_table.num_rows == sample_table.num_rows

        # Check metadata
        assert metadata[Metrics.External.TOTAL_DOCS] == 3
        assert metadata[Metrics.External.PROCESSED_DOCS] == 3

    def test_operator_transform_detects_languages(self, sample_config, sample_table):
        """Test that operator correctly detects languages"""
        operator = LanguageDetect(sample_config)
        result_tables, _metadata = operator.transform(sample_table)
        result_table = result_tables[0]

        # Verify language codes are detected
        languages = result_table[OperatorConstants.Columns.LANGUAGE_NAME_COLUMN_KEY].to_pylist()

        assert all(isinstance(lang, str) for lang in languages)
        assert all(len(lang) >= 2 for lang in languages)  # ISO codes are at least 2 chars

        # First document should be English
        assert languages[0] == "en"

    def test_operator_transform_confidence_scores(self, sample_config, sample_table):
        """Test that confidence scores are in valid range"""
        operator = LanguageDetect(sample_config)
        result_tables, _metadata = operator.transform(sample_table)
        result_table = result_tables[0]

        # Verify confidence scores are between 0 and 1
        scores = result_table[OperatorConstants.Columns.LANGUAGE_SCORE_COLUMN_KEY].to_pylist()

        assert all(isinstance(score, float) for score in scores)
        assert all(0.0 <= score <= 1.0 for score in scores)

    def test_operator_filter_unknown_language(self):
        """Test filtering of documents with unknown language"""
        config = {
            "doc_column": "content",
            OperatorConstants.Config.FILTER_UNKNOWN_LANGUAGE: True,
        }

        # Create table with some problematic content
        content = pa.array(
            [
                "Hello, world!",
                "",  # Empty content
                "Valid English text here.",
            ]
        )
        names = pa.array(["valid1.txt", "empty.txt", "valid2.txt"])
        doc_ids = pa.array(["1", "2", "3"])

        table = pa.Table.from_arrays(
            [doc_ids, content, names],
            names=[
                OperatorConstants.Columns.ID,
                "content",
                OperatorConstants.Columns.NAME,
            ],
        )

        operator = LanguageDetect(config)
        result_tables, metadata = operator.transform(table)
        result_table = result_tables[0]

        # Empty content should be filtered out
        assert result_table.num_rows < table.num_rows
        assert metadata[Metrics.External.FAILED_DOCS_COUNT] > 0
        assert metadata[Metrics.External.NODE_STATUS] == ExecutionStatus.COMPLETED_WITH_ERRORS.value

    def test_operator_no_filter_marks_unknown(self):
        """Test that without filtering, unknown languages are marked as UNKNOWN"""
        config = {
            "doc_column": "content",
            OperatorConstants.Config.FILTER_UNKNOWN_LANGUAGE: False,
        }

        # Create table with problematic content
        content = pa.array(
            [
                "Hello, world!",
                "",  # Empty content
            ]
        )
        names = pa.array(["valid.txt", "empty.txt"])
        doc_ids = pa.array(["1", "2"])

        table = pa.Table.from_arrays(
            [doc_ids, content, names],
            names=[
                OperatorConstants.Columns.ID,
                "content",
                OperatorConstants.Columns.NAME,
            ],
        )

        operator = LanguageDetect(config)
        result_tables, metadata = operator.transform(table)
        result_table = result_tables[0]

        # All rows should be kept
        assert result_table.num_rows == table.num_rows

        # Check that empty content is marked as UNKNOWN
        languages = result_table[OperatorConstants.Columns.LANGUAGE_NAME_COLUMN_KEY].to_pylist()
        assert "UNKNOWN" in languages

        # Check warning status
        assert metadata[Metrics.External.NODE_STATUS] == ExecutionStatus.COMPLETED_WITH_WARNINGS.value

    def test_operator_required_features(self, sample_config):
        """Test that required features are correctly specified"""
        operator = LanguageDetect(sample_config)
        required_features = operator.get_required_features()

        assert "content" in required_features

    def test_operator_empty_table(self, sample_config):
        """Test handling of empty table"""
        empty_table = pa.Table.from_arrays(
            [pa.array([]), pa.array([]), pa.array([])],
            names=[
                OperatorConstants.Columns.ID,
                "content",
                OperatorConstants.Columns.NAME,
            ],
        )

        operator = LanguageDetect(sample_config)
        result_tables, metadata = operator.transform(empty_table)
        result_table = result_tables[0]

        assert result_table.num_rows == 0
        assert metadata[Metrics.External.TOTAL_DOCS] == 0

    def test_operator_with_different_doc_column(self):
        """Test operator with custom document column name"""
        config = {
            "doc_column": "text_content",
            OperatorConstants.Config.FILTER_UNKNOWN_LANGUAGE: False,
        }

        content = pa.array(["Hello, world!"])
        names = pa.array(["test.txt"])
        doc_ids = pa.array(["1"])

        table = pa.Table.from_arrays(
            [doc_ids, content, names],
            names=[
                OperatorConstants.Columns.ID,
                "text_content",
                OperatorConstants.Columns.NAME,
            ],
        )

        operator = LanguageDetect(config)
        result_tables, _metadata = operator.transform(table)
        result_table = result_tables[0]

        assert result_table.num_rows == 1
        assert OperatorConstants.Columns.LANGUAGE_NAME_COLUMN_KEY in result_table.column_names


class TestLanguageDetectionErrorHandling:
    """Test suite for error handling in language detection"""

    def test_adapter_initialization_error_propagates(self):
        """Test that adapter initialization errors are properly propagated"""
        config = {
            "doc_column": "content",
            "language_provider": "nonexistent_provider",
        }

        with pytest.raises(ValueError) as exc_info:
            LanguageDetect(config)

        assert "Unknown language detection adapter" in str(exc_info.value)

    def test_adapter_initialization_error_includes_available_providers(self):
        """Test that initialization error message includes available providers"""
        config = {
            "doc_column": "content",
            "language_provider": "invalid",
        }

        try:
            LanguageDetect(config)
            pytest.fail("Should have raised ValueError")
        except ValueError as e:
            error_msg = str(e)
            assert "Available adapters:" in error_msg or "available" in error_msg.lower()

    def test_langdetect_adapter_handles_detection_failure(self):
        """Test that LangdetectAdapter properly wraps detection failures"""
        adapter = LangdetectAdapter()

        # Very short or ambiguous text might cause detection issues
        # Test with numbers only which langdetect can't detect
        with pytest.raises(ExternalServiceError):
            adapter.detect_language("123")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
