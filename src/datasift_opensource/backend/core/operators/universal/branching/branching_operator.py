import re
from typing import Any, List, Dict, Tuple, Optional, Set
import pyarrow as pa
import sqlglot
from sqlglot import expressions as exp

from core.operators.abstract_operator import AbstractOperator, OperatorCategory
from core.operators.universal.filter.sql_filter import (
    SQLFilterOperator,
    extract_columns,
)
from common.util.operator_utils import (
    validate_link_name,
    find_doc_count,
    validate_filter_criteria,
)
from common.util.log import get_logger
from common.util.constants import (
    OperatorConstants,
    Metrics,
    AttributeDataTypes,
    MemoryLogPhases,
)
from common.util.perf_utils import log_memory_usage

logger = get_logger()


class BranchingOperator(AbstractOperator):
    """
    BranchingOperator class for branching data based on specified conditions.
    This class inherits from AbstractOperator and provides functionality to branch data
    based on given conditions and logical operators.
    """

    short_name: str = OperatorConstants.BRANCHING
    category: OperatorCategory = OperatorCategory.Functional

    def __init__(self, config: Dict[str, Any]) -> None:
        super().__init__(config)
        self._config: Dict[str, Any] = config
        self.branch_criteria: List[Dict[str, Any]] = config.get("branches", [])

    def validate(
        self, errors: List[str], warnings: List[str], available_features: List[str]
    ) -> None:
        if not self.should_validate_field(field_value=self.branch_criteria):
            return

        if not self.branch_criteria:
            errors.append("branch_criteria parameter is missing")
            return

        if len(self.branch_criteria) == 1:
            warnings.append(
                "Branching Operator has only one branch. Consider using a Filter Operator instead."
            )

        # Check if this is unconditional branching (all branches have empty criteria_json['criteria_list'])
        is_unconditional_branching: bool = all(
            isinstance(branch.get(OperatorConstants.FILTER_CRITERIA_JSON), dict)
            and not branch.get(OperatorConstants.FILTER_CRITERIA_JSON, {}).get(
                "criteria_list", []
            )
            for branch in self.branch_criteria
        )

        invalid_features: Set[str] = set()
        existing_link_names: Set[str] = set()
        for branch in self.branch_criteria:
            logical_op: Optional[str] = branch.get("logical_operator")
            criteria_list: List[str] = branch.get(
                OperatorConstants.FILTER_CRITERIA_LIST, []
            )
            criteria_json: Optional[Dict[str, Any]] = branch.get(
                OperatorConstants.FILTER_CRITERIA_JSON
            )
            link_name: Optional[str] = branch.get(OperatorConstants.LINK_NAME)
            validate_link_name(
                link_name=link_name,
                existing_link_names=existing_link_names,
                errors=errors,
            )

            if logical_op and logical_op not in ["AND", "OR"]:
                errors.append(
                    f"Invalid logical operator '{logical_op}' in branch. Use 'AND' or 'OR'."
                )

            # Skip criteria validation for unconditional branching
            if is_unconditional_branching:
                continue

            # Validate that branch has at least one valid condition for conditional branching
            should_validate_criteria: bool = self.should_validate_field(
                field_value=criteria_list
            )
            should_validate_json: bool = self.should_validate_field(
                field_value=criteria_json
            )

            # Only validate if both fields are not parameterized
            if should_validate_criteria and should_validate_json:
                criteria_valid: bool
                json_valid: bool
                criteria_valid, json_valid = validate_filter_criteria(
                    criteria_list=criteria_list, criteria_json=criteria_json
                )

                # Warning if both are invalid/empty in conditional branching
                if not (criteria_valid or json_valid):
                    warnings.append(
                        f"Filter criteria must have at least one condition for conditional branch '{link_name or 'unnamed'}'"
                    )

            # validate criteria JSON
            if criteria_json:
                criteria_columns: Set[str] = extract_columns(criteria_json)
                invalid_columns: Set[str] = criteria_columns - set(available_features)
                invalid_features.update(invalid_columns)
            # validate criteria list
            elif criteria_list:
                for criteria in criteria_list:
                    if (
                        criteria and criteria.strip()
                    ):  # Only validate non-empty criteria
                        self.validate_expression(
                            expr=criteria,
                            available_features=available_features,
                            errors=errors,
                        )

            if not branch.get(OperatorConstants.LINK_ID):
                errors.append("Branch Id is missing in the branch parameters.")

        if invalid_features:
            errors.append(
                f"Invalid features in filter criteria - {', '.join(invalid_features)}. Filter criteria should use only the available features: {', '.join(available_features)}."
            )

    def get_metadata(self) -> Dict[str, Any]:
        return {
            OperatorConstants.SDK: True,
            OperatorConstants.CATEGORY: self.category.value,
            OperatorConstants.IS_OPERATOR_AVAILABLE: self.is_available(),
            OperatorConstants.LABEL: "Branching Operator",
            OperatorConstants.ATTRIBUTES: {
                "branch_criteria": {
                    OperatorConstants.NAME: "Branches",
                    OperatorConstants.DESCRIPTION: (
                        "A list of branch configurations. Each branch includes a set of filter conditions, "
                        "a logical operator (AND/OR) to combine them, and features to drop from the resulting table."
                    ),
                    OperatorConstants.REQUIRED: True,
                    OperatorConstants.TYPE: AttributeDataTypes.LIST,
                }
            },
        }

    def _update_metadata(
        self,
        idx: int,
        filtered_table: pa.Table,
        metadata: Dict[str, Any],
        total_docs: int,
        skipped_docs: List[Dict[str, Any]],
        failed_docs: List[Dict[str, Any]],
    ) -> None:
        branch_id: Optional[str] = self.branch_criteria[idx].get(
            OperatorConstants.LINK_ID
        )
        metadata["branches"][branch_id] = {
            "result_index": idx,
            "docs_filtered": total_docs - filtered_table.num_rows,
            "remaining_docs": filtered_table.num_rows,
            "processed_docs": filtered_table.num_rows,
            "skipped_docs_count": len(skipped_docs),
            "failed_docs_count": len(failed_docs),
        }
        metadata[Metrics.External.SKIPPED_DOCS] = skipped_docs
        metadata[Metrics.External.FAILED_DOCS] = failed_docs

    def runner(
        self, table: pa.Table, spark_session: Optional[Any] = None
    ) -> Tuple[List[pa.Table], Dict[str, Any]]:
        log_memory_usage(
            operator_name=self.name,
            phase=MemoryLogPhases.TRANSFORM_COMPLETED,
            table=table,
            extra=self.common_log_arguments,
            logger=logger,
        )
        total_docs: int = table.num_rows

        metadata: Dict[str, Any] = self.create_base_metadata(
            total_docs_count=find_doc_count(table=table)
        )
        metadata["branches"] = {}

        filtered_tables: List[pa.Table] = []
        skipped_docs: List[Dict[str, Any]] = []
        failed_docs: List[Dict[str, Any]] = []
        processed_doc_ids: Set[str] = set()

        for idx, branch in enumerate(self.branch_criteria):
            if not branch.get(
                OperatorConstants.FILTER_CRITERIA_LIST
            ) and not branch.get(OperatorConstants.FILTER_CRITERIA_JSON):
                filtered_tables.append(pa.Table.from_batches(table.to_batches()))
                # Track unique document IDs for unconditional branching
                if OperatorConstants.ID in table.column_names:
                    doc_ids: List[str] = table.column(OperatorConstants.ID).to_pylist()
                    processed_doc_ids.update(doc_ids)
                self._update_metadata(
                    idx=idx,
                    filtered_table=table,
                    metadata=metadata,
                    total_docs=total_docs,
                    skipped_docs=skipped_docs,
                    failed_docs=failed_docs,
                )
                continue

            config: Dict[str, Any] = {
                OperatorConstants.FILTER_CRITERIA_LIST: branch.get(
                    OperatorConstants.FILTER_CRITERIA_LIST
                ),
                OperatorConstants.FILTER_LOGICAL_OPERATOR_KEY: branch.get(
                    OperatorConstants.FILTER_LOGICAL_OPERATOR_KEY
                ),
                OperatorConstants.FILTER_CRITERIA_JSON: branch.get(
                    OperatorConstants.FILTER_CRITERIA_JSON
                ),
            }
            filter_operator: Any
            if spark_session:
                from core.operators.universal.filter.sql_filter import (
                    SparkSQLFilterOperator,
                )

                config |= self._config
                filter_operator = SparkSQLFilterOperator(
                    config=config, spark_session=spark_session
                )
            else:
                filter_operator = SQLFilterOperator(config=config)

            branch_tables: List[pa.Table]
            metadata_filter_transform: Optional[Dict[str, Any]]
            branch_tables, metadata_filter_transform = filter_operator.transform(table)
            filtered_table: pa.Table = branch_tables[0]

            # Track unique document IDs for conditional branching
            if OperatorConstants.ID in filtered_table.column_names:
                doc_ids = filtered_table.column(OperatorConstants.ID).to_pylist()
                processed_doc_ids.update(doc_ids)

            if metadata_filter_transform is not None:
                skipped_docs = self.get_skipped_doc(
                    skipped_docs, metadata_filter_transform, idx=idx
                )
                failed_docs = self.get_failed_doc(
                    failed_docs, metadata_filter_transform, idx=idx
                )

            self._update_metadata(
                idx=idx,
                filtered_table=filtered_table,
                metadata=metadata,
                total_docs=total_docs,
                skipped_docs=skipped_docs,
                failed_docs=failed_docs,
            )
            filtered_tables.append(filtered_table)

        # Update overall metadata counts
        metadata[Metrics.External.PROCESSED_DOCS] = len(processed_doc_ids)
        metadata[Metrics.External.SKIPPED_DOCS_COUNT] = len(skipped_docs)
        metadata[Metrics.External.FAILED_DOCS_COUNT] = len(failed_docs)

        log_memory_usage(
            operator_name=self.name,
            phase=MemoryLogPhases.TRANSFORM_COMPLETED,
            table=filtered_tables,
            extra=self.common_log_arguments,
            logger=logger,
        )
        return filtered_tables, metadata

    @staticmethod
    def get_skipped_doc(
        skipped_docs: List[Dict[str, Any]],
        metadata_filter_transform: Dict[str, Any],
        idx: int,
    ) -> List[Dict[str, Any]]:
        metadata_skipped: List[Dict[str, Any]] = metadata_filter_transform.get(
            Metrics.External.SKIPPED_DOCS, []
        )

        if not skipped_docs:
            return metadata_skipped if (metadata_skipped and idx == 0) else []

        if not metadata_skipped:
            return []

        metadata_ids: Set[str] = {doc["id"] for doc in metadata_skipped}
        return [doc for doc in skipped_docs if doc["id"] in metadata_ids]

    @staticmethod
    def get_failed_doc(
        failed_docs: List[Dict[str, Any]],
        metadata_filter_transform: Dict[str, Any],
        idx: int,
    ) -> List[Dict[str, Any]]:
        metadata_failed: List[Dict[str, Any]] = metadata_filter_transform.get(
            Metrics.External.FAILED_DOCS, []
        )

        if not failed_docs:
            return metadata_failed if (metadata_failed and idx == 0) else []

        if not metadata_failed:
            return []

        metadata_ids: Set[str] = {doc["id"] for doc in metadata_failed}
        return [doc for doc in failed_docs if doc["id"] in metadata_ids]

    def transform(
        self, table: pa.Table, file_name: Optional[str] = None
    ) -> Tuple[List[pa.Table], Dict[str, Any]]:
        return self.runner(table=table)

    def validate_expression(
        self, *, expr: str, available_features: List[str], errors: List[str]
    ) -> None:

        try:
            is_valid: bool
            columns: List[str]
            is_valid, columns = self.analyze_where_clause(clause_str=expr)
            invalid_columns: Set[str] = set(columns) - set(available_features)
            if not is_valid or len(invalid_columns) > 0:
                if invalid_columns:
                    errors.append(
                        f"Invalid branching criteria expression: {expr}, invalid features found: {invalid_columns}, Please use valid features in criteria expression"
                    )
                else:
                    errors.append(
                        f"Invalid branching criteria expression: {expr}, Please use valid criteria expression"
                    )
        except Exception as exc:
            errors.append(
                f"Unexpected error while validating branching criteria: {expr}, Error: {str(exc)}"
            )

    def analyze_where_clause(self, *, clause_str: str) -> Tuple[bool, List[str]]:
        clause_str = clause_str.strip()
        if not clause_str:
            return False, []
        if ";" in clause_str:
            return False, []

        if re.search(r"\w%\w", clause_str):
            return False, []

        sql: str = f"SELECT * FROM dummy_table WHERE {clause_str}"
        try:
            parsed: Any = sqlglot.parse_one(sql)
            where: Optional[Any] = parsed.find(exp.Where)
            if not where:
                return False, []
            columns: List[str] = []

            for col in where.find_all(exp.Column):
                # col.name strips table qualifiers automatically
                columns.append(col.name)
            # Remove duplicates while preserving order
            unique_cols: List[str] = []
            for c in columns:
                if c not in unique_cols and self._is_valid_column_name(c):
                    unique_cols.append(c)
            return True, unique_cols
        except Exception as e:
            logger.error(f"Error while parsing sql statement: {str(e)}")
            return False, []

    def _is_valid_column_name(self, column_name: str) -> bool:
        """
        **STRICT VALIDATION**: Validate column name format

        Args:
            column_name (str): Column name to validate

        Returns:
            bool: True if valid column name format
        """
        import re

        if not column_name or len(column_name) > 128:  # Max column name length
            return False

        # Allow alphanumeric, underscore, and dot for table.column format
        # Must start with letter or underscore
        pattern: str = r"^\w+(\.\w+)?$"

        return bool(re.match(pattern, column_name))
