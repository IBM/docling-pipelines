#!/usr/bin/env python3
"""
Example: FastText Language Detection

This example demonstrates how to detect languages using the FastText model,
which supports 176 languages with high accuracy.
"""

import sys
from pathlib import Path
from typing import Any

import pyarrow as pa

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "datasift_opensource" / "backend"))

from common.constants.operator_constants import OperatorConstants
from core.operators.quality.lang_id_fasttext import LanguageDetectFastText


def main() -> tuple[list[pa.Table], dict[str, Any]]:
    """Test FastText language detection with multilingual content."""
    print("=" * 80)
    print("FastText Language Detection Operator - Test Run")
    print("=" * 80)

    # 1. Construct the operator with the required configuration and input parameters
    print("\n1. Initializing operator...")
    operator: LanguageDetectFastText = LanguageDetectFastText(
        {
            "doc_column": "content",
            OperatorConstants.Config.FILTER_UNKNOWN_LANGUAGE: False,
        }
    )
    print(f"   Operator initialized: {operator.short_name}")
    print(f"   FastText model loaded: {operator.fasttext_model is not None}")
    print(f"   Model manager ref count: {operator.model_manager.get_ref_count()}")

    # 2. Create an in-memory py-arrow table, as the input
    print("\n2. Creating test data...")
    content: pa.Array = pa.array(
        [
            "Hello, world! This is an English text.",
            "Bonjour, monde! Ceci est un texte français.",
            "¡Hola, mundo! Este es un texto en español.",
            "Привет, мир! Это русский текст.",
            "こんにちは世界！これは日本語のテキストです。",  # noqa: RUF001
            "Salom dunyo! Bu o'zbek tilidagi matn.",  # Uzbek
            "你好世界！这是中文文本。",  # noqa: RUF001 - Chinese (Simplified)
            "مرحبا بالعالم! هذا نص عربي.",  # Arabic
            "Hallo Welt! Dies ist ein deutscher Text.",  # German
            "Ciao mondo! Questo è un testo italiano.",  # Italian
            "Olá mundo! Este é um texto em português.",  # Portuguese
            "안녕하세요 세계! 이것은 한국어 텍스트입니다.",  # Korean
            "Hej världen! Detta är en svensk text.",  # Swedish
            "Hallo wereld! Dit is een Nederlandse tekst.",  # Dutch
            "Γεια σου κόσμε! Αυτό είναι ένα ελληνικό κείμενο.",  # noqa: RUF001 - Greek
            "Merhaba dünya! Bu bir Türkçe metindir.",  # Turkish
            "Witaj świecie! To jest tekst po polsku.",  # Polish
            "Ahoj světe! Toto je český text.",  # Czech
            "สวัสดีชาวโลก! นี่คือข้อความภาษาไทย",  # Thai
            "Xin chào thế giới! Đây là văn bản tiếng Việt.",  # Vietnamese
        ]
    )
    name: pa.Array = pa.array(
        [
            "english.txt",
            "french.txt",
            "spanish.txt",
            "russian.txt",
            "japanese.txt",
            "uzbek.txt",
            "chinese.txt",
            "arabic.txt",
            "german.txt",
            "italian.txt",
            "portuguese.txt",
            "korean.txt",
            "swedish.txt",
            "dutch.txt",
            "greek.txt",
            "turkish.txt",
            "polish.txt",
            "czech.txt",
            "thai.txt",
            "vietnamese.txt",
        ]
    )
    doc_id: pa.Array = pa.array([str(i) for i in range(1, 21)])
    col_names: list[str] = [
        OperatorConstants.Columns.ID,
        OperatorConstants.Columns.DOC_COLUMN_DEFAULT,
        OperatorConstants.Columns.NAME,
    ]
    input_table: pa.Table = pa.Table.from_arrays([doc_id, content, name], names=col_names)
    print(f"   Created table with {input_table.num_rows} rows")

    # 3. Run the operator
    print("\n3. Running language detection...")
    try:
        table_list: list[pa.Table]
        metadata: dict[str, Any]
        table_list, metadata = operator.transform(input_table)

        # 4. Inspect and print the results after the operator is completed
        print("\n4. Results:")
        print("=" * 80)
        table: pa.Table = table_list[0]

        # Print metadata
        print("\nMetadata:")
        print(f"   Total docs: {metadata.get('total_docs', 0)}")
        print(f"   Processed docs: {metadata.get('processed_docs', 0)}")
        print(f"   Failed docs: {metadata.get('failed_docs_count', 0)}")
        print(f"   Status: {metadata.get('node_status', 'unknown')}")

        # Print detected languages (using correct column names: lang_name and lang_score)
        print("\nDetected Languages:")
        print("-" * 80)
        print(f"{'File':<20} {'Language':<10} {'Confidence':<12} {'Text Preview'}")
        print("-" * 80)
        for i in range(table.num_rows):
            file_name = table["name"][i].as_py()
            lang = table["lang_name"][i].as_py()
            score = table["lang_score"][i].as_py()
            text_preview = table["content"][i].as_py()[:30] + "..."
            print(f"{file_name:<20} {lang:<10} {score:<12.4f} {text_preview}")
        print("-" * 80)

        print("\n" + "=" * 80)
        print("Test completed successfully!")
        print("=" * 80)

        return table_list, metadata
    except Exception as e:
        print(f"\n✗ ERROR during execution: {e}")
        import traceback

        traceback.print_exc()
        raise
    finally:
        # Cleanup
        print("\n5. Cleaning up...")
        operator.cleanup()
        print(f"   Model manager ref count after cleanup: {operator.model_manager.get_ref_count()}")
        print("   Cleanup complete!")


if __name__ == "__main__":
    main()

# Made with Bob
