#!/usr/bin/env python3
"""
Example: Document Deduplication

This example demonstrates how to remove duplicate documents based on content
using the EdedupOperator.
"""

import sys
from pathlib import Path
from typing import Any

import pyarrow as pa

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.operators.quality.ededup import EdedupOperator
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger()


def main() -> None:
    """Test the deduplication operator with sample data."""
    # 1. Create a PyArrow table with duplicate content
    content: list[str] = [
        "Document content 1",
        "Document content 2",
        "Document content 1",  # Duplicate of first document
    ]
    doc_id_hash: list[str] = [str(101), str(102), str(103)]
    id: list[str] = [str(101), str(102), str(103)]
    name: list[str] = ["Doc 1", "Doc 2", "Doc 3"]

    data: dict[str, list[str]] = {
        OperatorConstants.Columns.DOC_COLUMN_DEFAULT: content,
        OperatorConstants.Columns.DOC_ID_HASH_DEFAULT: doc_id_hash,
        OperatorConstants.Misc.ID: id,
        OperatorConstants.Misc.NAME: name,
    }

    input_table: pa.Table = pa.table(data)
    logger.info(f"\nInput PyArrow Table : {input_table}\n")

    config: dict[str, Any] = {}

    operator: EdedupOperator = EdedupOperator(config=config)

    print(operator)

    table: list[pa.Table]
    metadata: dict[str, Any]
    table, metadata = operator.transform(input_table)
    logger.info(f"Ededup Output Table : {table}")
    logger.info(f"Ededup Output MetaData : {metadata}")


if __name__ == "__main__":
    main()
