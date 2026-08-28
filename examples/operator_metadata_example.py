#!/usr/bin/env python3
"""
Example: Operator Metadata Retrieval

This example demonstrates how to retrieve metadata for all available operators
in the docling-pipelines framework.
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from docpipe.core.operators.operator_metadata import OperatorMetadata


def main():  # pragma: no cover
    """Retrieve and display metadata for all operators."""
    operator = OperatorMetadata()
    operator_items = operator.get_operator_metadata()
    for key, value in operator_items.items():
        print(f"Key: {key}, value: {value}")


if __name__ == "__main__":  # pragma: no cover
    main()
