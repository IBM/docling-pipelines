"""Valid custom operator for testing."""

import pyarrow as pa

from docpipe.core.constants.constants import DocpipeConstants
from docpipe.core.operators.abstract_operator import AbstractOperator, OperatorCategory


class ValidCustomOperator(AbstractOperator):
    """A valid custom operator for testing."""

    short_name: str = "valid_custom"
    category: OperatorCategory = OperatorCategory.Functional
    owner: str | None = DocpipeConstants.OWNER_CUSTOM

    def __init__(self, config: dict):
        super().__init__(config)
        self.test_param = config.get("test_param", "default")

    def transform(self, table: pa.Table, file_name: str | None = None) -> tuple[list[pa.Table], dict]:
        """Add a test column to the table."""
        test_column = pa.array([self.test_param] * len(table))
        table = table.append_column("test_field", test_column)

        metadata = self.create_base_metadata(total_docs_count=table.num_rows)
        return [table], metadata

    def get_metadata(self) -> dict:
        """Return operator metadata."""
        return {
            "label": "Valid Custom Operator",
            "description": "Test operator for validation",
            "category": self.category,
        }

    def get_required_features(self) -> list:
        """Return required features."""
        return []
