"""Invalid operator missing SHORT_NAME attribute."""

import pyarrow as pa

from docpipe.core.operators.abstract_operator import AbstractOperator, OperatorCategory


class InvalidOperatorNoShortName(AbstractOperator):
    """Invalid operator without SHORT_NAME."""

    category: OperatorCategory = OperatorCategory.Functional

    def __init__(self, config: dict):
        super().__init__(config)

    def transform(self, table: pa.Table, file_name: str | None = None) -> tuple[list[pa.Table], dict]:
        metadata = self.create_base_metadata(total_docs_count=table.num_rows)
        return [table], metadata

    def get_metadata(self) -> dict:
        return {"label": "Invalid Operator"}

    def get_required_features(self) -> list:
        return []
