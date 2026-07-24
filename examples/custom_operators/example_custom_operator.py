"""Example custom operator demonstrating how to create custom operators.

This operator adds a custom field to each document in the PyArrow table.
"""

from typing import Any

import pyarrow as pa

from docpipe.core.constants.constants import DocpipeConstants
from docpipe.core.operators.abstract_operator import AbstractOperator, OperatorCategory


class ExampleCustomOperator(AbstractOperator):
    """Example custom operator that adds a custom field to documents.

    This operator demonstrates the minimum requirements for a custom operator:
    - Inherit from AbstractOperator
    - Define short_name, category, and owner class attributes
    - Implement transform(), get_metadata(), and get_required_features() methods

    Note: Setting owner to DocpipeConstants.OWNER_CUSTOM identifies this as a custom operator.
    The category should be one of the standard categories.
    """

    short_name: str = "example_custom"
    category: OperatorCategory = OperatorCategory.Functional
    owner: str | None = DocpipeConstants.OWNER_CUSTOM

    def __init__(self, config: dict[str, Any]):
        """Initialize the custom operator.

        Args:
            config: Configuration dictionary containing operator parameters
        """
        super().__init__(config)
        # Custom configuration parameters
        self.custom_field_name = config.get("custom_field_name", "custom_field")
        self.custom_field_value = config.get("custom_field_value", "custom_value")

    def transform(self, table: pa.Table, file_name: str | None = None) -> tuple[list[pa.Table], dict[str, Any]]:
        """Transform the input table by adding a custom field.

        Args:
            table: Input PyArrow table
            file_name: Optional file name (not used in this operator)

        Returns:
            Tuple of (list of transformed tables, metadata dictionary)
        """
        # Remove columns with dots in their names (e.g., 'doc_id_hash.original')
        # These cause issues with document_set storage
        columns_to_keep = [name for name in table.column_names if "." not in name]
        if len(columns_to_keep) < len(table.column_names):
            table = table.select(columns_to_keep)

        # Add custom field to the table
        custom_column = pa.array([self.custom_field_value] * len(table))
        table = table.append_column(self.custom_field_name, custom_column)

        # Create metadata
        metadata = self.create_base_metadata(total_docs_count=table.num_rows)
        metadata["processed_docs"] = table.num_rows

        return [table], metadata

    @staticmethod
    def get_metadata() -> dict[str, Any]:
        """Return operator metadata for UI display.

        Returns:
            Dictionary containing operator metadata
        """
        return {
            "label": "Example Custom Operator",
            "description": "Adds a custom field to each document",
            "category": OperatorCategory.Functional.value,
            "owner": DocpipeConstants.OWNER_CUSTOM,
            "features": {
                "custom_field_name": {
                    "type": "string",
                    "description": "Name of the custom field to add",
                    "default": "custom_field",
                },
                "custom_field_value": {
                    "type": "string",
                    "description": "Value for the custom field",
                    "default": "custom_value",
                },
            },
        }

    @staticmethod
    def get_required_features() -> list[str]:
        """Return list of required input features.

        Returns:
            List of required column names (empty for this example)
        """
        return []
