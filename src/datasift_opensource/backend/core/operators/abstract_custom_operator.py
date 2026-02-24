import pyarrow as pa
from typing import Any
from datasift_opensource.backend.core.operators.abstract_operator import AbstractOperator


class AbstractCustomOperator(AbstractOperator):

    def __init__(self, config: dict[str, Any]):
        super().__init__(config=config)

    def get_removed_and_added_columns(self) -> (set[str], list[pa.Field]):
        """
        Return the details of the removed and added columns after the transform.

        Returns:
            removed_columns (set[str]): Set of column names removed during the transform.
            added_columns (list[pa.Field]): List of column schemas added during the transform.
        """
        raise NotImplementedError('subclasses must implement this method')

    def get_metadata_fields_to_accumulate(self) -> list[str]:
        """
        Return the metadata field names that needs to be accumulated.

        Returns:
            list[str]: List of field to be accumulated.
        """
        raise NotImplementedError('subclasses must implement this method')
