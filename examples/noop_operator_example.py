#!/usr/bin/env python3
"""
Example: NOOP Operator

This example demonstrates the NOOP (No Operation) operator, which is useful
for testing and debugging pipelines without performing any actual operations.
"""

import sys
from pathlib import Path
from typing import Any

import pyarrow as pa

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from docpipe.core.operators.functional.noop import NOOPOperator


def main() -> None:  # pragma: no cover
    """Test the NOOP operator with a simple configuration."""
    # 1. Construct the operator with the required configuration and input parameters
    operator: NOOPOperator = NOOPOperator({"sleep_sec": 1})
    print(operator)

    # 2. Create an in-memory py-arrow table, as the input
    input_table: pa.Table = pa.Table.from_arrays([], names=[])

    # 3. Run the operator
    table_list: list[pa.Table]
    metadata: dict[str, Any]
    table_list, metadata = operator.transform(input_table)

    # 4. Inspect and print the results after the operator is completed
    print(">>> completed the operator", operator)
    print(f"\noutput table has {table_list[0].num_rows} rows")
    print(f"output metadata : {metadata}")


if __name__ == "__main__":  # pragma: no cover
    main()
