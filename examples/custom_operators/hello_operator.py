from typing import Any

import pyarrow as pa

from docpipe.core.constants.constants import AttributeDataTypes, DocpipeConstants
from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.operators.abstract_operator import AbstractOperator, OperatorCategory


class HelloOperator(AbstractOperator):
    """A simple operator that adds a greeting column to the table."""

    # Required class attributes
    short_name: str = "hello"
    category: OperatorCategory = OperatorCategory.Functional
    owner: str | None = DocpipeConstants.OWNER_CUSTOM

    def transform(self, table: pa.Table, file_name: str | None = None) -> tuple[list[pa.Table], dict[str, Any]]:
        """Add a greeting column to the table."""
        # Create greeting values for each row
        greetings = ["Hello from custom operator!"] * table.num_rows

        # Add new column to table
        table = table.append_column("greeting", pa.array(greetings))

        # Return table and metadata
        metadata = self.create_base_metadata(total_docs_count=table.num_rows)
        return [table], metadata

    @staticmethod
    def get_metadata() -> dict[str, Any]:
        """Return operator metadata for UI and validation."""
        return {
            OperatorConstants.Misc.CATEGORY: HelloOperator.category.value,
            OperatorConstants.Misc.IS_OPERATOR_AVAILABLE: True,
            OperatorConstants.Misc.LABEL: "Hello Operator",
            OperatorConstants.Config.FEATURES: {
                "greeting": {
                    OperatorConstants.Misc.NAME: "Greeting",
                    OperatorConstants.Config.DESCRIPTION: "A friendly greeting message",
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                    OperatorConstants.Misc.TAGS: [OperatorConstants.Misc.MANDATORY],
                }
            },
            OperatorConstants.Config.ATTRIBUTES: {},
        }

    @staticmethod
    def get_required_features() -> list[str]:
        """Return list of required input columns."""
        return []  # No specific columns required
