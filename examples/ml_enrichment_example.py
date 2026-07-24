#!/usr/bin/env python3
"""
Example: ML Enrichment

This example demonstrates how to enrich documents with ML-based quality metrics
such as word counts, character ratios, and duplication patterns.
Supports multiple languages (English, Spanish, French, etc.).
"""

import sys
from pathlib import Path
from typing import Any

import pyarrow as pa

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.operators.quality.ml_enrichment import MLEnrichmentOperator
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger()


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
    main()
