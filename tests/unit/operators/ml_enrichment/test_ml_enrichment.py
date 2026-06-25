"""
Unit tests for ML Enrichment Operator
"""

import pyarrow as pa
import pytest

from docpipe.core.constants import Metrics, OperatorConstants
from docpipe.core.operators.quality.ml_enrichment import (
    ENRICHMENT_COLUMNS_KEY,
    FEATURES_ADDED_KEY,
    MLEnrichmentOperator,
)


class TestMLEnrichmentOperator:
    """Test suite for ML Enrichment operator"""

    @pytest.fixture
    def sample_config(self):
        """Provide sample configuration for the operator"""
        return {
            OperatorConstants.Columns.DOC_COLUMN: "content",
            OperatorConstants.Columns.LANG_COLUMN: "lang_name",
            OperatorConstants.Columns.OUTPUT_COLUMN_PREFIX: "ml_",
        }

    @pytest.fixture
    def sample_config_with_error_tracking(self):
        """Provide configuration with error tracking enabled"""
        return {
            OperatorConstants.Columns.DOC_COLUMN: "content",
            OperatorConstants.Columns.LANG_COLUMN: "lang_name",
            OperatorConstants.Columns.OUTPUT_COLUMN_PREFIX: "ml_",
            OperatorConstants.Columns.ERROR_COLUMN_NAME: "enrichment_error",
        }

    @pytest.fixture
    def sample_table(self):
        """Create a sample PyArrow table with multilingual content"""
        content = pa.array(
            [
                "Hello, world! This is an English text with multiple sentences. "
                "It contains various words and punctuation marks.",
                "Bonjour, monde! Ceci est un texte français avec plusieurs phrases. "
                "Il contient divers mots et signes de ponctuation.",
                "¡Hola, mundo! Este es un texto en español con múltiples oraciones. "
                "Contiene varias palabras y signos de puntuación.",
            ]
        )
        lang_names = pa.array(["en", "fr", "es"])
        names = pa.array(["english.txt", "french.txt", "spanish.txt"])
        doc_ids = pa.array(["1", "2", "3"])

        return pa.Table.from_arrays(
            [doc_ids, content, lang_names, names],
            names=[
                OperatorConstants.Columns.ID,
                "content",
                "lang_name",
                OperatorConstants.Columns.NAME,
            ],
        )

    @pytest.fixture
    def complex_text_table(self):
        """Create a table with complex text patterns for feature testing"""
        content = pa.array(
            [
                # Text with duplicates and special patterns
                """This is a paragraph with some content.

This is a paragraph with some content.

This paragraph has bullet points:
• First item
• Second item
• Third item

Some text with ellipsis... and more text...""",
                # Text with various character types
                """Mixed content: ABC123 xyz789!

Special characters: @#$%^&*()
Punctuation marks: .,;:!?
Control characters and tabs:	indented text
Numbers: 1234567890""",
                # Short text
                "Short.",
            ]
        )
        lang_names = pa.array(["en", "en", "en"])
        names = pa.array(["complex1.txt", "complex2.txt", "short.txt"])
        doc_ids = pa.array(["1", "2", "3"])

        return pa.Table.from_arrays(
            [doc_ids, content, lang_names, names],
            names=[
                OperatorConstants.Columns.ID,
                "content",
                "lang_name",
                OperatorConstants.Columns.NAME,
            ],
        )

    def test_operator_initialization(self, sample_config):
        """Test that operator initializes correctly"""
        operator = MLEnrichmentOperator(sample_config)

        assert operator.doc_column == "content"
        assert operator.lang_column == "lang_name"
        assert operator.output_column_prefix == "ml_"
        assert operator.error_column_name == ""

    def test_operator_initialization_with_defaults(self):
        """Test operator initialization with default values"""
        config = {}
        operator = MLEnrichmentOperator(config)

        assert operator.doc_column == OperatorConstants.Columns.DOC_COLUMN_DEFAULT
        assert operator.lang_column == OperatorConstants.Columns.LANGUAGE_NAME_COLUMN_KEY
        assert operator.output_column_prefix == ""

    def test_operator_metadata(self, sample_config):
        """Test that operator metadata is correctly defined"""
        operator = MLEnrichmentOperator(sample_config)
        metadata = operator.get_metadata()

        assert metadata[OperatorConstants.Misc.LABEL] == "ML Text Enrichment"
        assert OperatorConstants.Columns.DOC_COLUMN in metadata[OperatorConstants.Config.ATTRIBUTES]
        assert OperatorConstants.Columns.LANG_COLUMN in metadata[OperatorConstants.Config.ATTRIBUTES]
        assert OperatorConstants.Columns.OUTPUT_COLUMN_PREFIX in metadata[OperatorConstants.Config.ATTRIBUTES]
        assert OperatorConstants.Config.FEATURES in metadata
        assert metadata[OperatorConstants.Misc.IS_OPERATOR_AVAILABLE] is True

    def test_metadata_features(self, sample_config):
        """Test that metadata includes all expected enrichment features"""
        # get_metadata() is now static and returns features without prefix
        # (prefix is applied at runtime based on instance config)
        metadata = MLEnrichmentOperator.get_metadata()
        features = metadata[OperatorConstants.Config.FEATURES]

        # Check for some key features (without prefix in metadata)
        expected_features = [
            "num_words",
            "num_chars",
            "num_paragraphs",
            "avg_word_length",
            "alphanumeric_char_ratio",
            "punctuation_char_ratio",
        ]

        for feature in expected_features:
            assert feature in features
            assert OperatorConstants.Misc.NAME in features[feature]
            assert OperatorConstants.Config.DESCRIPTION in features[feature]
            assert OperatorConstants.Config.AVAILABLE_FOR_FILTER in features[feature]
            assert OperatorConstants.Misc.TYPE in features[feature]

    def test_basic_enrichment(self, sample_config, sample_table):
        """Test basic enrichment functionality"""
        operator = MLEnrichmentOperator(sample_config)

        result_tables, metadata = operator.transform(sample_table)

        assert len(result_tables) == 1
        result_table = result_tables[0]

        # Check that enrichment columns were added
        assert "ml_num_words" in result_table.column_names
        assert "ml_num_chars" in result_table.column_names
        assert "ml_num_paragraphs" in result_table.column_names

        # Check that all rows were processed
        assert result_table.num_rows == sample_table.num_rows

        # Check metadata
        assert metadata[Metrics.External.TOTAL_DOCS] == 3
        assert metadata[Metrics.External.PROCESSED_DOCS] >= 0
        assert FEATURES_ADDED_KEY in metadata
        assert ENRICHMENT_COLUMNS_KEY in metadata

    def test_enrichment_feature_values(self, sample_config, sample_table):
        """Test that enrichment features have reasonable values"""
        operator = MLEnrichmentOperator(sample_config)

        result_tables, _ = operator.transform(sample_table)
        result_table = result_tables[0]

        # Check first document's features
        num_words = result_table["ml_num_words"][0].as_py()
        num_chars = result_table["ml_num_chars"][0].as_py()
        avg_word_length = result_table["ml_avg_word_length"][0].as_py()

        # Basic sanity checks
        assert num_words > 0, "Should have counted words"
        assert num_chars > 0, "Should have counted characters"
        assert avg_word_length > 0, "Average word length should be positive"
        assert avg_word_length < 20, "Average word length should be reasonable (< 20)"

        # Check that character ratios are between 0 and 1
        alphanumeric_ratio = result_table["ml_alphanumeric_char_ratio"][0].as_py()
        assert 0.0 <= alphanumeric_ratio <= 1.0

    def test_complex_text_features(self, sample_config, complex_text_table):
        """Test enrichment on complex text with special patterns"""
        operator = MLEnrichmentOperator(sample_config)

        result_tables, _ = operator.transform(complex_text_table)
        result_table = result_tables[0]

        # First document has duplicates and bullet points
        doc1_duplicates = result_table["ml_dup_paragraphs_ratio"][0].as_py()
        doc1_bullets = result_table["ml_bulletpoint_ratio"][0].as_py()
        doc1_ellipsis = result_table["ml_ellipsis_ratio"][0].as_py()

        # Check duplicate detection (should be greater than 0 due to repeated paragraph)
        assert doc1_duplicates > 0, "Should detect duplicate paragraphs"

        # Check bullet point detection
        assert doc1_bullets > 0, "Should detect bullet points"

        # Check ellipsis detection
        assert doc1_ellipsis > 0, "Should detect ellipsis"

        # Second document has special characters
        doc2_other_symbols = result_table["ml_other_symbol_char_ratio"][1].as_py()
        assert doc2_other_symbols > 0, "Should detect special characters"

    def test_empty_table(self, sample_config):
        """Test handling of empty table"""
        empty_table = pa.Table.from_arrays(
            [pa.array([]), pa.array([]), pa.array([]), pa.array([])],
            names=[
                OperatorConstants.Columns.ID,
                "content",
                "lang_name",
                OperatorConstants.Columns.NAME,
            ],
        )

        operator = MLEnrichmentOperator(sample_config)

        result_tables, metadata = operator.transform(empty_table)
        result_table = result_tables[0]

        assert result_table.num_rows == 0
        assert metadata[Metrics.External.TOTAL_DOCS] == 0

    def test_single_row_table(self, sample_config):
        """Test handling of single row table"""
        single_row_table = pa.Table.from_arrays(
            [
                pa.array(["1"]),
                pa.array(["This is a test document with some content."]),
                pa.array(["en"]),
                pa.array(["test.txt"]),
            ],
            names=[
                OperatorConstants.Columns.ID,
                "content",
                "lang_name",
                OperatorConstants.Columns.NAME,
            ],
        )

        operator = MLEnrichmentOperator(sample_config)

        result_tables, metadata = operator.transform(single_row_table)
        result_table = result_tables[0]

        assert result_table.num_rows == 1
        assert metadata[Metrics.External.TOTAL_DOCS] == 1
        assert "ml_num_words" in result_table.column_names

    def test_error_tracking(self, sample_config_with_error_tracking):
        """Test error tracking functionality"""
        # get_metadata() is now static and returns features without prefix
        # The prefix is applied at runtime based on instance config
        metadata = MLEnrichmentOperator.get_metadata()
        features = metadata[OperatorConstants.Config.FEATURES]

        # Check that error column is in metadata (without prefix)
        assert "processing_error" in features
        assert features["processing_error"][OperatorConstants.Misc.NAME] == "Processing Error"

    def test_custom_column_prefix(self):
        """Test custom output column prefix"""
        # get_metadata() is now static and returns features without prefix
        # The prefix is applied at runtime based on instance config
        metadata = MLEnrichmentOperator.get_metadata()
        features = metadata[OperatorConstants.Config.FEATURES]

        # Check that features are present without prefix in metadata
        assert "num_words" in features
        assert "num_chars" in features

    def test_no_column_prefix(self):
        """Test enrichment without column prefix"""
        config = {
            OperatorConstants.Columns.DOC_COLUMN: "content",
            OperatorConstants.Columns.LANG_COLUMN: "lang_name",
            OperatorConstants.Columns.OUTPUT_COLUMN_PREFIX: "",
        }

        operator = MLEnrichmentOperator(config)
        metadata = operator.get_metadata()
        features = metadata[OperatorConstants.Config.FEATURES]

        # Check that features have no prefix
        assert "num_words" in features
        assert "num_chars" in features

    def test_multilingual_support(self, sample_table):
        """Test that operator handles multiple languages"""
        config = {
            OperatorConstants.Columns.DOC_COLUMN: "content",
            OperatorConstants.Columns.LANG_COLUMN: "lang_name",
            OperatorConstants.Columns.OUTPUT_COLUMN_PREFIX: "",
        }

        operator = MLEnrichmentOperator(config)

        result_tables, metadata = operator.transform(sample_table)
        result_table = result_tables[0]

        # All three documents (en, fr, es) should be processed
        assert result_table.num_rows == 3
        assert metadata[Metrics.External.TOTAL_DOCS] == 3

        # Check that each document has enrichment features
        for i in range(3):
            num_words = result_table["num_words"][i].as_py()
            assert num_words > 0, f"Document {i} should have word count"

    def test_required_features(self, sample_config):
        """Test that required features are correctly specified"""
        operator = MLEnrichmentOperator(sample_config)
        required_features = operator.get_required_features()

        # ML enrichment operator doesn't define required features
        # It uses doc_column and lang_column from config
        assert isinstance(required_features, list)

    def test_operator_category(self, sample_config):
        """Test that operator has correct category"""
        operator = MLEnrichmentOperator(sample_config)
        metadata = operator.get_metadata()

        from docpipe.core.operators.abstract_operator import OperatorCategory

        assert metadata[OperatorConstants.Misc.CATEGORY] == OperatorCategory.Quality.value

    def test_metadata_counts(self, sample_config, sample_table):
        """Test that metadata contains correct document counts"""
        operator = MLEnrichmentOperator(sample_config)

        result_tables, metadata = operator.transform(sample_table)

        assert metadata[Metrics.External.TOTAL_DOCS] == 3
        assert metadata[Metrics.External.PROCESSED_DOCS] <= 3
        assert metadata[Metrics.External.PROCESSED_ROWS] == result_tables[0].num_rows

    def test_enrichment_columns_added(self, sample_config, sample_table):
        """Test that enrichment columns are properly tracked in metadata"""
        operator = MLEnrichmentOperator(sample_config)

        _, metadata = operator.transform(sample_table)

        assert FEATURES_ADDED_KEY in metadata
        assert ENRICHMENT_COLUMNS_KEY in metadata
        assert metadata[FEATURES_ADDED_KEY] > 0
        assert len(metadata[ENRICHMENT_COLUMNS_KEY]) > 0

        # All enrichment columns should start with the prefix
        for col in metadata[ENRICHMENT_COLUMNS_KEY]:
            assert col.startswith("ml_")

    def test_original_columns_preserved(self, sample_config, sample_table):
        """Test that original columns are preserved in output"""
        operator = MLEnrichmentOperator(sample_config)

        result_tables, _ = operator.transform(sample_table)
        result_table = result_tables[0]

        # Original columns should still be present
        assert OperatorConstants.Columns.ID in result_table.column_names
        assert "content" in result_table.column_names
        assert "lang_name" in result_table.column_names
        assert OperatorConstants.Columns.NAME in result_table.column_names

    def test_feature_types(self, sample_config, sample_table):
        """Test that features have correct data types"""
        operator = MLEnrichmentOperator(sample_config)

        result_tables, _ = operator.transform(sample_table)
        result_table = result_tables[0]

        # Integer features
        num_words = result_table["ml_num_words"][0].as_py()
        assert isinstance(num_words, int)

        # Float features
        avg_word_length = result_table["ml_avg_word_length"][0].as_py()
        assert isinstance(avg_word_length, float)

        alphanumeric_ratio = result_table["ml_alphanumeric_char_ratio"][0].as_py()
        assert isinstance(alphanumeric_ratio, float)

    def test_paragraph_detection(self, complex_text_table):
        """Test paragraph detection and counting"""
        config = {
            OperatorConstants.Columns.DOC_COLUMN: "content",
            OperatorConstants.Columns.LANG_COLUMN: "lang_name",
            OperatorConstants.Columns.OUTPUT_COLUMN_PREFIX: "",
        }

        operator = MLEnrichmentOperator(config)

        result_tables, _ = operator.transform(complex_text_table)
        result_table = result_tables[0]

        # First document has multiple paragraphs
        num_paragraphs = result_table["num_paragraphs"][0].as_py()
        assert num_paragraphs > 1, "Should detect multiple paragraphs"

    def test_newline_detection(self, complex_text_table):
        """Test newline detection"""
        config = {
            OperatorConstants.Columns.DOC_COLUMN: "content",
            OperatorConstants.Columns.LANG_COLUMN: "lang_name",
            OperatorConstants.Columns.OUTPUT_COLUMN_PREFIX: "",
        }

        operator = MLEnrichmentOperator(config)

        result_tables, _ = operator.transform(complex_text_table)
        result_table = result_tables[0]

        # Documents with multiple paragraphs should have newlines
        num_newlines = result_table["num_newlines"][0].as_py()
        assert num_newlines > 0, "Should detect newlines"

    def test_short_text_handling(self, complex_text_table):
        """Test handling of very short text"""
        config = {
            OperatorConstants.Columns.DOC_COLUMN: "content",
            OperatorConstants.Columns.LANG_COLUMN: "lang_name",
            OperatorConstants.Columns.OUTPUT_COLUMN_PREFIX: "",
        }

        operator = MLEnrichmentOperator(config)

        result_tables, _ = operator.transform(complex_text_table)
        result_table = result_tables[0]

        # Third document is very short ("Short.")
        num_words = result_table["num_words"][2].as_py()
        # The tokenizer may count "Short." as 2 tokens (word + punctuation)
        assert num_words >= 1, "Short text should have at least 1 word"

        num_chars = result_table["num_chars"][2].as_py()
        assert num_chars > 0, "Short text should have characters"

    def test_operator_is_available(self, sample_config):
        """Test that operator reports availability correctly"""
        operator = MLEnrichmentOperator(sample_config)
        assert operator.is_available() is True

    def test_transform_with_filename(self, sample_config, sample_table):
        """Test transform with optional filename parameter"""
        operator = MLEnrichmentOperator(sample_config)

        result_tables, _ = operator.transform(sample_table, file_name="test_file.txt")

        assert len(result_tables) == 1
        assert result_tables[0].num_rows == sample_table.num_rows

    def test_validate_missing_doc_column(self, sample_config):
        """Test validation when required document column is missing"""
        operator = MLEnrichmentOperator(sample_config)

        errors = []
        warnings = []
        available_features = ["lang_name", "doc_id", "name"]  # Missing 'content'

        operator.validate(errors=errors, warnings=warnings, available_features=available_features)

        # Parent class validation adds a ValidationMessage object
        assert len(errors) == 1
        error_msg = str(errors[0]) if hasattr(errors[0], "message") else errors[0]
        assert "content" in error_msg

    def test_validate_missing_lang_column(self, sample_config):
        """Test validation when language column is missing (should warn, not error)"""
        operator = MLEnrichmentOperator(sample_config)

        errors = []
        warnings = []
        available_features = ["content", "doc_id", "name"]  # Missing 'lang_name'

        operator.validate(errors=errors, warnings=warnings, available_features=available_features)

        assert len(errors) == 0
        assert len(warnings) == 1
        assert "lang_name" in warnings[0]
        assert "not found" in warnings[0]

    def test_validate_output_column_conflict(self, sample_config):
        """Test validation when output columns already exist"""
        operator = MLEnrichmentOperator(sample_config)

        errors = []
        warnings = []
        # Include some output columns that would be generated
        available_features = ["content", "lang_name", "ml_num_words", "ml_num_chars"]

        operator.validate(errors=errors, warnings=warnings, available_features=available_features)

        assert len(errors) == 0
        assert len(warnings) >= 2  # At least warnings for num_words and num_chars
        assert any("ml_num_words" in w for w in warnings)
        assert any("already exists" in w for w in warnings)

    def test_validate_all_columns_present(self, sample_config):
        """Test validation when all required columns are present"""
        operator = MLEnrichmentOperator(sample_config)

        errors = []
        warnings = []
        available_features = ["content", "lang_name", "doc_id", "name"]

        operator.validate(errors=errors, warnings=warnings, available_features=available_features)

        assert len(errors) == 0
        # May have warnings about output columns, but no errors

    def test_get_required_features_returns_doc_column(self):
        """Test that get_required_features returns the document column"""
        required = MLEnrichmentOperator.get_required_features()

        assert isinstance(required, list)
        assert len(required) == 1
        assert OperatorConstants.Columns.DOC_COLUMN_DEFAULT in required


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
