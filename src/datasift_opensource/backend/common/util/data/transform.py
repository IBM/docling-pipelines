"""Data transformation utilities for PyArrow table operations.
   This class serves as a compatibility shim between datasift-opensource 
   and the external data-prep-toolkit-transforms library. It:

Primary mode: Imports TransformUtils from data_processing.utils (the external toolkit)
Fallback mode: Provides a minimal local implementation if the external library is unavailable
Centralizes PyArrow table column operations across all operators

"""

from typing import Any

import pyarrow as pa

# Try to import TransformUtils from data-prep-toolkit-transforms
try:
    from data_processing.utils import TransformUtils
except ImportError:
    
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


__all__ = ["TransformUtils"]

# Made with Bob