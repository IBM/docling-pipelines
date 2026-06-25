"""Test custom operator that converts text to uppercase."""

import pyarrow as pa

from docpipe.core.constants.constants import DocpipeConstants, ExecutionStatus
from docpipe.core.operators.abstract_operator import AbstractOperator, OperatorCategory


class UppercaseOperator(AbstractOperator):
    """Custom operator that converts document content to uppercase.

    This is a simple test operator to demonstrate custom operator loading.
    """

    short_name: str = "uppercase"
    category: OperatorCategory = OperatorCategory.Functional
    owner: str | None = DocpipeConstants.OWNER_CUSTOM

    def __init__(self, *, config: dict):
        super().__init__(config=config)
        self.doc_column = config.get("doc_column", "content")

    def transform(self, table: pa.Table, file_name: str = "") -> tuple[list[pa.Table], dict]:
        """Transform document content to uppercase.

        Args:
            table: Input PyArrow table
            file_name: Optional file name

        Returns:
            Tuple of (list of transformed tables, metadata dict)
        """
        metadata = self.create_base_metadata(total_docs_count=len(table), node_status=ExecutionStatus.COMPLETED)

        # Get the content column
        if self.doc_column not in table.column_names:
            metadata["node_status"] = ExecutionStatus.FAILED.value
            metadata["failed_docs_count"] = len(table)
            return [table], metadata

        # Convert content to uppercase
        content_array = table[self.doc_column]
        uppercase_content = pa.array([text.as_py().upper() if text.as_py() else "" for text in content_array])

        # Replace the content column
        new_table = table.set_column(
            table.column_names.index(self.doc_column),
            self.doc_column,
            uppercase_content,
        )

        metadata["processed_docs"] = len(new_table)
        return [new_table], metadata

    @staticmethod
    def get_metadata() -> dict:
        """Return operator metadata."""
        return {
            "label": "Uppercase Operator",
            "description": "Converts document content to uppercase",
            "category": OperatorCategory.Functional.value,
            "short_name": "uppercase",
        }

    @staticmethod
    def get_required_features() -> list:
        """Return required features."""
        return ["content"]
