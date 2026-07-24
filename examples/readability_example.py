#!/usr/bin/env python3
"""
Example: Readability Scoring

This example demonstrates how to calculate readability scores for documents
using various metrics (Flesch Reading Ease, Flesch-Kincaid Grade Level, etc.).
"""

import sys
from pathlib import Path
from typing import Any

import pyarrow as pa

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from docpipe.core.operators.quality.readability import (
    DEFAULT_READABILITY_SCORES,
    ReadabilityOperator,
)


def main() -> None:  # pragma: no cover
    """Test the readability operator with sample texts of varying complexity."""
    config: dict[str, Any] = {
        "doc_column": "content",
        "readability_score_list": DEFAULT_READABILITY_SCORES,
    }
    operator: ReadabilityOperator = ReadabilityOperator(config=config)
    print(operator)

    content: pa.Array = pa.array(
        [
            "The cat sat on the mat. It was a sunny day.",
            "Python is a high-level programming language used for web development.",
            "The implementation of sophisticated algorithms necessitates comprehensive understanding.",
        ]
    )
    col_names: list[str] = ["content"]
    input_table: pa.Table = pa.Table.from_arrays([content], names=col_names)

    table_list: list[pa.Table]
    metadata: dict[str, Any]
    table_list, metadata = operator.transform(table=input_table)

    print(">>> completed the operator", operator)
    table: pa.Table = table_list[0]
    print(f"total scores added: {table.num_columns}")
    print(f"\noutput table: {table} {metadata} {table.column_names}")


if __name__ == "__main__":  # pragma: no cover
    main()
