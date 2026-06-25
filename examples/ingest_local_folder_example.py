#!/usr/bin/env python3
"""
Example: Local Folder Ingestion

This example demonstrates how to ingest documents from a local folder
using the IngestLocalOperator.
"""

import sys
from pathlib import Path
from typing import Any

import pyarrow as pa

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from docpipe.core.operators.ingest.ingest_local import IngestLocalOperator


def main() -> None:  # pragma: no cover
    """Test the IngestLocalOperator with a sample configuration."""
    # 1. Construct the operator with the required configuration and input parameters
    operator: IngestLocalOperator = IngestLocalOperator(
        {
            "doc_column": "content",
            "paths": "tests/fixtures/invoices",
            "include_filter": "pdf,txt",
        }
    )
    print(operator)

    # 2. Create an in-memory py-arrow table, as the input
    input_table: pa.Table | None = None

    # 3. Run the operator
    table_list: list[pa.Table]
    metadata: dict[str, Any]
    table_list, metadata = operator.transform(input_table)

    # 4. Inspect and print the results after the operator is completed
    print(">>> completed the operator", operator)
    print(f"\noutput table has {table_list[0].num_rows} rows")

    table: pa.Table = table_list[0]
    print(f"output metadata : {metadata}")
    if table_list[0].num_rows:  # avoid printing if table is empty
        print("Found docs: ", table["name"], table["size"])


if __name__ == "__main__":  # pragma: no cover
    main()
