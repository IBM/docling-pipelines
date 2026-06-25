#!/usr/bin/env python3
"""
Example: Language Detection

This example demonstrates how to detect the language of documents
using the LanguageDetect operator with the default FastText provider and with an explicit langdetect override.
"""

import sys
from pathlib import Path
from typing import Any

import pyarrow as pa

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.operators.quality.language_detection.lang_id import LanguageDetect


def run_with_provider(provider: str, content: pa.Array, names: pa.Array, doc_ids: pa.Array) -> None:
    """Run language detection with specified provider."""
    print(f"\n{'=' * 80}")
    print(f"Testing with provider: {provider}")
    print(f"{'=' * 80}")

    # Create operator with specified provider
    operator: LanguageDetect = LanguageDetect(
        {
            "doc_column": "content",
            "language_provider": provider,
            OperatorConstants.Config.FILTER_UNKNOWN_LANGUAGE: False,
        }
    )
    print(f"Operator: {operator.short_name}")
    print(f"Provider: {operator.language_provider}")
    print(f"Adapter: {operator.language_adapter.__class__.__name__}")

    # Create input table
    col_names: list[str] = [
        OperatorConstants.Columns.ID,
        OperatorConstants.Columns.DOC_COLUMN_DEFAULT,
        OperatorConstants.Misc.NAME,
    ]
    input_table: pa.Table = pa.Table.from_arrays([doc_ids, content, names], names=col_names)

    # Run the operator
    table_list: list[pa.Table]
    metadata: dict[str, Any]
    table_list, metadata = operator.transform(input_table)

    # Print results
    table: pa.Table = table_list[0]
    print("\nResults:")
    print(f"  Total docs: {metadata.get('total_docs', 0)}")
    print(f"  Processed docs: {metadata.get('processed_docs', 0)}")
    print(f"  Failed docs: {metadata.get('failed_docs_count', 0)}")

    print(f"\n{'File':<15} {'Language':<10} {'Confidence':<12} {'Text Preview'}")
    print("-" * 80)
    for i in range(table.num_rows):
        file_name = table["name"][i].as_py()
        lang = table["lang_name"][i].as_py()
        score = table["lang_score"][i].as_py()
        text_preview = table["content"][i].as_py()[:40] + "..."
        print(f"{file_name:<15} {lang:<10} {score:<12.4f} {text_preview}")


def main() -> None:
    """Test language detection with multiple providers."""
    print("=" * 80)
    print("Language Detection Operator - Multi-Provider Example")
    print("=" * 80)

    # Create test data with multilingual content
    content: pa.Array = pa.array(
        [
            "Hello, world! This is an English text.",
            "Bonjour, monde! Ceci est un texte français.",
            "¡Hola, mundo! Este es un texto en español.",
            "Сәлем, әлем! Бұл қазақ тіліндегі мәтін.",  # Kazakh: FastText detects `kk`, langdetect misclassifies it
            "Contact support: support@example.com, Phone: 08012345678",
        ]
    )
    names: pa.Array = pa.array(["english.txt", "french.txt", "spanish.txt", "kazakh.txt", "mixed.txt"])
    doc_ids: pa.Array = pa.array(["1", "2", "3", "4", "5"])

    # Test with explicit langdetect provider (55 languages)
    try:
        run_with_provider("langdetect", content, names, doc_ids)
    except Exception as e:
        print(f"\nError with langdetect: {e}")

    # Test with explicit fasttext provider (default provider, 176+ languages)
    try:
        run_with_provider("fasttext", content, names, doc_ids)
    except Exception as e:
        print(f"\nError with fasttext: {e}")

    print(f"\n{'=' * 80}")
    print("Example completed!")
    print(f"{'=' * 80}")
    print("\nKey differences:")
    print("  - langdetect: Fast, 55 languages, no model download required")
    print("  - fasttext: 176+ languages, requires model download (~131MB), higher accuracy")


if __name__ == "__main__":
    main()
