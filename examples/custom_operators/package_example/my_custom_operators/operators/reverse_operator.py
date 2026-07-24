"""Reverse text operator."""

from typing import Any

import pyarrow as pa

from docpipe.core.constants.constants import DocpipeConstants
from docpipe.core.operators.abstract_operator import AbstractOperator, OperatorCategory


class ReverseOperator(AbstractOperator):
    """Reverses text content.

    This operator demonstrates a simple text transformation that can be
    distributed as part of a custom operator package.
    """

    short_name: str = "reverse_text"
    category: OperatorCategory = OperatorCategory.Functional
    owner: str | None = DocpipeConstants.OWNER_CUSTOM

    def __init__(self, config: dict[str, Any]):
        """Initialize the reverse operator.

        Args:
            config: Configuration dictionary containing operator parameters
        """
        super().__init__(config)
        self.text_column = config.get("text_column", "text")

    def transform(self, table: pa.Table, file_name: str | None = None) -> tuple[list[pa.Table], dict[str, Any]]:
        """Reverse text content.

        Args:
            table: Input PyArrow table
            file_name: Optional file name (not used)

        Returns:
            Tuple of (list of tables, metadata dict)
        """
        if self.text_column not in table.column_names:
            raise ValueError(f"Column '{self.text_column}' not found in table")

        # Get the text column
        text_array = table.column(self.text_column)

        # Reverse text
        reversed_array = pa.array([text.as_py()[::-1] if text.as_py() else None for text in text_array])

        # Replace the column
        column_index = table.column_names.index(self.text_column)
        new_table = table.set_column(column_index, self.text_column, reversed_array)

        # Create metadata
        metadata = self.create_base_metadata(total_docs_count=table.num_rows)
        metadata["processed_docs"] = table.num_rows

        return [new_table], metadata

    @staticmethod
    def get_metadata() -> dict[str, Any]:
        """Get operator metadata.

        Returns:
            Dictionary containing operator metadata
        """
        return {
            "short_name": ReverseOperator.short_name,
            "category": ReverseOperator.category.value,
            "owner": ReverseOperator.owner,
            "description": "Reverses text content",
            "parameters": {
                "text_column": {
                    "type": "string",
                    "description": "Name of the column containing text to reverse",
                    "default": "text",
                }
            },
        }
