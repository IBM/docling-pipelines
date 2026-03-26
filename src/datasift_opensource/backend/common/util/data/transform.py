"""Data transformation utilities for PyArrow table operations."""

from typing import Any

import pyarrow as pa

# Try to import TransformUtils from data-prep-toolkit-transforms
try:
    from data_processing.utils import TransformUtils

    HAS_TRANSFORM_UTILS: bool = True
except ImportError:
    HAS_TRANSFORM_UTILS: bool = False

    # Fallback implementation
    class TransformUtils:
        """Fallback implementation for TransformUtils when data_processing is not available."""

        @staticmethod
        def add_column(table: pa.Table, name: str, content: list[Any]) -> pa.Table:
            """
            Add a column to a PyArrow table.

            Args:
                table: The PyArrow table to add a column to
                name: The name of the new column
                content: The content/data for the new column

            Returns:
                A new PyArrow table with the added column
            """
            # Infer the type from the content
            new_column: pa.Array = pa.array(content)
            new_field: pa.Field = pa.field(name, new_column.type)
            return table.append_column(new_field, new_column)


__all__ = ["HAS_TRANSFORM_UTILS", "TransformUtils"]

# Made with Bob