import datetime
import json
import os
from typing import Any

import pyarrow as pa

from common.exceptions.datasift_exceptions import FlowExecutionFailedException
from common.exceptions.error_messages import ValidationCodeMessages, ValidationMessage
from common.util.constants import (
    DatasiftConstants,
    DocsStructure,
    ExecutionStatus,
    Metrics,
    OperatorConstants,
)
from common.util.job_tracker.model.models import normalize_node_stats_for_dto
from common.util.job_tracker.tracker.job_tracker import NodeStatsDto
from common.util.log import get_logger

status_codes = {
    ExecutionStatus.FAILED: 1,
    ExecutionStatus.COMPLETED_WITH_ERRORS: 2,
    ExecutionStatus.COMPLETED_WITH_WARNINGS: 3,
    ExecutionStatus.CANCELED: 4,
    ExecutionStatus.CANCELING: 5,
    ExecutionStatus.PAUSED: 6,
    ExecutionStatus.RESUMING: 7,
    ExecutionStatus.RUNNING: 8,
    ExecutionStatus.STARTING: 9,
    ExecutionStatus.QUEUED: 10,
    ExecutionStatus.COMPLETED: 1000,
}


class OperatorUtils:
    logger = get_logger()

    @staticmethod
    def validate_columns(
        table: pa.Table | list,
        required: list[str],
        operator_name: str,
        error_messages: list = None,
    ) -> None:
        """
        Check if required columns exist in the provided available features or table.

        :param required: List of required columns
        :param operator_name: Name of the operator for error reporting
        :param error_messages: (optional) List of error messages
        :return: None
        """
        if isinstance(table, pa.Table):
            table = table.schema.names

        missing_features = []
        missing_operators = []

        result = True
        for r in required:
            if r not in table:
                missing_features.append(r)
        if len(missing_features) > 0:
            result = False
        if not result:
            missing_operators.extend(get_missing_operator(missing_features))

            if isinstance(table, list):
                message = ValidationMessage.create(
                    message=ValidationCodeMessages.MISSING_FEATURES.value.format(
                        operator_name=operator_name,
                        missing_features=missing_features,
                        missing_operators=missing_operators,
                    ),
                    message_code=ValidationCodeMessages.MISSING_FEATURES.name,
                    missing_features=missing_features,
                    missing_operators=missing_operators,
                )
            else:
                message = ValidationMessage.create(
                    message=ValidationCodeMessages.MISSING_COLUMNS.value.format(
                        operator_name=operator_name, missing_features=missing_features
                    ),
                    message_code=ValidationCodeMessages.MISSING_COLUMNS.name,
                    missing_features=missing_features,
                    missing_operators=missing_operators,
                )
            if error_messages is not None:
                error_messages.append(message)
            else:
                raise FlowExecutionFailedException(message)

    @staticmethod
    def merge_status(old_stat: ExecutionStatus, new_stat: ExecutionStatus) -> ExecutionStatus:
        """
        Merge two JobStatus values by returning the one with the lower numeric code (i.e., higher severity).
        If the old status is more severe, it is returned; otherwise, the new status is returned.
        """

        if status_codes[old_stat] < status_codes[new_stat]:
            return old_stat
        else:
            return new_stat

    @staticmethod
    def store_node_metadata(operator: dict, node_metadata: dict):  # pragma: no cover
        """
        Function which add operators metadata to a json file.
        Parameters -
            operator: dict - {'operator': 'chunker', 'id': 1234}, etc.,
            node_metadata: dict - {'num_rows': 10} etc.,
            store_config: dict - {'cp4d_base_url': 'https://cpd.com', ...}
        Returns -
            None. Node Metadata is added to file.
        """

        from common.models.session_info import get_session_info

        session_info = get_session_info()
        job_id = session_info.job_id
        job_run_id = session_info.job_run_id

        common_log_arguments = {
            DatasiftConstants.JOB_ID: job_id,
            DatasiftConstants.JOB_RUN_ID: job_run_id,
        }

        logger = get_logger()

        metadata_file_path = f"{job_id}/{job_run_id}/{OperatorConstants.NODES_METADATA_FILE}"

        op_node_metadata = {
            OperatorConstants.ID: operator[OperatorConstants.ID],
            OperatorConstants.OPERATOR: operator[OperatorConstants.NAME],
            OperatorConstants.NODE_METADATA: node_metadata,
        }

        try:
            from common.util.job_tracker.tracker.job_tracker import JobTracker

            node_stats = {OperatorConstants.NODE_METADATA: op_node_metadata}
            JobTracker().update_node_stats(
                job_run_id=job_run_id,
                node_id=operator[OperatorConstants.ID],
                node_stats=node_stats,
            )

        except Exception as e:
            logger.error(
                f"An error occurred while storing {operator[OperatorConstants.NAME]} metadata to {metadata_file_path} file: {e!s}",
                exc_info=True,
                stack_info=True,
                extra=common_log_arguments,
            )

    @staticmethod
    def get_feature(
        name,
        description,
        type,
        available_for_filter=False,
        available_for_vector_db=False,
        mandatory_for_vector_db=False,
    ):
        return {
            OperatorConstants.NAME: name,
            OperatorConstants.DESCRIPTION: description,
            OperatorConstants.TYPE: type,
            OperatorConstants.AVAILABLE_FOR_FILTER: available_for_filter,
            OperatorConstants.AVAILABLE_FOR_VECTOR_DB: available_for_vector_db,
            OperatorConstants.MANDATORY_FOR_VECTOR_DB: mandatory_for_vector_db,
        }

    @staticmethod
    def find_skipped_docs(input_table: pa.Table, output_table: pa.Table, reason: str) -> dict[str, Any]:
        """
        Compares two PyArrow tables to find documents that are in the input but not
        in the output, and returns them in a structured format.

        Args:
            input_table: The PyArrow Table with the initial set of documents.
                         Must contain both the ID and Name columns.
            output_table: The PyArrow Table with the processed documents.
            reason: A string explaining why these documents were skipped.

        Returns:
            A dictionary containing:
            - 'skipped_docs': A list of DocsStructure dictionaries for skipped items.
            - 'skipped_docs_count': The integer count of skipped items.
        """
        # 1. Get the set of IDs from the output table for fast lookup.
        output_ids_set = set(output_table.column(OperatorConstants.ID).to_pylist())

        # 2. Get the ID and Name columns from the input table.
        input_ids = input_table.column(OperatorConstants.ID).to_pylist()
        input_names = input_table.column(OperatorConstants.NAME).to_pylist()

        # 3. Iterate through the input data and build the list of skipped docs.
        skipped_docs_list: list[DocsStructure] = []
        for doc_id, doc_name in zip(input_ids, input_names, strict=False):
            # If the ID from the input is NOT in the output set, it was skipped.
            if doc_id not in output_ids_set:
                skipped_docs_list.append({"id": doc_id, "name": doc_name, "reason": reason})

        return {
            Metrics.External.SKIPPED_DOCS: skipped_docs_list,
            Metrics.External.SKIPPED_DOCS_COUNT: len(skipped_docs_list),
        }

    @staticmethod
    def get_aggregated_flow_logs(job_id, jobrun_id):
        """
        Private method to retrieve operator logs based on the execution environment.

        Args:
            job_id: The ID of the job.
            jobrun_id: The ID of the specific job run.

        Returns:
            A dictionary containing the operator logs.
        """
        from common.util.operator_log_details import get_log_and_job_file_path

        log_final_path, _, _, aggregated_job_log_path = get_log_and_job_file_path(job_id=job_id, jobrun_id=jobrun_id)

        if os.path.exists(aggregated_job_log_path):
            with open(aggregated_job_log_path) as file:
                aggregated_flow_logs = json.load(file)
        else:
            return {"message": "Logs are not available.!"}

        # Normalize node_stats before returning
        if isinstance(aggregated_flow_logs, dict) and "job_stats" in aggregated_flow_logs:
            job_stats = aggregated_flow_logs["job_stats"]
            if isinstance(job_stats, dict):
                normalize_node_stats_for_dto(job_stats)
        return aggregated_flow_logs

    @staticmethod
    def determine_final_job_status(*, node_stats_list: dict) -> ExecutionStatus:
        """Determines the most severe job status from a list of node statuses."""
        if not node_stats_list:
            return ExecutionStatus.STARTING

        min_code = min(
            status_codes.get(
                ExecutionStatus(node.node_status if isinstance(node, NodeStatsDto) else node["node_status"]),
                1000,
            )
            for node in node_stats_list.values()
            if (isinstance(node, NodeStatsDto) and node.node_status)
            or (isinstance(node, dict) and node.get("node_status"))
        )

        for status, code in status_codes.items():
            if code == min_code:
                return status

        return ExecutionStatus.COMPLETED

    @staticmethod
    def get_unique_ids(
        tables: pa.Table | list[pa.Table] | dict[str, pa.Table] | None,
        id_col=OperatorConstants.ID,
    ):
        # wrap single table as list
        if isinstance(tables, pa.Table):
            tables = [tables]
        elif not isinstance(tables, list):
            tables = list(tables.values())

        if not tables:  # empty list
            return []

        seen = set()
        unique_ids = []
        for table in tables:
            if id_col in table.column_names:
                for val in table.column(id_col).to_pylist():
                    if val not in seen:
                        seen.add(val)
                        unique_ids.append(val)
        return unique_ids

    @staticmethod
    def epoch_ms_to_iso8601_utc(epoch_ms: int | None) -> str | None:
        """
        Convert epoch time in milliseconds to ISO8601 UTC string format.

        Args:
            epoch_ms: Epoch time in milliseconds

        Returns:
             ISO8601 formatted datetime string with 'Z' timezone indicator,or None if conversion fails
        """
        if not epoch_ms:
            return None
        try:
            dt = datetime.datetime.fromtimestamp(epoch_ms / 1000, tz=datetime.UTC)
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        except (ValueError, TypeError, OverflowError) as e:
            OperatorUtils.logger.error(f"Failed to convert epoch milliseconds to ISO8601: {e}")
            return None

    @staticmethod
    def is_operator_present_in_flow(flow_definition: dict, operator: str) -> bool:
        """
        Check if any operator in the flow definition is an ACL operator.

        Args:
            flow_definition: The flow definition dictionary.
        Returns:
            True if an ACL operator is present, False otherwise.
        """
        if not flow_definition or not isinstance(flow_definition, dict):
            return False

        exists = any(node.get("operator") == operator for node in flow_definition.get("dag", []))

        return exists


def get_missing_operator(features: list[str]):
    from common.util.operator_metadata import OperatorMetadata

    operator_metadata = OperatorMetadata()
    feature_operators_map = operator_metadata.get_feature_operators_map()
    operator_list = set()
    for feature in features:
        oplist: list = feature_operators_map.get(feature, [])
        # Temporary change to omit Extract Json operator name from validation failure logs
        if "Extract Json" in oplist:
            oplist.remove("Extract Json")
        operator_list.update(oplist)
    return operator_list
