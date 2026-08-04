"""
ML Enrichment Operator

This operator computes text quality features using the dpk_enrichment package.
It analyzes document content to extract various quality metrics including:
- Basic statistics (word count, character count, paragraph count)
- Character ratios (alphanumeric, punctuation, control characters)
- Duplication metrics (paragraph and n-gram duplicates)
- Special pattern detection (ellipsis, bullet points, etc.)

Dependencies:
    - dpk_enrichment: IBM's text quality feature extraction package
    - NLTK punkt_tab: Required tokenizer data (auto-downloaded on first use)
"""

from typing import Any

import pyarrow as pa
from dpk_enrichment import EnrichmentTransform
from dpk_enrichment.features import DEFAULT_TEXT_ENRICHER_DICT

from docpipe.core.constants import (
    DocpipeConstants,
    ExecutionStatus,
    Metrics,
    OperatorConstants,
)
from docpipe.core.operators.abstract_operator import AbstractOperator, OperatorCategory
from docpipe.core.operators.operator_utils import OperatorUtils
from docpipe.utils.infrastructure.logging import get_logger
from docpipe.utils.infrastructure.nltk_data_manager import ensure_nltk_data

logger = get_logger()

# Metadata keys for ML enrichment results
FEATURES_ADDED_KEY: str = "features_added"
ENRICHMENT_COLUMNS_KEY: str = "enrichment_columns"


class MLEnrichmentOperator(EnrichmentTransform, AbstractOperator):
    """
    ML Enrichment Operator computes text quality features for document content.

    This operator uses the dpk_enrichment package to analyze text and extract
    30+ quality metrics that can be used for data quality assessment, filtering,
    and machine learning feature engineering.

    Features computed include:
    - Basic statistics: num_words, num_chars, num_paragraphs, num_newlines
    - Averages: avg_word_length, avg_paragraph_length
    - Character ratios: alphanumeric, punctuation, control characters
    - Duplication detection: paragraph duplicates, n-gram duplicates
    - Special patterns: ellipsis, bullet points, tabs, hashes
    """

    short_name: str = OperatorConstants.Operators.ML_ENRICHMENT
    category: OperatorCategory = OperatorCategory.Quality
    owner = DocpipeConstants.OWNER_DOCPIPE

    def __init__(self, config: dict[str, Any]) -> None:
        """
        Initialize the ML Enrichment operator.

        Parameters:
            config: Configuration dictionary with the following keys:
                - doc_column: Name of the column containing document text (default: "content")
                - lang_column: Name of the column containing language identifier (default: "lang_name")
                - output_column_prefix: Prefix to add to all output columns (default: "")
                - newline_normalized_column_name: Optional column name for normalized text
                - error_column_name: Optional column name for errors
                - <feature>_column_name: Optional custom name for each feature column
        """
        # Ensure NLTK data is available (punkt_tab tokenizer)
        # This will auto-download on first use with SSL bypass if needed
        ensure_nltk_data("punkt_tab")

        # Get configuration parameters with defaults
        self.lang_column: str = config.get(
            OperatorConstants.Columns.LANG_COLUMN, OperatorConstants.Columns.LANGUAGE_NAME_COLUMN_KEY
        )
        self.output_column_prefix: str = config.get(OperatorConstants.Columns.OUTPUT_COLUMN_PREFIX, "")
        self.newline_normalized_column_name: str = config.get(
            OperatorConstants.Columns.NEWLINE_NORMALIZED_COLUMN_NAME, ""
        )
        self.error_column_name: str = config.get(OperatorConstants.Columns.ERROR_COLUMN_NAME, "")

        # Update config with dpk_enrichment-specific keys
        config.update(
            {
                OperatorConstants.Columns.CONTENT_COLUMN_NAME: config.get(
                    OperatorConstants.Columns.DOC_COLUMN, OperatorConstants.Columns.DOC_COLUMN_DEFAULT
                ),
                OperatorConstants.Columns.LANG_COLUMN_NAME: self.lang_column,
                OperatorConstants.Columns.OUTPUT_COLUMN_PREFIX: self.output_column_prefix,
                OperatorConstants.Columns.NEWLINE_NORMALIZED_COLUMN_NAME: self.newline_normalized_column_name,
                OperatorConstants.Columns.ERROR_COLUMN_NAME: self.error_column_name,
            }
        )

        # Call both parent constructors
        super().__init__(config=config)

        # Setup logging context
        self.common_log_arguments: dict[str, Any] = {
            DocpipeConstants.JOB_ID: self.job_id,
            DocpipeConstants.JOB_RUN_ID: self.job_run_id,
        }

    @staticmethod
    def get_required_features() -> list[str]:
        """Return list of required input features."""
        return [OperatorConstants.Columns.DOC_COLUMN_DEFAULT]

    def validate(self, errors: list[str], warnings: list[str], available_features: list[str]) -> None:
        """
        Validate operator configuration and dependencies.

        Args:
            errors: List to append validation errors
            warnings: List to append validation warnings
            available_features: List of available input features
        """
        # Parent class already validates required features (doc_column)
        super().validate(errors, warnings, available_features)

        # Validate language column if specified (optional, so only warn)
        if self.should_validate_field(field_value=self.lang_column):
            if self.lang_column and self.lang_column not in available_features:
                warnings.append(f"Language column '{self.lang_column}' not found, may affect results")

        # Check for output column conflicts
        if self.should_validate_field(field_value=self.output_column_prefix):
            for feature_key in DEFAULT_TEXT_ENRICHER_DICT.keys():
                output_col = f"{self.output_column_prefix}{feature_key}"
                if output_col in available_features:
                    warnings.append(f"Output column '{output_col}' already exists and will be overwritten")

    @staticmethod
    def get_metadata() -> dict[str, Any]:
        """
        Get operator metadata including features and attributes.

        Returns:
            Dictionary containing operator metadata with features and configuration
        """
        # Build features dictionary for all enrichment metrics
        features = {}

        # Add all default enrichment features (with empty prefix as default)
        for feature_key, default_value in DEFAULT_TEXT_ENRICHER_DICT.items():
            column_name = feature_key  # No prefix by default
            features[column_name] = {
                OperatorConstants.Misc.NAME: feature_key.replace("_", " ").title(),
                OperatorConstants.Config.DESCRIPTION: f"Text quality metric: {feature_key}",
                OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                OperatorConstants.Misc.TYPE: OperatorConstants.Types.TYPE_FLOAT
                if isinstance(default_value, float)
                else OperatorConstants.Types.TYPE_INT32,
            }

        # Add optional columns (always include in metadata)
        features["newline_normalized_text"] = {
            OperatorConstants.Misc.NAME: "Newline Normalized Text",
            OperatorConstants.Config.DESCRIPTION: "Text with normalized newlines",
            OperatorConstants.Config.AVAILABLE_FOR_FILTER: False,
            OperatorConstants.Misc.TYPE: OperatorConstants.Types.TYPE_STRING,
        }

        features["processing_error"] = {
            OperatorConstants.Misc.NAME: "Processing Error",
            OperatorConstants.Config.DESCRIPTION: "Error message if processing failed",
            OperatorConstants.Config.AVAILABLE_FOR_FILTER: False,
            OperatorConstants.Misc.TYPE: OperatorConstants.Types.TYPE_STRING,
        }

        return {
            OperatorConstants.Misc.CATEGORY: MLEnrichmentOperator.category.value,
            OperatorConstants.Misc.IS_OPERATOR_AVAILABLE: MLEnrichmentOperator.is_available(),
            OperatorConstants.Misc.LABEL: "ML Text Enrichment",
            OperatorConstants.Config.DESCRIPTION: (
                "Computes 30+ text quality features including word counts, character ratios, "
                "duplication metrics, and special pattern detection for data quality assessment"
            ),
            OperatorConstants.Config.FEATURES: features,
            OperatorConstants.Config.ATTRIBUTES: {
                OperatorConstants.Columns.DOC_COLUMN: {
                    OperatorConstants.Misc.NAME: "Document Column",
                    OperatorConstants.Config.DESCRIPTION: "Name of the column containing document text",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: OperatorConstants.Columns.DOC_COLUMN_DEFAULT,
                    OperatorConstants.Misc.TYPE: OperatorConstants.Types.TYPE_STRING,
                },
                OperatorConstants.Columns.LANG_COLUMN: {
                    OperatorConstants.Misc.NAME: "Language Column",
                    OperatorConstants.Config.DESCRIPTION: "Name of the column containing language identifier",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: OperatorConstants.Columns.LANGUAGE_NAME_COLUMN_KEY,
                    OperatorConstants.Misc.TYPE: OperatorConstants.Types.TYPE_STRING,
                },
                OperatorConstants.Columns.OUTPUT_COLUMN_PREFIX: {
                    OperatorConstants.Misc.NAME: "Output Column Prefix",
                    OperatorConstants.Config.DESCRIPTION: "Prefix to add to all output column names",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: "",
                    OperatorConstants.Misc.TYPE: OperatorConstants.Types.TYPE_STRING,
                },
            },
        }

    def transform(self, table: pa.Table, file_name: str | None = None) -> tuple[list[pa.Table], dict[str, Any]]:
        """
        Transform the input table by computing text enrichment features.

        Args:
            table: Input PyArrow table with document content
            file_name: Optional file name for logging

        Returns:
            Tuple of (list of output tables, metadata dictionary)
        """
        logger.info(
            f"Running ML Enrichment on table with {table.num_rows} rows",
            extra=self.common_log_arguments,
        )

        # Create docpipe metadata
        total_docs: int = OperatorUtils.find_doc_count(table=table)
        metadata: dict[str, Any] = self.create_base_metadata(total_docs_count=total_docs)

        # Handle empty table edge case
        if table.num_rows == 0:
            logger.info(
                "Empty table provided, returning as-is",
                extra=self.common_log_arguments,
            )
            return [table], metadata

        # Call parent transform (EnrichmentTransform)
        output_tables, _metadata = super().transform(table=table, file_name=file_name or "")

        # Check for enrichment errors and record failed documents
        if output_tables and self.error_column_name and self.error_column_name in output_tables[0].column_names:
            error_column = output_tables[0][self.error_column_name]
            id_column = output_tables[0][OperatorConstants.Columns.ID]
            name_column = output_tables[0][OperatorConstants.Columns.NAME]

            for idx in range(output_tables[0].num_rows):
                error = error_column[idx].as_py()
                if error:  # If there's an error message
                    doc_id = id_column[idx].as_py()
                    doc_name = name_column[idx].as_py()
                    self.record_failed_document(
                        metadata=metadata,
                        doc_id=str(doc_id),
                        doc_name=str(doc_name),
                        reason=f"ML Enrichment error: {error}",
                    )
                    metadata[Metrics.External.NODE_STATUS] = ExecutionStatus.COMPLETED_WITH_ERRORS.value

        # Update metadata with processing results
        processed_docs = total_docs - metadata[Metrics.External.FAILED_DOCS_COUNT]
        metadata[Metrics.External.PROCESSED_DOCS] = processed_docs
        metadata[Metrics.External.PROCESSED_ROWS] = output_tables[0].num_rows if output_tables else 0

        # Add enrichment-specific metadata
        num_features_added = (
            len([col for col in output_tables[0].column_names if col not in table.column_names]) if output_tables else 0
        )

        metadata[FEATURES_ADDED_KEY] = num_features_added
        metadata[ENRICHMENT_COLUMNS_KEY] = (
            [col for col in output_tables[0].column_names if col not in table.column_names] if output_tables else []
        )

        # Log completion status
        if metadata.get(Metrics.External.FAILED_DOCS_COUNT, 0) > 0:
            logger.warning(
                f"ML Enrichment completed with {metadata[Metrics.External.FAILED_DOCS_COUNT]} failed documents",
                extra=self.common_log_arguments,
            )
        else:
            logger.info(
                "ML Enrichment completed successfully",
                extra=self.common_log_arguments,
            )

        return output_tables, metadata
