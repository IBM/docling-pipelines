"""
MergeOperator for combining multiple PyArrow tables.

This operator supports two merge strategies:
1. Row Merge (Concatenation): Stacks tables vertically
2. Column Merge (Join): Joins tables horizontally on ID column
"""

from logging import Logger
from typing import Any

import pyarrow as pa

from docpipe.core.constants.constants import (
    AttributeDataTypes,
    DocpipeConstants,
    ExecutionStatus,
    Metrics,
)
from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.operators.abstract_operator import AbstractOperator, OperatorCategory
from docpipe.core.operators.operator_utils import OperatorUtils
from docpipe.exceptions.docpipe_exceptions import DocpipeException, FlowExecutionFailedException
from docpipe.exceptions.error_messages import ValidationCodeMessages, ValidationMessage
from docpipe.utils.infrastructure.logging import get_logger

logger: Logger = get_logger()


class MergeOperator(AbstractOperator):
    """
    Merges two or more PyArrow tables using configurable strategies.

    Supports two merge types:
    - rows: Concatenates tables vertically (one after another)
    - columns: Joins tables horizontally on ID column (inner_join or full_outer)

    The operator handles both supported join types (primitives) and unsupported types
    (nested structures like lists/structs) by remapping them after the join operation.
    """

    short_name: str = OperatorConstants.Operators.MERGE
    category: OperatorCategory = OperatorCategory.Functional
    owner = DocpipeConstants.OWNER_DOCPIPE

    def __init__(self, config: dict[str, Any]) -> None:
        """
        Initialize the MergeOperator.

        Args:
            config: Configuration dictionary containing:
                - merge_type: "rows" or "columns" (required)
                - column_option: "inner_join" or "full_outer" (required when merge_type="columns")
                - input_links: List of input link configurations (minimum 2 required)
        """
        super().__init__(config)
        self.merge_type: str | None = config.get(OperatorConstants.Merge.MERGE_TYPE)
        self.column_option: str | None = config.get(OperatorConstants.Merge.COLUMN_OPTION)
        self.common_log_arguments: dict[str, Any] = {
            DocpipeConstants.JOB_ID: self.job_id,
            DocpipeConstants.JOB_RUN_ID: self.job_run_id,
        }
        self.input_links: list[dict[str, Any]] = config.get(OperatorConstants.Merge.INPUT_LINKS, [])

    @staticmethod
    def get_metadata() -> dict[str, Any]:
        """Return operator metadata for registration and discovery."""
        return {
            OperatorConstants.Misc.SDK: True,
            OperatorConstants.Misc.CATEGORY: MergeOperator.category.value,
            OperatorConstants.Misc.IS_OPERATOR_AVAILABLE: MergeOperator.is_available(),
            OperatorConstants.Misc.LABEL: "Merge Operator",
            OperatorConstants.Config.DESCRIPTION: "Merge multiple input tables by combining rows or columns.",
            OperatorConstants.Config.ATTRIBUTES: {
                OperatorConstants.Merge.MERGE_TYPE: {
                    OperatorConstants.Misc.NAME: "Merge Type",
                    OperatorConstants.Config.DESCRIPTION: "Merge configuration specified by the user (Rows or Columns)",
                    OperatorConstants.Config.REQUIRED: True,
                    OperatorConstants.Config.DEFAULT: OperatorConstants.Merge.ROWS,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
                OperatorConstants.Merge.COLUMN_OPTION: {
                    OperatorConstants.Misc.NAME: "Column Option",
                    OperatorConstants.Config.DESCRIPTION: "Column configuration specified by the user (inner_join or full_outer)",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
            },
        }

    def _validate_input_links(self, *, errors: list) -> None:
        """Validate that at least two input links are provided."""
        if not self.should_validate_field(field_value=self.input_links):
            return

        # Check minimum number of links
        if len(self.input_links) < 2:
            errors.append(
                ValidationMessage(
                    message=ValidationCodeMessages.MERGE_INPUT_LINKS_INSUFFICIENT.value,
                    message_code=ValidationCodeMessages.MERGE_INPUT_LINKS_INSUFFICIENT.name,
                )
            )

        # Validate link names
        existing_link_names: set[str] = set()
        for node in self.input_links:
            OperatorUtils.validate_link_name(
                link_name=node["link_name"],
                existing_link_names=existing_link_names,
                errors=errors,
            )

    def _validate_merge_type_provided(self, *, errors: list) -> bool:
        """Check if merge type is provided. Returns True if valid to continue."""
        if not self.should_validate_field(field_value=self.merge_type):
            return False

        if not self.merge_type:
            errors.append(
                ValidationMessage(
                    message=ValidationCodeMessages.MERGE_TYPE_NOT_PROVIDED.value,
                    message_code=ValidationCodeMessages.MERGE_TYPE_NOT_PROVIDED.name,
                )
            )
            return False

        return True

    def _validate_merge_type_value(self, *, errors: list) -> None:
        """Validate that merge type is one of the supported values."""
        if self.merge_type not in [OperatorConstants.Merge.ROWS, OperatorConstants.Merge.COLUMNS]:
            errors.append(
                ValidationMessage.create(
                    message=ValidationCodeMessages.INVALID_MERGE_TYPE.value.format(merge_type=self.merge_type),
                    message_code=ValidationCodeMessages.INVALID_MERGE_TYPE.name,
                    merge_type=self.merge_type,
                )
            )

    def _validate_column_option(self, *, errors: list) -> None:
        """Validate column_option when merge_type is COLUMNS."""
        # Only validate column_option if merge_type is COLUMNS
        if self.merge_type != OperatorConstants.Merge.COLUMNS:
            return

        # Check if field should be validated
        if not self.should_validate_field(field_value=self.column_option):
            return

        # Validate column_option is provided
        if not self.column_option:
            errors.append(
                ValidationMessage(
                    message=ValidationCodeMessages.MERGE_COLUMN_OPTION_NOT_PROVIDED.value,
                    message_code=ValidationCodeMessages.MERGE_COLUMN_OPTION_NOT_PROVIDED.name,
                )
            )

        # Validate column_option value
        if self.column_option not in [
            OperatorConstants.Columns.INNER_JOIN_DUPLICATE_COLUMN,
            OperatorConstants.Merge.FULL_OUTER_JOIN,
        ]:
            errors.append(
                ValidationMessage.create(
                    message=ValidationCodeMessages.MERGE_INVALID_COLUMN_OPTION.value.format(
                        column_option=self.column_option
                    ),
                    message_code=ValidationCodeMessages.MERGE_INVALID_COLUMN_OPTION.name,
                    column_option=self.column_option,
                )
            )

    def validate(self, errors: list, warnings: list, available_features: list) -> None:
        """Validate Merge operator configuration."""
        self._validate_input_links(errors=errors)

        if self._validate_merge_type_provided(errors=errors):
            self._validate_merge_type_value(errors=errors)
            self._validate_column_option(errors=errors)

    def transform(self, table: pa.Table, **kwargs) -> tuple[list[pa.Table], dict[str, Any]]:
        """
        Merge multiple tables or validate single table input.

        Multi-table data is passed via kwargs['tables'] by the orchestrator.
        If no tables dict is provided, this is a validation-only call.

        Args:
            table: Primary input table (used for validation)
            **kwargs: Additional arguments, including 'tables' dict for multi-input merging

        Returns:
            Tuple of (list of merged tables, metadata dictionary)
        """
        # Validation: Check minimum number of input links
        if len(self.input_links) < 2:
            raise FlowExecutionFailedException(
                "At least two input links are required for merging. Aborting..", status_code=400
            )

        # Get tables from kwargs (orchestrator provides this for multi-input operators)
        tables: dict[str, pa.Table] | None = kwargs.get("tables")

        # If no multi-table dict provided, this is validation-only call
        if not tables:
            metadata: dict[str, Any] = self.create_base_metadata(
                total_docs_count=OperatorUtils.find_doc_count(table=table)
            )
            metadata[Metrics.External.PROCESSED_DOCS] = len(table)
            return [table], metadata

        # ACTUAL MERGE LOGIC
        # Filter out empty tables
        tables = {name: t for name, t in tables.items() if t.num_rows > 0}

        if not tables:
            logger.warning("Cannot merge empty Tables. Skipping..", extra=self.common_log_arguments)
            metadata = self.create_base_metadata(
                total_docs_count=0, node_status=ExecutionStatus.COMPLETED_WITH_WARNINGS.value
            )
            metadata[Metrics.External.PROCESSED_DOCS] = 0
            return [pa.table({})], metadata

        if len(tables) == 1:
            single_table: pa.Table = next(iter(tables.values()))
            total_docs_count: int = OperatorUtils.find_doc_count(table=single_table)
            metadata = self.create_base_metadata(total_docs_count=total_docs_count)
            metadata[Metrics.External.PROCESSED_DOCS] = total_docs_count
            return [single_table], metadata

        # Perform merge based on configuration
        merged_table: pa.Table

        if self.merge_type == OperatorConstants.Merge.ROWS:
            merged_table = self._merge_rows(tables=tables)
        elif self.merge_type == OperatorConstants.Merge.COLUMNS and self.column_option in (
            OperatorConstants.Columns.INNER_JOIN_DUPLICATE_COLUMN,
            OperatorConstants.Merge.FULL_OUTER_JOIN,
        ):
            merged_table = self._merge_columns(tables=tables)
        else:
            raise DocpipeException(f"Unsupported merge configuration: {self.merge_type}, {self.column_option}")

        # Initialize metadata
        metadata = self.create_base_metadata(total_docs_count=OperatorUtils.find_doc_count(table=merged_table))
        metadata[Metrics.External.PROCESSED_DOCS] = len(merged_table)
        return [merged_table], metadata

    def _merge_rows(self, *, tables: dict[str, pa.Table]) -> pa.Table:
        """
        Merge tables by concatenating rows vertically.

        Args:
            tables: Dictionary of tables to merge

        Returns:
            Concatenated PyArrow table

        Raises:
            FlowExecutionFailedException: If duplicate document IDs are found
        """
        logger.info(
            f"Merging {len(tables)} tables using merge type '{self.merge_type}'.",
            extra=self.common_log_arguments,
        )

        id_column: str = OperatorConstants.Columns.ID

        # Collect all ID arrays using PyArrow operations
        # Convert ChunkedArray to Array using combine_chunks()
        id_arrays: list[pa.Array] = []
        for table in tables.values():
            id_col = table.column(id_column)
            if isinstance(id_col, pa.ChunkedArray):
                id_arrays.append(id_col.combine_chunks())
            else:
                id_arrays.append(id_col)

        # Concatenate all ID arrays efficiently using PyArrow
        all_ids_array: pa.Array = pa.concat_arrays(id_arrays)

        # Check for duplicates by comparing total length vs unique length
        # This is more efficient than converting to Python list first
        total_count = len(all_ids_array)
        unique_count = len(all_ids_array.unique())

        if total_count != unique_count:
            # Only convert to Python list for error reporting when duplicates are found
            err_msg: str = (
                "The Merging operator received the same documents from multiple branches. "
                'In this case, the merge option "Merge rows from all tables, one after another" cannot be used.'
            )
            logger.error(msg=err_msg, extra=self.common_log_arguments)
            raise FlowExecutionFailedException(message=err_msg, status_code=400)

        merged_table: pa.Table = pa.concat_tables(list(tables.values()), promote_options="default")
        logger.info(
            f"Merged {len(tables)} tables with row counts: {[t.num_rows for t in tables.values()]}",
            extra=self.common_log_arguments,
        )

        return merged_table

    def _merge_columns(self, *, tables: dict[str, pa.Table]) -> pa.Table:  # NOSONAR python:S3776
        """
        Merge tables by joining columns horizontally on ID.

        Args:
            tables: Dictionary of tables to merge

        Returns:
            Joined PyArrow table
        """
        logger.info(
            f"Merging {len(tables)} tables using merge type '{self.merge_type}' "
            f"with column option '{self.column_option}'.",
            extra=self.common_log_arguments,
        )

        link_names: list[str] = []
        join_key: str = OperatorConstants.Columns.ID
        join_type: str = (
            "inner" if self.column_option == OperatorConstants.Columns.INNER_JOIN_DUPLICATE_COLUMN else "full outer"
        )

        # STEP 1: INITIAL TABLE
        table_iter = iter(tables.items())
        first_link_name, first_table = next(table_iter)

        link_names.append(first_link_name)

        first_supported, first_unsupported = split_supported_fields(table=first_table)
        merged_table: pa.Table = first_supported

        # Store unsupported columns along with their table-specific ID arrays
        unsupported_columns: dict[str, tuple[pa.Array, pa.Array]] = {}

        if first_unsupported.num_columns > 0:
            # Attach ID to unsupported subset
            first_unsupported = first_unsupported.append_column(join_key, first_table[join_key])
            for col in first_unsupported.column_names:
                # Store tuple: (column array, corresponding table ID array)
                unsupported_columns[col] = (
                    first_unsupported[col].combine_chunks(),
                    first_unsupported[join_key].combine_chunks(),
                )

        # STEP 2: PROCESS REMAINING TABLES
        for link_name, table in table_iter:
            link_names.append(link_name)
            table_supported, table_unsupported = split_supported_fields(table=table)

            # Perform join on supported fields
            merged_table = merged_table.join(
                table_supported,
                keys=join_key,
                join_type=join_type,
                right_suffix=f"_{link_name}",
            )

            # Process unsupported fields
            if table_unsupported.num_columns > 0:
                # Attach ID column to unsupported subset
                table_unsupported = table_unsupported.append_column(join_key, table[join_key])

                for col in table_unsupported.column_names:
                    proposed_col_name: str = col
                    if proposed_col_name in merged_table.column_names or proposed_col_name in unsupported_columns:
                        proposed_col_name = f"{col}_{link_name}"

                    if proposed_col_name in unsupported_columns:
                        raise DocpipeException(f"Duplicate unsupported column after suffixing: {proposed_col_name}")

                    # Store both column array and table-specific ID array
                    unsupported_columns[proposed_col_name] = (
                        table_unsupported[col].combine_chunks(),
                        table_unsupported[join_key].combine_chunks(),
                    )

        # STEP 3: REATTACH UNSUPPORTED COLUMNS USING ID-MATCHING
        # Get merged IDs as PyArrow array for efficient operations
        merged_ids_array: pa.Array = merged_table[join_key]

        for col_name, (arr, arr_id) in unsupported_columns.items():
            if col_name == join_key:
                continue

            # Build mapping: table-specific ID → index
            id_index_map: dict[str, int] = build_id_index(arr_id=arr_id)

            # Convert merged_ids to list only once for lookup
            merged_ids_list: list[str] = merged_ids_array.to_pylist()
            py_array: list = arr.to_pylist()

            # Build remapped array using list comprehension (still efficient for this use case)
            remapped: list = [py_array[id_index_map[mid]] if mid in id_index_map else None for mid in merged_ids_list]

            merged_table = merged_table.append_column(col_name, pa.array(remapped, type=arr.type))

        # Remove any temporary ID columns if they exist
        temp_id_cols: list[str] = [f"{join_key}_{link}" for link in link_names]
        merged_table = merged_table.drop([c for c in temp_id_cols if c in merged_table.column_names])

        logger.info(
            f"Merged {len(merged_table)} tables with row counts: {[t.num_rows for t in tables.values()]}",
            extra=self.common_log_arguments,
        )

        return merged_table


def is_supported_join_type(field: pa.Field) -> bool:
    """
    Check if a field's type is supported in a join operation.

    Args:
        field: PyArrow field to check

    Returns:
        True if the field type supports joins (primitives), False otherwise
    """
    return (
        pa.types.is_boolean(field.type)
        or pa.types.is_integer(field.type)
        or pa.types.is_floating(field.type)
        or pa.types.is_string(field.type)
        or pa.types.is_timestamp(field.type)
    )


def split_supported_fields(*, table: pa.Table) -> tuple[pa.Table, pa.Table]:
    """
    Split a table into joinable and non-joinable columns.

    Args:
        table: PyArrow table to split

    Returns:
        Tuple of (supported_table, unsupported_table)
    """
    supported: list[str] = []
    unsupported: list[str] = []

    for field in table.schema:
        if is_supported_join_type(field=field):
            supported.append(field.name)
        else:
            unsupported.append(field.name)

    return table.select(supported), table.select(unsupported)


def build_id_index(*, arr_id: pa.Array) -> dict[str, int]:
    """
    Build a mapping from ID to index for an unsupported subset.

    Args:
        arr_id: PyArrow array of IDs

    Returns:
        Dictionary mapping ID values to their indices
    """
    id_list: list = arr_id.to_pylist()
    return {id_value: idx for idx, id_value in enumerate(id_list)}
