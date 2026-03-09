import ast
import re
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import duckdb
import pyarrow as pa

from common.exceptions.datasift_exceptions import DatasiftException
from common.exceptions.error_codes import ErrorCode
from common.exceptions.error_messages import ValidationCodeMessages, ValidationMessage
from common.util.constants import (
    AttributeDataTypes,
    ExecutionStatus,
    Metrics,
    OperatorConstants,
)
from common.util.log import get_logger
from common.util.operator_utils import find_doc_count, validate_filter_criteria
from core.operators.abstract_operator import AbstractOperator, OperatorCategory
from core.operators.operator_utils import OperatorUtils

logger = get_logger()


""" AST Key holds the list of filter criteria (in SQL WHERE clause format)"""

""" Key holds the logical operators that joins filter criteria (AND or OR)"""

""" AST Key holds the list of features to drop after filtering"""
FILTER_LOGICAL_OPERATOR_AND: str = "AND"
FILTER_LOGICAL_OPERATOR_OR: str = "OR"
VALID_FILTER_LOGICAL_OPERATORS: List[str] = [
    FILTER_LOGICAL_OPERATOR_AND,
    FILTER_LOGICAL_OPERATOR_OR,
]
# defaults
FILTER_CRITERIA_DEFAULT: List[Any] = ast.literal_eval("[]")
""" The default list of filter criteria (in SQL WHERE clause format)"""
FILTER_LOGICAL_OPERATOR_DEFAULT: str = FILTER_LOGICAL_OPERATOR_AND
FILTER_FEATURES_TO_DROP_DEFAULT: List[Any] = ast.literal_eval("[]")
""" The default list of features to drop"""

IS_NULL: str = "IS NULL"
IS_NOT_NULL: str = "IS NOT NULL"


class Mode(Enum):
    COLUMNS_TO_DROP = "features to drop"
    FILTER_CRITERIA_JSON = "filter criteria (JSON)"
    FILTER_CRITERIA_LIST = "filter criteria (list)"


class SQLFilterOperator(AbstractOperator):
    """
    Implements filtering - select from a pyarrow.Table a set of rows that
    satisfy a set of filtering criteria
    """

    short_name: str = OperatorConstants.SQL_FILTER
    category: OperatorCategory = OperatorCategory.Quality

    def __init__(self, config: Dict[str, Any]) -> None:
        """
        Initialize based on the dictionary of configuration information.
        This is generally called with configuration parsed from the CLI arguments defined
        by the companion runtime, FilterTransformRuntime.  If running from the Ray orchestrator,
        these will be provided by that class with help from the RayMutatingDriver.
        """

        super().__init__(config)
        self.filter_criteria: List[str] = config.get(
            OperatorConstants.FILTER_CRITERIA_LIST, FILTER_CRITERIA_DEFAULT
        )
        self.logical_operator: str = config.get(
            OperatorConstants.FILTER_LOGICAL_OPERATOR_KEY,
            FILTER_LOGICAL_OPERATOR_DEFAULT,
        )
        self.features_to_drop: List[str] = config.get(
            OperatorConstants.FILTER_FEATURES_TO_DROP_KEY,
            FILTER_FEATURES_TO_DROP_DEFAULT,
        )
        self.columns_to_drop: List[str] = self.features_to_drop
        self.filter_criteria_json: Optional[Dict[str, Any]] = config.get(
            OperatorConstants.FILTER_CRITERIA_JSON
        )

    def validate(
        self,
        errors: List[Union[str, ValidationMessage]],
        warnings: List[str],
        available_features: List[str],
    ) -> None:
        """
        Validate operator conditions.
        """
        # Check if at least one filter criteria is provided (only validate non-parameterized fields)
        should_validate_criteria = self.should_validate_field(
            field_value=self.filter_criteria
        )
        should_validate_json = self.should_validate_field(
            field_value=self.filter_criteria_json
        )

        # Only validate if both fields are not parameterized
        if should_validate_criteria and should_validate_json:
            criteria_valid, json_valid = validate_filter_criteria(
                criteria_list=self.filter_criteria,
                criteria_json=self.filter_criteria_json,
            )

            # Warn if both are invalid/empty
            # If either field is parameterized, skip warning (it will be provided at runtime)
            if not (criteria_valid or json_valid):
                warnings.append("Filter criteria must have at least one condition.")

        # Validate features to drop
        if self.should_validate_field(field_value=self.features_to_drop):
            protected_features = {
                OperatorConstants.ID: ValidationCodeMessages.SQL_FILTER_ID_DROP_ATTEMPTED,
                OperatorConstants.DOC_COLUMN_DEFAULT: ValidationCodeMessages.SQL_FILTER_CONTENT_DROP_ATTEMPTED,
                OperatorConstants.PAGES_PROCESSED_COLUMN: ValidationCodeMessages.SQL_FILTER_PAGES_DROP,
            }

            for feature, error_msg in protected_features.items():
                if feature in self.features_to_drop:
                    errors.append(
                        ValidationMessage(
                            message=error_msg.value, message_code=error_msg.name
                        )
                    )

        # Validate filter criteria columns - only if at least one is not parameterized
        criteria_to_validate = None
        if should_validate_json and self.filter_criteria_json:
            criteria_to_validate = self.filter_criteria_json
        elif should_validate_criteria and self.filter_criteria:
            criteria_to_validate = self.filter_criteria

        if criteria_to_validate:
            criteria_columns = extract_columns(criteria_to_validate)

            # Identify invalid features
            invalid_features = [
                feature
                for feature in criteria_columns
                if feature not in available_features
            ]
            if invalid_features:
                errors.append(
                    ValidationMessage(
                        message=(
                            f"Invalid feature name(s): {', '.join(sorted(invalid_features))}. "
                            f"Please ensure the filter_criteria has features from {', '.join(available_features)}."
                        ),
                        message_code=ValidationCodeMessages.SQL_FILTER_INVALID_COLUMN.name,
                    )
                )

        # Validate features to drop columns
        if self.should_validate_field(field_value=self.features_to_drop):
            drop_column_validation = self.has_invalid_columns(
                input_table_columns_set=set(available_features),
                mode=Mode.COLUMNS_TO_DROP,
            )
            if drop_column_validation and isinstance(
                drop_column_validation, (set, list)
            ):
                errors.append(
                    f"Invalid feature name in the feature drop list: {', '.join(drop_column_validation)}. Please select features from {', '.join(available_features)}"
                )

    def transform(self, table: pa.Table) -> Tuple[List[pa.Table], Dict[str, Any]]:
        """
        This implementation filters the input table using a SQL statement and
        returns the filtered table and execution stats
        :param table: input table
        :return: list of output tables and custom statistics
        """
        # Initialize metadata
        metadata: Dict[str, Any] = self.create_base_metadata(
            total_docs_count=find_doc_count(table=table)
        )

        filtered_table: List[pa.Table] = self._dpk_transform(
            table=table, metadata=metadata
        )
        if not metadata.get(Metrics.External.SKIPPED_DOCS_COUNT):
            metadata.update(
                OperatorUtils.find_skipped_docs(
                    input_table=table,
                    output_table=filtered_table[0],
                    reason="Document Filtered out based on the specified filter criteria.",
                )
            )
        return filtered_table, metadata

    def _dpk_transform(
        self, table: pa.Table, metadata: Dict[str, Any]
    ) -> List[pa.Table]:
        """
        This implementation filters the input table using a SQL statement and
        returns the filtered table and execution stats
        :param table: input table
        :return: list of output tables
        """

        # move table under a different name, to avoid SQL query parsing error
        input_table: pa.Table = table
        total_docs: int = input_table.num_rows
        total_columns: int = input_table.num_columns
        total_bytes: int = input_table.nbytes
        input_table_columns_set: Set[str] = set(input_table.column_names)

        # initialize the metadata dictionary
        metadata["total_docs_count"] = total_docs
        metadata["total_bytes_count"] = total_bytes
        metadata["total_columns_count"] = total_columns

        # initialize the SQL statement used for filtering
        sql_statement: str = "SELECT * FROM input_table"
        con: Optional[duckdb.DuckDBPyConnection] = None

        if self.filter_criteria_json:
            if self.has_invalid_columns(
                input_table_columns_set=input_table_columns_set,
                metadata=metadata,
                mode=Mode.FILTER_CRITERIA_JSON,
            ):
                return [table]
            sql_where: str = json_to_sql_where(self.filter_criteria_json)
            sql_statement = sql_statement + " " + sql_where
            con = duckdb.connect()
        elif len(self.filter_criteria) > 0:
            if self.has_invalid_columns(
                input_table_columns_set=input_table_columns_set,
                metadata=metadata,
                mode=Mode.FILTER_CRITERIA_LIST,
            ):
                return [table]

            # populate metadata with filtering stats for each filter criterion
            con = duckdb.connect()
            for filter_criterion in self.filter_criteria:
                criterion_sql: str = f"{sql_statement} WHERE {filter_criterion}"
                filter_table: pa.Table = con.execute(criterion_sql).arrow()
                docs_filtered: int = total_docs - filter_table.num_rows
                bytes_filtered: int = total_bytes - filter_table.nbytes
                metadata[f"docs_filtered_out_by '{filter_criterion}'"] = docs_filtered
                metadata[f"bytes_filtered_out_by '{filter_criterion}'"] = bytes_filtered

            # use filtering criteria to build the SQL query for filtering
            filter_clauses: List[str] = [f"({x})" for x in self.filter_criteria]
            where_clause: str = f" {self.logical_operator} ".join(filter_clauses)
            sql_statement = f"{sql_statement} WHERE {where_clause}"

        if "WHERE" in sql_statement and con is not None:
            # filter using SQL statement
            duckdb_binding_errors: Tuple[type, ...] = (
                duckdb.BinderException,
                duckdb.ConversionException,
                duckdb.CatalogException,
            )

            try:
                filtered_table: pa.Table = con.execute(sql_statement).arrow()
            except duckdb_binding_errors as ex:
                err_msg: str = f"Filter condition is invalid due to mismatched data types. (e.g. comparing text to numbers). Please review the filter expression and table schema. {ex}"
                raise DatasiftException(
                    message=err_msg,
                    status_code=400,
                    error_code=ErrorCode.SQL_FILTER_ERROR,
                ) from ex
            except Exception as ex:
                err_msg: str = f"An unexpected error occurred. Please review your filter logic. {ex}"
                raise DatasiftException(
                    message=err_msg,
                    status_code=400,
                    error_code=ErrorCode.SQL_FILTER_ERROR,
                ) from ex
        else:
            filtered_table: pa.Table = table

        # drop any columns requested from the final result
        if len(self.columns_to_drop) > 0:
            if self.has_invalid_columns(
                metadata=metadata,
                input_table_columns_set=input_table_columns_set,
                mode=Mode.COLUMNS_TO_DROP,
            ):
                return [table]

            filtered_table_cols_dropped: pa.Table = filtered_table.drop_columns(
                self.columns_to_drop
            )
        else:
            filtered_table_cols_dropped: pa.Table = filtered_table

        # add global filter stats to metadata
        metadata["docs_after_filter"] = filtered_table.num_rows
        metadata["columns_after_filter"] = filtered_table_cols_dropped.num_columns
        metadata["bytes_after_filter"] = filtered_table.nbytes
        metadata[Metrics.External.PROCESSED_DOCS] = find_doc_count(
            table=filtered_table_cols_dropped
        )

        return [filtered_table_cols_dropped]

    def has_invalid_columns(
        self,
        input_table_columns_set: Set[str],
        mode: Mode,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Union[bool, List[str]]:
        filter_column_set: Set[str]
        if mode == Mode.COLUMNS_TO_DROP:
            filter_column_set = set(self.columns_to_drop)
        elif mode == Mode.FILTER_CRITERIA_JSON:
            filter_column_set = extract_columns(self.filter_criteria_json)
        else:
            filter_column_set = extract_columns(self.filter_criteria)

        invalid_columns: Set[str] = filter_column_set - input_table_columns_set

        if invalid_columns:
            logger.error(
                f"Invalid features found in {mode} - {', '.join(invalid_columns)}. {mode} should use only the available features."
            )
            if metadata is not None:
                metadata[Metrics.External.PROCESSED_DOCS] = 0
                metadata[Metrics.External.NODE_STATUS] = (
                    ExecutionStatus.COMPLETED_WITH_WARNINGS.value
                )
                return True
            else:
                return list(invalid_columns)
        return False

    def get_metadata(self) -> Dict[str, Any]:
        return {
            OperatorConstants.IS_OPERATOR_AVAILABLE: True,
            OperatorConstants.CATEGORY: self.category.value,
            OperatorConstants.LABEL: "Annotation Filter",
            OperatorConstants.ATTRIBUTES: {
                OperatorConstants.FILTER_CRITERIA_LIST: {
                    OperatorConstants.NAME: "Filter Criteria (List)",
                    OperatorConstants.DESCRIPTION: "Add different Filter criteria as part of the WHERE clause",
                    OperatorConstants.DEFAULT: FILTER_CRITERIA_DEFAULT,
                    OperatorConstants.REQUIRED: False,
                    OperatorConstants.TYPE: AttributeDataTypes.LIST,
                },
                OperatorConstants.FILTER_CRITERIA_JSON: {
                    OperatorConstants.NAME: "Filter Criteria (String/Json)",
                    OperatorConstants.DESCRIPTION: "Add different Filter criteria as part of the WHERE clause in JSON format",
                    OperatorConstants.DEFAULT: None,
                    OperatorConstants.REQUIRED: False,
                    OperatorConstants.TYPE: AttributeDataTypes.JSON,
                },
                OperatorConstants.FILTER_LOGICAL_OPERATOR_KEY: {
                    OperatorConstants.NAME: "Logical Operator",
                    OperatorConstants.DESCRIPTION: "Select the logical Operator for WHERE clause: OR or AND",
                    OperatorConstants.DEFAULT: FILTER_LOGICAL_OPERATOR_DEFAULT,
                    OperatorConstants.REQUIRED: False,
                    OperatorConstants.VALID_VALUES: VALID_FILTER_LOGICAL_OPERATORS,
                    OperatorConstants.TYPE: AttributeDataTypes.STRING,
                },
                OperatorConstants.FILTER_FEATURES_TO_DROP_KEY: {
                    OperatorConstants.NAME: "Features to drop",
                    OperatorConstants.DESCRIPTION: "Declare the features which need to be dropped",
                    OperatorConstants.DEFAULT: FILTER_FEATURES_TO_DROP_DEFAULT,
                    OperatorConstants.REQUIRED: False,
                    OperatorConstants.TYPE: AttributeDataTypes.LIST,
                },
            },
        }


_OPERATOR_MAP: Dict[str, str] = {
    "=": "=",
    "==": "=",
    "!=": "!=",
    "<>": "<>",
    ">": ">",
    "<": "<",
    ">=": ">=",
    "<=": "<=",
    "in": "IN",
    "not in": "NOT IN",
    "like": "LIKE",
    "not like": "NOT LIKE",
    "is null": IS_NULL,
    "is not null": IS_NOT_NULL,
    "between": "BETWEEN",
}


def convert_operator(op: str) -> str:
    """Convert JSON operator to SQL operator."""
    if not isinstance(op, str):
        raise DatasiftException(
            f"Operator must be a string, got {type(op).__name__}",
            error_code=ErrorCode.SQL_FILTER_ERROR,
        )
    try:
        return _OPERATOR_MAP[op.lower()]
    except KeyError:
        raise DatasiftException(
            f"Unknown operator: {op}", error_code=ErrorCode.SQL_FILTER_ERROR
        )


def format_value(value: Any) -> str:
    """Format value for SQL based on its type."""
    if value is None:
        return "NULL"
    elif isinstance(value, (int, float)):
        return str(value)
    elif isinstance(value, list):
        return f"({', '.join(format_value(v) for v in value)})"
    elif isinstance(value, str):
        try:
            # Try to parse as number
            return str(float(value)) if "." in value else str(int(value))
        except ValueError:
            escaped: str = value.replace("'", "''")
            return f"'{escaped}'"
    else:
        escaped: str = str(value).replace("'", "''")
        return f"'{escaped}'"


def process_condition(condition: Dict[str, Any]) -> str:
    """Process a single condition."""

    required_keys: List[str] = ["variable", "operator"]
    if not all(key in condition for key in required_keys):
        raise DatasiftException(
            message="Condition must contain 'variable' and 'operator'",
            status_code=400,
            error_code=ErrorCode.SQL_FILTER_ERROR,
        )

    variable: str = condition["variable"]
    operator: str = convert_operator(condition["operator"])
    value_raw: Any = condition.get("value")

    # Handle special cases
    if operator in [IS_NULL, IS_NOT_NULL]:
        return f"{variable} {operator}"

    if operator == "BETWEEN":
        if isinstance(value_raw, list) and len(value_raw) == 2:
            lower: str = format_value(value_raw[0])
            upper: str = format_value(value_raw[1])
            return f"{variable} {operator} {lower} AND {upper}"
        elif isinstance(value_raw, str):
            parts: List[str] = [v.strip() for v in value_raw.split(",")]
            if len(parts) != 2:
                raise DatasiftException(
                    message=f"BETWEEN operator requires 2 values, got: '{value_raw}'",
                    status_code=400,
                    error_code=ErrorCode.SQL_FILTER_ERROR,
                )
            lower: str = format_value(parts[0])
            upper: str = format_value(parts[1])
            return f"{variable} {operator} {lower} AND {upper}"
        else:
            raise DatasiftException(
                message=f"BETWEEN operator requires a list or comma-separated string of 2 values, got: {value_raw}",
                status_code=400,
                error_code=ErrorCode.SQL_FILTER_ERROR,
            )

    if operator in ["IN", "NOT IN"]:
        value_list: List[Any]
        if isinstance(value_raw, str):
            value_list = [v.strip() for v in value_raw.split(",")]
        elif isinstance(value_raw, list):
            value_list = value_raw
        else:
            raise DatasiftException(
                message=f"{operator} operator requires a list or comma-separated string, got: {value_raw}",
                status_code=400,
                error_code=ErrorCode.SQL_FILTER_ERROR,
            )
        formatted_value: str = format_value(value_list)
        return f"{variable} {operator} {formatted_value}"

    # All other operators
    formatted_value: str = format_value(value_raw)
    return f"{variable} {operator} {formatted_value}"


def process_criteria_group(group: Dict[str, Any]) -> str:
    """Process a group of criteria connected by a logical operator."""
    if not isinstance(group, dict):
        raise DatasiftException(
            message="Group must be a dictionary",
            status_code=400,
            error_code=ErrorCode.SQL_FILTER_ERROR,
        )

    # Check if it's a leaf condition
    if "criteria_list" not in group:
        return process_condition(group)

    logical_op: str = group.get("logical_operator", "AND").upper()
    criteria_list: List[Any] = group["criteria_list"]

    if not isinstance(criteria_list, list):
        raise DatasiftException(
            message="criteria_list must be a list",
            status_code=400,
            error_code=ErrorCode.SQL_FILTER_ERROR,
        )
    if not criteria_list:
        return ""

    processed_criteria: List[str] = []
    for criterion in criteria_list:
        if isinstance(criterion, dict) and "criteria_list" in criterion:
            # Nested group
            processed_group: str = process_criteria_group(criterion)
            if processed_group:
                processed_criteria.append(f"({processed_group})")
        else:
            # Leaf condition
            try:
                processed_condition: str = process_condition(criterion)
                if processed_condition:
                    processed_criteria.append(processed_condition)
            except ValueError as e:
                raise DatasiftException(
                    message=f"Skipping invalid condition: {criterion}. {e}",
                    status_code=400,
                    error_code=ErrorCode.SQL_FILTER_ERROR,
                )

    if not processed_criteria:
        return ""

    return f" {logical_op} ".join(processed_criteria)


def json_to_sql_where(where_json: Optional[Dict[str, Any]]) -> str:
    """Convert JSON representation to SQL WHERE clause."""
    if not where_json or not isinstance(where_json, dict):
        return ""

    try:
        where_clause: str = process_criteria_group(where_json)
    except (ValueError, TypeError) as e:
        raise DatasiftException(
            message=f"Error processing WHERE clause: {e}",
            status_code=400,
            error_code=ErrorCode.SQL_FILTER_ERROR,
        )

    if not where_clause.strip():
        return ""

    return f"WHERE {where_clause}"


def extract_columns(filter_input: Union[Dict[str, Any], List[str]]) -> Set[str]:
    """
    Extract column names from either JSON criteria (dict) or list of filter strings.

    Args:
        filter_input: Either a dict (JSON criteria) or a list of strings.

    Returns:
        A set of column names.
    """
    if isinstance(filter_input, dict):
        return extract_columns_json(filter_input)
    elif isinstance(filter_input, list) and all(
        isinstance(x, str) for x in filter_input
    ):
        return extract_columns_list(filter_input)
    else:
        raise DatasiftException(
            message=f"Unsupported filter_input type: {type(filter_input).__name__}",
            status_code=400,
        )


def extract_columns_json(condition_or_group: Dict[str, Any]) -> Set[str]:
    """Extract all column names from condition(s)."""
    columns: Set[str] = set()
    if "variable" in condition_or_group and "operator" in condition_or_group:
        columns.add(condition_or_group["variable"])
    elif "criteria_list" in condition_or_group:
        for criterion in condition_or_group["criteria_list"]:
            if isinstance(criterion, dict):
                columns.update(extract_columns_json(criterion))
    return columns


def extract_columns_list(filter_criteria: List[str]) -> Set[str]:
    """Extract column names from filter criteria strings."""

    # Pattern to split expressions on AND / OR
    logical_split_pattern: re.Pattern[str] = re.compile(
        r"\s+(AND|OR)\s+", flags=re.IGNORECASE
    )

    # Pattern to match a column name at the start of a condition
    column_pattern: re.Pattern[str] = re.compile(
        r"^\s*([\w.]+)\s*(?:IN|NOT IN|LIKE|IS NULL|IS NOT NULL|=|<>|!=|<=|>=|<|>)",
        flags=re.IGNORECASE,
    )

    columns: Set[str] = set()
    for criterion in filter_criteria:
        # Split complex condition into individual expressions
        expressions: List[str] = logical_split_pattern.split(criterion)
        for expr in expressions:
            if expr.upper() in {"AND", "OR"}:
                continue
            match: Optional[re.Match[str]] = column_pattern.match(expr.strip())
            if match:
                columns.add(match.group(1))

    return columns
