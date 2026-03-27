#!/usr/bin/env python3
"""
Example: Language Detection

This example demonstrates how to detect the language of documents
using the LanguageDetect operator.
"""

import sys
from pathlib import Path
from typing import Any

import pyarrow as pa

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "datasift_opensource" / "backend"))

from common.constants.operator_constants import OperatorConstants
from core.operators.quality.lang_id import LanguageDetect


def main() -> tuple[list[pa.Table], dict[str, Any]]:
    """Test the language detection operator with sample multilingual content."""
    # 1. Construct the operator with the required configuration and input parameters
    operator: LanguageDetect = LanguageDetect(
        {"doc_column": "content", OperatorConstants.Config.FILTER_UNKNOWN_LANGUAGE: False}
    )
    print(operator)

    # 2. Create an in-memory py-arrow table, as the input
    content: pa.Array = pa.array(
        [
            "Contact support team via email: support@ibm.com, or the sales team sales@in.ibm.com, Content Phone Number: 08012345678 ",
            "My personal email id is jj@acm.org, PhoneNumber is: +91 932-123-1234 and +91 9321231234, Amex Card Number: 378734493671000",
            "",
            "8967840594",
            "Hello, world! Bonjour, monde! ¡Hola, mundo!",
        ]
    )
    name: pa.Array = pa.array(["name1", "name2", "name3", "name4", "name5"])
    doc_id: pa.Array = pa.array(["1", "2", "3", "4", "5"])
    col_names: list[str] = [
        OperatorConstants.Columns.ID,
        OperatorConstants.Columns.DOC_COLUMN_DEFAULT,
        OperatorConstants.Misc.NAME,
    ]
    input_table: pa.Table = pa.Table.from_arrays([doc_id, content, name], names=col_names)

    # 3. Run the operator
    table_list: list[pa.Table]
    metadata: dict[str, Any]
    table_list, metadata = operator.transform(input_table)
    
    # 4. Inspect and print the results after the operator is completed
    print(">>> completed the operator", operator)
    table: pa.Table = table_list[0]
    print(f"\noutput table: {table}, {metadata}")
    return table_list, metadata


if __name__ == "__main__":
    main()

# Made with Bob
