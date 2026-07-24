#!/usr/bin/env python3
"""
Example: Content Redaction

This example demonstrates how to redact sensitive information (like SSN, emails, etc.)
from documents using regex patterns.
"""

import sys
from pathlib import Path

import pyarrow as pa

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from docpipe.core.operators.quality.redaction import RedactionOperator


def main():  # pragma: no cover
    """Test the redaction operator with sample data containing SSN patterns."""
    # 1. Construct the operator with the required configuration and input parameters
    config = {
        "doc_column": "content",
        "target_column": "redacted_content",
        "stats_column": "redaction_stats",
        "redaction_masking_character": "X",
        # "redaction_regex": "John",
        "redaction_regex": r"(?!000|.+0{4})(?:\d{9}|\d{3}-\d{2}-\d{4})",
    }
    operator = RedactionOperator(config=config)
    print(operator)

    # 2. Create an in-memory py-arrow table, as the input
    content = pa.array(
        [
            "Joe Doe: 123456854",
            "John Smith: 213254000 Andrew John",
            "Mary Paul: 213250000 -> Invalid SSN",
            "John Paul: 213250000",
            "32530 Paul: 20 -> Invalid SSN",
        ]
    )
    names = [11, 22, 33, 44, 55]
    input_table = pa.Table.from_arrays([content, names], names=["content", "name"])

    # 3. Run the operator
    table_list, metadata = operator.transform(input_table)

    # 4. Inspect and print the results after the operator is completed
    print(">>> completed the operator", operator)

    table = table_list[0]
    print(f"\noutput table: {table}")
    print(f"output metadata : {metadata}")
    print(f"metadata: {operator.get_metadata()}")


if __name__ == "__main__":  # pragma: no cover
    main()
