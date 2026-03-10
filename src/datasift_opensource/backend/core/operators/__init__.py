"""Core operators package."""
from typing import Any, Dict, List, Set, Tuple

import pyarrow as pa
import pyarrow.compute as pc

from common.util.constants import OperatorConstants, Metrics, ExecutionStatus
from common.util.log import get_logger

logger = get_logger()


def extract_columns(criteria_json: dict) -> Set[str]:
    """
    Recursively extract column names referenced in a criteria_json structure.

    criteria_json can be:
      - A leaf condition: {'variable': 'col', 'operator': '=', 'value': 'x'}
      - A group:          {'logical_operator': 'AND'|'OR', 'criteria_list': [...]}

    Returns a set of column name strings.
    """
    if not criteria_json or not isinstance(criteria_json, dict):
        return set()

    columns: Set[str] = set()

    # Leaf condition
    if "variable" in criteria_json:
        columns.add(criteria_json["variable"])
        return columns

    # Group condition
    for item in criteria_json.get("criteria_list", []):
        columns |= extract_columns(item)

    return columns


def _build_sql_filter_mask(table: pa.Table, criteria_list: list, logical_op: str) -> pa.Array:
    """
    Build a boolean mask for filtering a PyArrow table using criteria_list strings.
    Each criterion is a SQL-like WHERE clause fragment (e.g. "score > 0.5").
    """
    import sqlglot
    from sqlglot import expressions as exp

    masks = []
    for criterion in criteria_list:
        if not criterion or not criterion.strip():
            continue
        try:
            sql = f"SELECT * FROM t WHERE {criterion}"
            parsed = sqlglot.parse_one(sql)
            where = parsed.find(exp.Where)
            if where is None:
                continue
            mask = _eval_expression(where.this, table)
            if mask is not None:
                masks.append(mask)
        except Exception as e:
            logger.warning(f"SQLFilterOperator: failed to parse criterion '{criterion}': {e}")

    if not masks:
        # No valid criteria → keep all rows
        return pa.array([True] * table.num_rows, type=pa.bool_())

    result = masks[0]
    for m in masks[1:]:
        if logical_op and logical_op.upper() == "OR":
            result = pc.or_(result, m)
        else:
            result = pc.and_(result, m)
    return result


def _build_json_filter_mask(table: pa.Table, criteria_json: dict) -> pa.Array:
    """
    Build a boolean mask from a criteria_json structure.
    """
    if not criteria_json or not isinstance(criteria_json, dict):
        return pa.array([True] * table.num_rows, type=pa.bool_())

    # Leaf condition
    if "variable" in criteria_json and "operator" in criteria_json:
        col_name = criteria_json["variable"]
        operator = criteria_json["operator"]
        value = criteria_json.get("value")

        if col_name not in table.column_names:
            return pa.array([False] * table.num_rows, type=pa.bool_())

        col = table.column(col_name)
        try:
            scalar = pa.scalar(value, type=col.type) if value is not None else None
        except Exception:
            scalar = pa.scalar(str(value))

        op_map = {
            "=": pc.equal, "==": pc.equal,
            "!=": pc.not_equal, "<>": pc.not_equal,
            ">": pc.greater, ">=": pc.greater_equal,
            "<": pc.less, "<=": pc.less_equal,
        }
        op_fn = op_map.get(operator)
        if op_fn and scalar is not None:
            return op_fn(col, scalar)
        return pa.array([True] * table.num_rows, type=pa.bool_())

    # Group condition
    logical_op = criteria_json.get("logical_operator", "AND").upper()
    masks = [
        _build_json_filter_mask(table, item)
        for item in criteria_json.get("criteria_list", [])
    ]

    if not masks:
        return pa.array([True] * table.num_rows, type=pa.bool_())

    result = masks[0]
    for m in masks[1:]:
        if logical_op == "OR":
            result = pc.or_(result, m)
        else:
            result = pc.and_(result, m)
    return result


def _eval_expression(expr, table: pa.Table) -> pa.Array | None:
    """Evaluate a sqlglot expression node against a PyArrow table."""
    import sqlglot.expressions as exp

    if isinstance(expr, exp.And):
        left = _eval_expression(expr.left, table)
        right = _eval_expression(expr.right, table)
        if left is not None and right is not None:
            return pc.and_(left, right)
    elif isinstance(expr, exp.Or):
        left = _eval_expression(expr.left, table)
        right = _eval_expression(expr.right, table)
        if left is not None and right is not None:
            return pc.or_(left, right)
    elif isinstance(expr, (exp.EQ, exp.NEQ, exp.GT, exp.GTE, exp.LT, exp.LTE)):
        col_node = expr.left
        val_node = expr.right
        col_name = col_node.name if hasattr(col_node, "name") else str(col_node)
        if col_name not in table.column_names:
            return pa.array([False] * table.num_rows, type=pa.bool_())
        col = table.column(col_name)
        raw_val = val_node.this if hasattr(val_node, "this") else str(val_node)
        # Try to cast value to column type
        try:
            scalar = pa.scalar(raw_val, type=col.type)
        except Exception:
            try:
                scalar = pa.scalar(float(raw_val))
            except Exception:
                scalar = pa.scalar(str(raw_val))
        op_map = {
            exp.EQ: pc.equal, exp.NEQ: pc.not_equal,
            exp.GT: pc.greater, exp.GTE: pc.greater_equal,
            exp.LT: pc.less, exp.LTE: pc.less_equal,
        }
        op_fn = op_map.get(type(expr))
        if op_fn:
            return op_fn(col, scalar)
    return None


class SQLFilterOperator:
    """
    Filters a PyArrow table using SQL-like criteria.

    Supports:
      - criteria_list: list of SQL WHERE clause fragments (e.g. ["score > 0.5"])
      - criteria_json: nested criteria dict with 'variable'/'operator'/'value' leaves
      - logical_operator: 'AND' (default) or 'OR' for combining criteria_list items
    """

    def __init__(self, config: dict):
        self._config = config
        self._criteria_list: List[str] = config.get(OperatorConstants.FILTER_CRITERIA_LIST) or []
        self._logical_op: str = config.get(OperatorConstants.FILTER_LOGICAL_OPERATOR_KEY, "AND") or "AND"
        self._criteria_json: dict = config.get(OperatorConstants.FILTER_CRITERIA_JSON) or {}

    def transform(self, table: pa.Table) -> Tuple[List[pa.Table], Dict[str, Any]]:
        """
        Filter the table and return ([filtered_table], metadata).
        """
        total_docs = table.num_rows
        metadata = {
            Metrics.External.TOTAL_DOCS: total_docs,
            Metrics.External.PROCESSED_DOCS: 0,
            Metrics.External.FAILED_DOCS_COUNT: 0,
            Metrics.External.FAILED_DOCS: [],
            Metrics.External.SKIPPED_DOCS_COUNT: 0,
            Metrics.External.SKIPPED_DOCS: [],
            Metrics.External.NODE_STATUS: ExecutionStatus.COMPLETED.value,
        }

        try:
            if self._criteria_json:
                mask = _build_json_filter_mask(table, self._criteria_json)
            elif self._criteria_list:
                mask = _build_sql_filter_mask(table, self._criteria_list, self._logical_op)
            else:
                # No criteria → pass all rows through
                mask = pa.array([True] * table.num_rows, type=pa.bool_())

            filtered_table = table.filter(mask)
            metadata[Metrics.External.PROCESSED_DOCS] = filtered_table.num_rows

        except Exception as e:
            logger.error(f"SQLFilterOperator.transform failed: {e}")
            filtered_table = table  # fallback: return original table
            metadata[Metrics.External.FAILED_DOCS_COUNT] = total_docs

        return [filtered_table], metadata

# Made with Bob
