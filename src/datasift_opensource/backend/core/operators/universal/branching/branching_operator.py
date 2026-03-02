import re
from typing import Any, List, Dict, Tuple
import pyarrow as pa
import sqlglot
from sqlglot import expressions as exp

from core.operators.abstract_operator import AbstractOperator, OperatorCategory
from core.operators.universal.filter.sql_filter import SQLFilterOperator, extract_columns
from common.util.operator_utils import validate_link_name, find_doc_count, validate_filter_criteria
from common.util.log import get_logger
from common.util.constants import OperatorConstants, Metrics, AttributeDataTypes, MemoryLogPhases
from common.util.perf_utils import log_memory_usage

logger = get_logger()


class BranchingOperator(AbstractOperator):
    """
    BranchingOperator class for branching data based on specified conditions.
    This class inherits from AbstractOperator and provides functionality to branch data
    based on given conditions and logical operators.
    """

    short_name = OperatorConstants.BRANCHING
    category = OperatorCategory.Functional

    def __init__(self, config: dict):
        super().__init__(config)
        self._config = config
        self.branch_criteria = config.get('branches', [])

    def validate(self, errors: list, warnings: list, available_features: list):
        if not self.should_validate_field(field_value=self.branch_criteria):
            return

        if not self.branch_criteria:
            errors.append("branch_criteria parameter is missing")
            return
        
        if len(self.branch_criteria) == 1:
            warnings.append("Branching Operator has only one branch. Consider using a Filter Operator instead.")

        # Check if this is unconditional branching (all branches have empty criteria_json['criteria_list'])
        is_unconditional_branching = all(
            isinstance(branch.get(OperatorConstants.FILTER_CRITERIA_JSON), dict) and
            not branch.get(OperatorConstants.FILTER_CRITERIA_JSON, {}).get('criteria_list', [])
            for branch in self.branch_criteria
        )

        invalid_features=set()
        existing_link_names = set()
        for branch in self.branch_criteria:
            logical_op = branch.get('logical_operator')
            criteria_list = branch.get(OperatorConstants.FILTER_CRITERIA_LIST, [])
            criteria_json = branch.get(OperatorConstants.FILTER_CRITERIA_JSON)
            link_name = branch.get(OperatorConstants.LINK_NAME)
            validate_link_name(link_name=link_name, existing_link_names=existing_link_names, errors=errors)

            if logical_op and logical_op not in ['AND', 'OR']:
                errors.append(f"Invalid logical operator '{logical_op}' in branch. Use 'AND' or 'OR'.")

            # Skip criteria validation for unconditional branching
            if is_unconditional_branching:
                continue

            # Validate that branch has at least one valid condition for conditional branching
            should_validate_criteria = self.should_validate_field(field_value=criteria_list)
            should_validate_json = self.should_validate_field(field_value=criteria_json)

            # Only validate if both fields are not parameterized
            if should_validate_criteria and should_validate_json:
                criteria_valid, json_valid = validate_filter_criteria(criteria_list=criteria_list,
                                                                      criteria_json=criteria_json)

                # Warning if both are invalid/empty in conditional branching
                if not (criteria_valid or json_valid):
                    warnings.append(f"Filter criteria must have at least one condition for conditional branch '{link_name or 'unnamed'}'")

            #validate criteria JSON
            if criteria_json:
                criteria_columns = extract_columns(criteria_json)
                invalid_columns = criteria_columns - set(available_features)
                invalid_features.update(invalid_columns)
            #validate criteria list
            elif criteria_list:
                for criteria in criteria_list:
                    if criteria and criteria.strip():  # Only validate non-empty criteria
                        self.validate_expression(expr=criteria, available_features=available_features, errors=errors)

            if not branch.get(OperatorConstants.LINK_ID):
                errors.append("Branch Id is missing in the branch parameters.")
        
        if invalid_features:
            errors.append(f"Invalid features in filter criteria - {', '.join(invalid_columns)}. Filter criteria should use only the available features: {', '.join(available_features)}.")

    def get_metadata(self):
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
                    OperatorConstants.TYPE: AttributeDataTypes.LIST
                }
            },
        }

    def _update_metadata(self, idx, filtered_table, metadata, total_docs, skipped_docs, failed_docs):
        branch_id = self.branch_criteria[idx].get(OperatorConstants.LINK_ID)
        metadata['branches'][branch_id] = {
            "result_index": idx,
            'docs_filtered': total_docs - filtered_table.num_rows,
            'remaining_docs': filtered_table.num_rows,
            'processed_docs': filtered_table.num_rows,
            'skipped_docs_count': len(skipped_docs),
            'failed_docs_count': len(failed_docs),
        }
        metadata[Metrics.External.SKIPPED_DOCS] = skipped_docs
        metadata[Metrics.External.FAILED_DOCS] = failed_docs

    def runner(self, table: pa.Table, spark_session = None) -> Tuple[List[pa.Table], Dict]:
        log_memory_usage(operator_name=self.name, phase=MemoryLogPhases.TRANSFORM_COMPLETED, table=table,
                         extra=self.common_log_arguments,
                         logger=logger)
        total_docs = table.num_rows

        metadata = self.create_base_metadata(total_docs_count=find_doc_count(table=table))
        metadata["branches"] = {}

        filtered_tables = []
        skipped_docs = []
        failed_docs = []
        processed_doc_ids = set()
        
        for idx, branch in enumerate(self.branch_criteria):
            if not branch.get(OperatorConstants.FILTER_CRITERIA_LIST) and not branch.get(OperatorConstants.FILTER_CRITERIA_JSON):
                filtered_tables.append(pa.Table.from_batches(table.to_batches()))
                # Track unique document IDs for unconditional branching
                if OperatorConstants.ID in table.column_names:
                    doc_ids = table.column(OperatorConstants.ID).to_pylist()
                    processed_doc_ids.update(doc_ids)
                self._update_metadata(idx=idx, filtered_table=table, metadata=metadata, total_docs=total_docs,
                                    skipped_docs=skipped_docs, failed_docs=failed_docs)
                continue

            config = {
                OperatorConstants.FILTER_CRITERIA_LIST: branch.get(
                    OperatorConstants.FILTER_CRITERIA_LIST
                ),
                OperatorConstants.FILTER_LOGICAL_OPERATOR_KEY: branch.get(
                    OperatorConstants.FILTER_LOGICAL_OPERATOR_KEY
                ),
                OperatorConstants.FILTER_CRITERIA_JSON:branch.get(
                    OperatorConstants.FILTER_CRITERIA_JSON
                    )
            }
            if spark_session:
                from core.operators.universal.filter.sql_filter import SparkSQLFilterOperator
                config |= self._config
                filter_operator = SparkSQLFilterOperator(config=config, spark_session=spark_session)
            else:
                filter_operator = SQLFilterOperator(config=config)

            branch_tables, metadata_filter_transform = filter_operator.transform(table)
            filtered_table = branch_tables[0]
            
            # Track unique document IDs for conditional branching
            if OperatorConstants.ID in filtered_table.column_names:
                doc_ids = filtered_table.column(OperatorConstants.ID).to_pylist()
                processed_doc_ids.update(doc_ids)
            
            if metadata_filter_transform is not None:
                skipped_docs = self.get_skipped_doc(skipped_docs, metadata_filter_transform, idx=idx)
                failed_docs = self.get_failed_doc(failed_docs, metadata_filter_transform, idx=idx)
                
            self._update_metadata(idx=idx, filtered_table=filtered_table, metadata=metadata, total_docs=total_docs,
                                skipped_docs=skipped_docs, failed_docs=failed_docs)
            filtered_tables.append(filtered_table)

        # Update overall metadata counts
        metadata[Metrics.External.PROCESSED_DOCS] = len(processed_doc_ids)
        metadata[Metrics.External.SKIPPED_DOCS_COUNT] = len(skipped_docs)
        metadata[Metrics.External.FAILED_DOCS_COUNT] = len(failed_docs)
        
        log_memory_usage(operator_name=self.name, phase=MemoryLogPhases.TRANSFORM_COMPLETED, table=filtered_tables,
                         extra=self.common_log_arguments,
                         logger=logger)
        return filtered_tables, metadata

    @staticmethod
    def get_skipped_doc(skipped_docs: list, metadata_filter_transform: Dict[str, Any], idx) -> List[Any]:
        metadata_skipped = metadata_filter_transform.get(Metrics.External.SKIPPED_DOCS, [])

        if not skipped_docs:
            return metadata_skipped if (metadata_skipped and idx == 0) else []

        if not metadata_skipped:
            return []

        metadata_ids = {doc["id"] for doc in metadata_skipped}
        return [doc for doc in skipped_docs if doc["id"] in metadata_ids]

    @staticmethod
    def get_failed_doc(failed_docs: list, metadata_filter_transform: Dict[str, Any], idx) -> List[Any]:
        metadata_failed = metadata_filter_transform.get(Metrics.External.FAILED_DOCS, [])

        if not failed_docs:
            return metadata_failed if (metadata_failed and idx == 0) else []

        if not metadata_failed:
            return []

        metadata_ids = {doc["id"] for doc in metadata_failed}
        return [doc for doc in failed_docs if doc["id"] in metadata_ids]

    def transform(self, table: pa.Table, file_name: str = None) -> Tuple[List[pa.Table], Dict]:
        return self.runner(table=table)

    def validate_expression(self, *, expr, available_features, errors):

        try:
            is_valid, columns = self.analyze_where_clause(clause_str=expr)
            invalid_columns = set(columns) - set(available_features)
            if not is_valid or len(invalid_columns) > 0:
                if invalid_columns:
                    errors.append( f"Invalid branching criteria expression: {expr}, invalid features found: {invalid_columns}, Please use valid features in criteria expression")
                else:
                    errors.append(
                        f"Invalid branching criteria expression: {expr}, Please use valid criteria expression")
        except Exception as exc:
            errors.append(f"Unexpected error while validating branching criteria: {expr}, Error: {str(exc)}")

    def analyze_where_clause(self, *, clause_str: str):
        clause_str = clause_str.strip()
        if not clause_str:
            return False, []
        if ';' in clause_str:
            return False, []

        if re.search(r"\w%\w", clause_str):
            return False, []

        sql = f"SELECT * FROM dummy_table WHERE {clause_str}"
        try:
            parsed = sqlglot.parse_one(sql)
            where = parsed.find(exp.Where)
            if not where:
                return False, []
            columns = []

            for col in where.find_all(exp.Column):
                # col.name strips table qualifiers automatically
                columns.append(col.name)
            # Remove duplicates while preserving order
            unique_cols = []
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
        pattern = r'^\w+(\.\w+)?$'

        return bool(re.match(pattern, column_name))
