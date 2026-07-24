"""Shared utilities for VectorDB adapters.

This module contains common functionality used across different VectorDB adapters
(OpenSearch, Milvus, etc.) to avoid code duplication and ensure consistent behavior.
"""

import json
from typing import Any

import pyarrow as pa

from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger(__name__)


def calculate_batch_size_bytes(*, documents: list[dict[str, Any]]) -> int:
    """Calculate approximate size of documents in bytes.

    This utility function estimates the memory footprint of a batch of documents
    by serializing them to JSON and measuring the byte size. Used for batch
    size optimization across all VectorDB adapters.

    Args:
        documents: List of documents to measure

    Returns:
        Size in bytes, or 0 if calculation fails
    """
    try:
        return len(json.dumps(documents).encode("utf-8"))
    except Exception:
        return 0


def detect_vector_dimension(*, table: pa.Table, embeddings_column: str) -> int | None:  # NOSONAR python:S3776
    """
    Auto-detect vector dimension from the embeddings column in the PyArrow table.

    Handles both flat embeddings and nested (chunked) embeddings:
    - Flat: [float1, float2, ..., floatN] -> dimension is length of list
    - Nested: [[emb1], [emb2], ...] -> dimension is length of first inner list
    - Memmap files: Reads dimension from file metadata

    Args:
        table: PyArrow table containing embeddings
        embeddings_column: Name of the embeddings column

    Returns:
        Detected dimension or None if detection fails
    """
    if embeddings_column not in table.column_names:
        logger.debug(f"Embeddings column '{embeddings_column}' not found in table")
        return None

    if table.num_rows == 0:
        logger.debug("Cannot detect dimension from empty table")
        return None

    try:
        from docpipe.core.constants.constants import DocpipeConstants

        embeddings_col: pa.ChunkedArray = table[embeddings_column]

        for idx in range(min(table.num_rows, 10)):  # Check first 10 rows
            embedding_value: Any = embeddings_col[idx].as_py()

            if embedding_value is None:
                continue

            # Handle memmap file path references
            if isinstance(embedding_value, dict) and DocpipeConstants.EMBEDDINGS_MEMMAP_FILE in embedding_value:
                from docpipe.utils.core.memmap_file_utils import read_embedding_metadata

                embeddings_filepath = embedding_value[DocpipeConstants.EMBEDDINGS_MEMMAP_FILE]
                logger.debug(f"Reading dimension from memmap file metadata: {embeddings_filepath}")

                # Get dimension directly from metadata
                dim = read_embedding_metadata(embeddings_filepath)
                logger.info(f"Auto-detected vector dimension: {dim} (from memmap file metadata)")
                return dim

            if not isinstance(embedding_value, list):
                logger.warning(f"Embedding at row {idx} is not a list: {type(embedding_value)}")
                continue

            if len(embedding_value) == 0:
                continue

            # Check if this is nested embeddings (chunked)
            if isinstance(embedding_value[0], list):
                # Nested structure: [[emb1], [emb2], ...]
                if len(embedding_value[0]) > 0:
                    nested_dimension: int = len(embedding_value[0])
                    logger.info(f"Auto-detected vector dimension: {nested_dimension} (from chunked embeddings)")
                    return nested_dimension
            elif isinstance(embedding_value[0], (int, float)):
                # Flat structure: [float1, float2, ...]
                flat_dimension: int = len(embedding_value)
                logger.info(f"Auto-detected vector dimension: {flat_dimension} (from flat embeddings)")
                return flat_dimension
            else:
                logger.warning(
                    f"Unexpected embedding structure at row {idx}: first element is {type(embedding_value[0])}"
                )
                continue

        logger.warning("Could not find valid embeddings in first 10 rows for dimension detection")
        return None

    except Exception as e:
        logger.warning(f"Error detecting vector dimension: {e!s}")
        return None


def detect_all_vector_dimensions(*, table: pa.Table, vector_columns: list[str]) -> dict[str, int]:
    """
    Detect dimensions for all specified vector columns in the table.

    Args:
        table: PyArrow table containing embeddings
        vector_columns: List of column names to detect dimensions for

    Returns:
        Dictionary mapping column names to their detected dimensions.
        Only includes columns where dimension was successfully detected.
    """
    dimension_mapping: dict[str, int] = {}

    for column_name in vector_columns:
        detected_dim = detect_vector_dimension(table=table, embeddings_column=column_name)
        if detected_dim is not None:
            dimension_mapping[column_name] = detected_dim
            logger.info(f"Detected dimension {detected_dim} for column '{column_name}'")
        else:
            logger.warning(f"Could not detect dimension for column '{column_name}'")

    return dimension_mapping
