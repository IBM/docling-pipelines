import copy
import os
import pprint
from datetime import datetime
from queue import Queue
from typing import Any

import pyarrow as pa
from data_processing.data_access import DataAccess, DataAccessFactory

from common.constants.constants import (
    DatasiftConstants,
    ExecutionStatus,
    Metrics,
)
from common.constants.operator_constants import OperatorConstants
from common.models.session_info import get_session_info
from common.util.log import get_logger
from common.util.orchestrator_utils import update_deleted_rows
from core.data_access.data_access_utils import DataAccessUtils
from core.operators.abstract_operator import AbstractOperator
from core.operators.operator_utils import OperatorUtils

logger = get_logger()


class AbstractOperatorExecutor:
    def __init__(self, name: str, operator: str, params: dict):
        """
        - name: The name of the step mentioned in the flow. Note that the name of the step is different from the operator name.
                This is because the user can have multiple steps with the same operator but different name.
                For example, we can have a flow with one regex operator for e-mail and another regex operator for ssn.
        - operator: Identifies the operator to be executed
        - params: dictionary of configuration information used while executing the operator
        """
        self._name = name
        self._operator = operator
        self._params = params | {OperatorConstants.Columns.NAME: name}
        DataAccessUtils.add_intermediate_storage_config(
            config=self._params,
            job_id=self._params.get(DatasiftConstants.JOB_ID),
            job_run_id=self._params.get(DatasiftConstants.JOB_RUN_ID),
        )

    def execute(
        self,
        *,
        data_access: DataAccess | dict[str, DataAccess | None] | None,
        deleted_rows_list: Queue[pa.Table] = None,
    ) -> tuple[list[DataAccess], dict[str, Any]]:
        input_tables = self._get_input_tables(data_access=data_access)
        out_tables, metadata = self._execute_impl(tables=input_tables)
        if deleted_rows_list is not None:
            deleted_rows = update_deleted_rows(
                prev_tables=input_tables,
                current_tables=out_tables,
                op=self.get_operator(),
                skip_columns=[
                    OperatorConstants.Columns.KVP_COLUMN,
                    OperatorConstants.Columns.DOC_COLUMN,
                ],
            )
            if deleted_rows.num_rows > 0:
                deleted_rows_list.put(deleted_rows)
        output_data_accesses = self.create_data_accesses(out_tables)

        return output_data_accesses, metadata

    def create_data_accesses(self, tables):
        data_accesses = []
        for index, table in enumerate(tables):
            data_access_factory = DataAccessFactory()
            params_copy = self.safely_deep_copy_params(params=self._params, skip_keys=[])
            # Add node name + index of the branch to the output folder
            DataAccessUtils.add_node_name_to_output_folder(
                params=params_copy, node_name=f"{params_copy['name']}_{index}"
            )
            data_access_factory.apply_input_params(params_copy)
            output_data_access = data_access_factory.create_data_access()
            output_file_path = self.get_output_file_path(data_access=output_data_access)
            output_data_access.save_table(output_file_path, table)
            data_accesses.append(output_data_access)
        return data_accesses

    def get_operator(self) -> AbstractOperator:
        # The concrete class implements the method by returning the operator for the corresponding orchestrator.
        pass

    def validate(self, *, errors: list, warnings: list, available_features: list):
        op = self.get_operator()
        op.validate(errors, warnings, available_features)

    def get_metadata(self):
        """
        The concrete subclasses give the given operator metadata identified by _operator by passing the given table
        """
        op = self.get_operator()
        return op.get_metadata()

    def _execute_impl(self, tables: pa.Table | dict[str, pa.Table] | None) -> tuple[list[pa.Table], dict[str, Any]]:
        """
        The concrete subclasses execute the given operator identified by _operator by passing the given tables
        """
        pass

    def _get_input_tables(
        self,
        *,
        data_access: DataAccess | dict[str, DataAccess | None] | None,
    ) -> pa.Table | dict[str, pa.Table] | None:
        if data_access is None:
            tables = None
        elif isinstance(data_access, DataAccess):
            input_file_path = self.get_output_file_path(data_access=data_access)
            tables, _ = data_access.get_table(input_file_path)
        else:
            tables = {}
            for link_name, access in data_access.items():
                if access is None:
                    # Note: Merge operators should be ready to receive an empty list of tables, or a list with a single table.
                    continue
                input_file_path = self.get_output_file_path(data_access=access)
                table, _ = access.get_table(input_file_path)
                tables[link_name] = table
        return tables

    def set_default_node_stats(self, *, tables: pa.Table | dict[str, pa.Table] | None):
        """Initializes and stores the starting statistics for a node.

        This sets the node's status to 'RUNNING' in the job tracker and records
        the start time and the total number of documents to be processed.

        Args:
            tables: The input PyArrow table for a regular node, or a list of PyArrow tables for a merge node
        """
        node_id = self._params[OperatorConstants.Columns.ID]
        logger.info(f"Initializing stats for node '{self._name}' (ID: {node_id}).")

        from common.util.job_tracker.tracker.job_tracker import JobTracker

        node_stats = {
            "name": self._name,
            "start_time": round(datetime.now().timestamp()),
            "total_docs": OperatorUtils.get_unique_ids(tables=tables),
            "node_status": ExecutionStatus.RUNNING.value,
        }
        JobTracker().update_node_stats(
            self._params[DatasiftConstants.JOB_RUN_ID],
            node_id=node_id,
            node_stats=node_stats,
        )
        logger.info(f"Initial stats for node '{node_id}' stored successfully.")

    def update_final_node_stats(self, *, tables: list[pa.Table], metadata: dict):
        """Updates the final statistics for a node after its execution completes.

        This records the end time, calculates total time taken, and updates the
        final counts for completed, failed, and skipped documents.

        Args:
            tables: The output PyArrow Tables from the node.
            metadata: A dictionary containing additional metrics like lists of
                      failed and skipped documents.
        """
        node_id = self._params[OperatorConstants.Columns.ID]
        job_run_id = self._params[DatasiftConstants.JOB_RUN_ID]
        logger.info(f"Updating final stats for node '{node_id}'.")

        from common.util.job_tracker.tracker.job_tracker import (
            ExecutionStatus,
            JobTracker,
            NodeStatsDto,
        )

        job_stats = JobTracker().get_job(job_run_id=job_run_id)
        existing_node = job_stats.node_stats.get(node_id, {})

        # Extract node stats based on type
        if isinstance(existing_node, NodeStatsDto):
            node_stats = existing_node.model_dump()
        else:
            node_stats = existing_node.copy() if existing_node else {}
        # Update timings and status
        end_time = round(datetime.now().timestamp())
        start_time = node_stats.get("start_time", end_time)  # Default to end_time to avoid negative values
        node_stats["end_time"] = end_time
        node_stats["time_taken"] = end_time - start_time
        node_stats["node_status"] = metadata.get(Metrics.External.NODE_STATUS, ExecutionStatus.COMPLETED.value)
        node_stats["col_names"] = tables[0].column_names
        # Update document lists and counts
        doc_ids_completed = OperatorUtils.get_unique_ids(tables=tables)
        node_stats["docs_completed"] = doc_ids_completed
        node_stats["docs_completed_count"] = len(doc_ids_completed)
        node_stats["failed_docs"] = [
            doc.get("id", "") for doc in metadata.get(Metrics.External.FAILED_DOCS, []) if isinstance(doc, dict)
        ]
        node_stats["skipped_docs"] = [
            doc.get("id", "") for doc in metadata.get(Metrics.External.SKIPPED_DOCS, []) if isinstance(doc, dict)
        ]
        if not node_stats.get("total_docs"):
            node_stats["total_docs"] = (
                node_stats["docs_completed"] + node_stats["failed_docs"] + node_stats["skipped_docs"]
            )
        logger.info(
            f"Node '{node_id}' stats summary: "
            f"{node_stats['docs_completed_count']} completed, "
            f"{len(node_stats['failed_docs'])} failed, "
            f"{len(node_stats['skipped_docs'])} skipped."
        )

        # Handle the error field logic
        for field in [Metrics.External.FAILED_DOCS, Metrics.External.SKIPPED_DOCS]:
            if metadata.get(field):
                error_message = f"Node completed with issues in {field}."
                node_stats["error"] = error_message
                logger.warning(f"Node '{node_id}': {error_message}")
                break

        # Pass the final, updated dictionary to the update function
        JobTracker().update_node_stats(job_run_id=job_run_id, node_id=node_id, node_stats=node_stats)
        logger.info(f"Final stats for node '{node_id}' stored successfully.")

    @staticmethod
    def get_output_file_path(*, data_access):
        output_folder = data_access.get_output_folder()
        if output_folder is None:
            return ""
        if not output_folder.endswith("/"):
            output_folder += "/"
        return output_folder + "output.parquet"

    @staticmethod
    def safely_deep_copy_params(*, params, skip_keys=None):
        """
        Deep copy a dictionary while skipping certain keys (shallow copied instead).

        Args:
            params (dict): The dictionary to copy.
            skip_keys (iterable): Keys to skip deep copying (default: None).

        Returns:
            dict: A copy of params with skip_keys shallow copied.
        """
        if skip_keys is None:
            skip_keys = []

        # Extract skip_keys with shallow copy
        shallow_parts = {k: v for k, v in params.items() if k in skip_keys}

        # Deep copy everything else
        deep_parts = {k: v for k, v in params.items() if k not in skip_keys}
        copied_params = copy.deepcopy(deep_parts)

        # Put back the shallow copied parts
        copied_params.update(shallow_parts)

        return copied_params

    def _log_start(self, *, op_logger, node_id, name, short_name, common_log_arguments):
        op_logger.info(
            ">>> ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~",
            extra=common_log_arguments,
        )
        application_id: str = f" ApplicationId:{os.getenv('JOB_ID')}" if os.getenv("JOB_ID") else ""
        op_logger.info(f"OrchestratorType:{str(get_session_info().orchestrator).upper()}{application_id}")
        op_logger.info("Step ID: %s", node_id, extra=common_log_arguments)
        op_logger.info(
            ">>> Starting execution: Step Name: %s, operator: %s",
            name,
            short_name,
            extra=common_log_arguments,
        )
        op_logger.info(f"Invoking the `transform` method of operator: '{short_name}'...\n")

    def _log_completion(self, *, op_logger, name, time_taken, result, metadata, common_log_arguments):
        op_logger.info(
            ">>> Completed execution: %s, time= %.2f seconds",
            name,
            time_taken,
            extra=common_log_arguments,
        )
        if result[0] and result[0][0]:
            op_logger.info("Schema:%s", str(result[0][0].schema), extra=common_log_arguments)
        op_logger.info("Operator Metadata:\n%s", pprint.pformat(metadata, indent=2))
        op_logger.info(
            ">>> ================================================================",
            extra=common_log_arguments,
        )
