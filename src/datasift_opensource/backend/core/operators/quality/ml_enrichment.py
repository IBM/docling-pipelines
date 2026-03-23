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

from common.constants import (
    DatasiftConstants,
    ExecutionStatus,
    Metrics,
    OperatorConstants,
)
from common.util.log import get_logger
from common.util.operator_utils import find_doc_count
from core.operators.abstract_operator import AbstractOperator, OperatorCategory

# Import NLTK data management utilities
# This module handles NLTK downloads with SSL bypass capabilities
from core.operators.quality.nltk_data_manager import ensure_nltk_data

logger = get_logger()


class MLEnrichmentOperator(AbstractOperator):
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
        super().__init__(config)

        # Ensure NLTK data is available (punkt_tab tokenizer)
        # This will auto-download on first use with SSL bypass if needed
        ensure_nltk_data("punkt_tab")

        # Get configuration parameters with defaults
        self.doc_column: str = config.get(
            OperatorConstants.Columns.DOC_COLUMN, OperatorConstants.Columns.DOC_COLUMN_DEFAULT
        )
        self.lang_column: str = config.get(
            OperatorConstants.Columns.LANG_COLUMN, OperatorConstants.Columns.LANGUAGE_NAME_COLUMN_KEY
        )
        self.output_column_prefix: str = config.get(OperatorConstants.Columns.OUTPUT_COLUMN_PREFIX, "")
        self.newline_normalized_column_name: str = config.get(
            OperatorConstants.Columns.NEWLINE_NORMALIZED_COLUMN_NAME, ""
        )
        self.error_column_name: str = config.get(OperatorConstants.Columns.ERROR_COLUMN_NAME, "")

        # Update config with dpk_enrichment-specific keys
        self.config.update(
            {
                OperatorConstants.Columns.CONTENT_COLUMN_NAME: self.doc_column,
                OperatorConstants.Columns.LANG_COLUMN_NAME: self.lang_column,
                OperatorConstants.Columns.OUTPUT_COLUMN_PREFIX: self.output_column_prefix,
                OperatorConstants.Columns.NEWLINE_NORMALIZED_COLUMN_NAME: self.newline_normalized_column_name,
                OperatorConstants.Columns.ERROR_COLUMN_NAME: self.error_column_name,
            }
        )

        # Add any custom column name mappings from config
        for feature_key in DEFAULT_TEXT_ENRICHER_DICT.keys():
            column_name_key = f"{feature_key}_column_name"
            if column_name_key in config:
                self.config[column_name_key] = config[column_name_key]

        # Setup logging context
        self.common_log_arguments: dict[str, Any] = {
            DatasiftConstants.JOB_ID: self.job_id,
            DatasiftConstants.JOB_RUN_ID: self.job_run_id,
        }

    def get_metadata(self) -> dict[str, Any]:
        """
        Get operator metadata including features and attributes.

        Returns:
            Dictionary containing operator metadata with features and configuration
        """
        # Build features dictionary for all enrichment metrics
        features = {}

        # Add all default enrichment features
        for feature_key, default_value in DEFAULT_TEXT_ENRICHER_DICT.items():
            column_name = self.output_column_prefix + feature_key
            features[column_name] = {
                OperatorConstants.Misc.NAME: feature_key.replace("_", " ").title(),
                OperatorConstants.Config.DESCRIPTION: f"Text quality metric: {feature_key}",
                OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                OperatorConstants.Misc.TYPE: OperatorConstants.Types.TYPE_FLOAT
                if isinstance(default_value, float)
                else OperatorConstants.Types.TYPE_INT32,
            }

        # Add optional columns if configured
        if self.newline_normalized_column_name:
            features[self.newline_normalized_column_name] = {
                OperatorConstants.Misc.NAME: "Newline Normalized Text",
                OperatorConstants.Config.DESCRIPTION: "Text with normalized newlines",
                OperatorConstants.Config.AVAILABLE_FOR_FILTER: False,
                OperatorConstants.Misc.TYPE: OperatorConstants.Types.TYPE_STRING,
            }

        if self.error_column_name:
            features[self.error_column_name] = {
                OperatorConstants.Misc.NAME: "Processing Error",
                OperatorConstants.Config.DESCRIPTION: "Error message if processing failed",
                OperatorConstants.Config.AVAILABLE_FOR_FILTER: False,
                OperatorConstants.Misc.TYPE: OperatorConstants.Types.TYPE_STRING,
            }

        return {
            OperatorConstants.Misc.CATEGORY: self.category.value,
            OperatorConstants.Misc.IS_OPERATOR_AVAILABLE: self.is_available(),
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

        Raises:
            Exception: If required columns are missing or output columns already exist
        """
        logger.info(
            f"Running ML Enrichment on table with {table.num_rows} rows",
            extra=self.common_log_arguments,
        )

        # Initialize metadata
        total_docs: int = find_doc_count(table=table)
        metadata: dict[str, Any] = self.create_base_metadata(total_docs_count=total_docs)

        output_tables: list[pa.Table] = []

        try:
            # Instantiate the dpk_enrichment transform
            enrichment_transform = EnrichmentTransform(self.config)

            # Execute the transform
            output_tables, _metadata = enrichment_transform.transform(table=table, file_name=file_name or "")

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

            # Log completion status based on whether there were errors
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

            # Update metadata with processing results
            processed_docs = total_docs - metadata[Metrics.External.FAILED_DOCS_COUNT]
            metadata[Metrics.External.PROCESSED_DOCS] = processed_docs
            metadata[Metrics.External.PROCESSED_ROWS] = output_tables[0].num_rows if output_tables else 0

            # Add enrichment-specific metadata
            num_features_added = (
                len([col for col in output_tables[0].column_names if col not in table.column_names])
                if output_tables
                else 0
            )

            metadata["features_added"] = num_features_added
            metadata["enrichment_columns"] = (
                [col for col in output_tables[0].column_names if col not in table.column_names] if output_tables else []
            )

        except Exception as e:
            logger.error(
                f"ML Enrichment failed: {e!s}",
                extra=self.common_log_arguments,
                exc_info=True,
            )

            # Return original table on failure
            output_tables = [table]
            metadata[Metrics.External.NODE_STATUS] = ExecutionStatus.COMPLETED_WITH_ERRORS.value
            metadata[Metrics.External.FAILED_DOCS_COUNT] = total_docs
            metadata[Metrics.External.ERROR] = str(e)

        return output_tables, metadata


def main() -> None:  # pragma: no cover
    """
    Main function to test the ML Enrichment operator.
    """
    # Create sample data with different languages to test multi-language support
    content: list[str] = [
        # English document
        """The quick brown fox jumps over the lazy dog. This pangram contains every letter of the alphabet.

        Machine learning and artificial intelligence are transforming how we process and analyze text data. Natural language processing enables computers to understand, interpret, and generate human language in valuable ways.

        Text enrichment involves computing various quality metrics such as word counts, character ratios, and duplication patterns. These features help assess document quality and filter low-quality content.""",
        # Spanish document
        """El aprendizaje automático y la inteligencia artificial están transformando la forma en que procesamos y analizamos datos de texto.

        El procesamiento del lenguaje natural permite a las computadoras comprender, interpretar y generar lenguaje humano de maneras valiosas.

        Las métricas de calidad ayudan a evaluar la calidad del documento y filtrar contenido de baja calidad. La detección de contenido repetitivo es importante para la calidad de los datos.""",
        # French document
        """L'apprentissage automatique et l'intelligence artificielle transforment la façon dont nous traitons et analysons les données textuelles.

        Le traitement du langage naturel permet aux ordinateurs de comprendre, d'interpréter et de générer le langage humain de manière précieuse.

        Les métriques de qualité aident à évaluer la qualité des documents et à filtrer le contenu de faible qualité. La détection de contenu répétitif est importante pour la qualité des données.""",
    ]

    # Test with different languages: English, Spanish, French
    lang: list[str] = ["en", "es", "fr"]
    doc_id: list[str] = ["doc1", "doc2", "doc3"]
    name: list[str] = ["Document 1", "Document 2", "Document 3"]

    data: dict[str, list[str]] = {
        OperatorConstants.Columns.DOC_COLUMN_DEFAULT: content,
        OperatorConstants.Columns.LANGUAGE_NAME_COLUMN_KEY: lang,
        OperatorConstants.Columns.ID: doc_id,
        OperatorConstants.Columns.NAME: name,
    }

    input_table: pa.Table = pa.table(data)
    logger.info(f"\nInput PyArrow Table:\n{input_table}\n")

    # Configure the operator with error column enabled for debugging
    config: dict[str, Any] = {
        OperatorConstants.Columns.DOC_COLUMN: OperatorConstants.Columns.DOC_COLUMN_DEFAULT,
        OperatorConstants.Columns.LANG_COLUMN: OperatorConstants.Columns.LANGUAGE_NAME_COLUMN_KEY,
        OperatorConstants.Columns.OUTPUT_COLUMN_PREFIX: "ml_",
        OperatorConstants.Columns.ERROR_COLUMN_NAME: "enrichment_error",  # Enable error tracking
    }

    # Create and run the operator
    operator: MLEnrichmentOperator = MLEnrichmentOperator(config=config)

    logger.info(f"Operator: {operator}")

    # Transform the data
    output_tables: list[pa.Table]
    metadata: dict[str, Any]
    output_tables, metadata = operator.transform(input_table)

    # Display results
    output_table = output_tables[0]
    logger.info(f"\nOutput Table Shape: {output_table.num_rows} rows x {output_table.num_columns} columns")
    logger.info(f"Output Columns: {output_table.column_names}")
    logger.info(f"\nMetadata: {metadata}")

    # Check for errors first
    if "enrichment_error" in output_table.column_names:
        logger.info("\nChecking for processing errors:")
        for i in range(output_table.num_rows):
            error = output_table["enrichment_error"][i].as_py()
            if error:
                logger.error(f"  Document {i + 1} error: {error}")

    # Show enrichment features for all documents
    logger.info(f"\n{'=' * 80}")
    logger.info("Enrichment Features for All Documents:")
    logger.info(f"{'=' * 80}\n")

    for i in range(output_table.num_rows):
        doc_name = output_table["name"][i].as_py()
        doc_lang = output_table["lang_name"][i].as_py()
        logger.info(f"Document {i + 1}: {doc_name} (Language: {doc_lang})")
        logger.info("-" * 60)

        for col in output_table.column_names:
            if col.startswith("ml_"):
                value = output_table[col][i].as_py()
                # Format floats to 4 decimal places for readability
                if isinstance(value, float):
                    logger.info(f"  {col}: {value:.4f}")
                else:
                    logger.info(f"  {col}: {value}")
        logger.info("")  # Empty line between documents


if __name__ == "__main__":  # pragma: no cover
    exit(main())
