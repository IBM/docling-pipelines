import os
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from operator import itemgetter
from queue import Queue
from typing import ParamSpec, TypeVar

import pyarrow as pa
from data_processing.data_access import DataAccess, DataAccessFactory

from common.constants.constants import DatasiftConstants, ExecutionStatus, Metrics
from common.constants.operator_constants import OperatorConstants
from common.exceptions.datasift_exceptions import FlowExecutionFailedException
from common.models.session_info import SessionInfo, get_session_info, set_session_info
from common.util.core.datetime import get_current_timestamp
from common.util.data.incremental_update import IncrementalUpdateUtil
from common.util.data.pyarrow_handler import BaseParquetTableHandler, get_parquet_table_handler
from common.util.infrastructure.filesystem import get_data_path
from common.util.infrastructure.logging import get_logger
from common.util.infrastructure.performance import log_elapsed_time
from common.util.job_tracker.tracker.job_tracker import JobStatsDto, JobTracker
from common.util.orchestration.deleted_rows_tracker import (
    combine_cumulative_deleted_rows,
)
from common.util.orchestration.flow_utils import construct_deleted_rows_table_path
from common.util.orchestration.prefect_config import (
    clean_up_prefect_home,
)
from core.operators.abstract_operator import OperatorCategory
from core.operators.operator_utils import OperatorUtils
from core.orchestrator.abstract_operator_executor import AbstractOperatorExecutor
from core.orchestrator.batch_manager import BatchManager
from core.orchestrator.node_logger import NodeLogger
from core.orchestrator.prefect_engine import AbstractFlowEngine, ExecuteStepResults, PrefectEngine

logger = get_logger()

R = TypeVar("R")  # The return type of the user's function
P = ParamSpec("P")
thread_pool_executor = ThreadPoolExecutor(max_workers=20)


class AbstractOrchestrator(ABC):
    def __init__(self) -> None:
        self.canceling = False
        self.failing = False
        self.job_run_id: str | None = None
        self.job_id: str | None = None
        self.context_id: str | None = None
        self.jobs_client = None
        self.logger = get_logger()
        self.message = ""
        self.flow_id = None
        self.deleted_rows_list: Queue[pa.Table] = Queue()
        # Initialize batch manager
        self.batch_manager = BatchManager()
        self.job_tracker = JobTracker()
        # Initialize Prefect flow executor
        self.flow_engine: AbstractFlowEngine = None
        self.job_log_path = None
        self.common_log_arguments = None
        # Initialize node logger
        self.node_logger: NodeLogger | None = None

    def initialize(self, *, job_id, job_run_id):
        self.flow_id = get_session_info().flow_id
        self.job_id = job_id
        self.job_run_id = job_run_id
        self.job_log_path = self.create_log_folders(job_id=self.job_id, type_="job")
        self.common_log_arguments = {
            DatasiftConstants.JOB_ID: self.job_id,
            DatasiftConstants.JOB_RUN_ID: self.job_run_id,
        }
        self.flow_engine = PrefectEngine(
            orchestrator=self,
            batch_manager=self.batch_manager,
            job_id=job_id,
            job_run_id=job_run_id,
            job_log_path=self.job_log_path,
        )
        self.node_logger = NodeLogger(common_log_arguments=self.common_log_arguments)

    def execute(self, *, flow_def: dict, params: dict):
        """
        Executes the given flow
        """
        _, job_run_id = itemgetter(DatasiftConstants.JOB_ID, DatasiftConstants.JOB_RUN_ID)(params)
        self.job_id = params.get(DatasiftConstants.JOB_ID)
        self.job_run_id = params.get(DatasiftConstants.JOB_RUN_ID)
        global_config = (
            flow_def.get(OperatorConstants.Config.GLOBAL_CONFIG, {})
            | params
            | {DatasiftConstants.FLOW_DEFINITION: flow_def}
        )

        if DatasiftConstants.DAG not in flow_def:
            raise FlowExecutionFailedException("Invalid flow: 'dag' not found in the flow definition")

        op_flow = flow_def.get(DatasiftConstants.DAG, [])

        if self.job_tracker.cancel_job_run_if_cancelling(job_run_id=job_run_id, job_log_path=self.job_log_path):
            return
        self.job_tracker.start_tracking_job(orchestrator=self, job_id=self.job_id, job_run_id=self.job_run_id)
        self.context_id = params.get(DatasiftConstants.CONTEXT_ID, self.job_id)
        try:
            self.execute_flow(op_flow=op_flow, global_config=global_config)
        finally:
            self._check_and_upload_deleted_rows()

    def _get_ingest_summary_message(self, *, output_table, deleted_docs_count: int, operator: dict) -> str | None:
        """Process and log ingest step results."""
        if output_table.num_rows == 0 and operator[OperatorConstants.Misc.OPERATOR] != OperatorConstants.Operators.NOOP:
            message = "No documents are ingested."
            if deleted_docs_count > 0:
                message += f" But {deleted_docs_count} document{'s' if deleted_docs_count != 1 else ''} {'were' if deleted_docs_count != 1 else 'was'} removed."
            self.logger.info(message, extra=self.common_log_arguments)
            return message
        return None

    def _handle_node_failure(self, *, e, op_def, global_config):
        from common.exceptions.error_codes import ErrorCode

        self.failing = True
        node_stats = {
            "name": op_def["name"],
            "node_status": ExecutionStatus.FAILED.value,
            "error": str(e),
            "error_code": ErrorCode.OPERATOR_EXECUTION_FAILED.value
        }
        self.job_tracker.update_node_stats(
            job_run_id=self.job_run_id,
            node_id=op_def[OperatorConstants.Columns.ID],
            node_stats=node_stats,
        )
        logger.error(e, stack_info=True, exc_info=True, extra=self.common_log_arguments)
        # if any exception occur for any operator,
        # we should add node_stats in above format in job_stats.json file
        job_stats = self.job_tracker.get_job(job_run_id=self.job_run_id)
        self.job_tracker.write_job_logs(job_stats=job_stats, job_log_path=self.job_log_path)
        # below logger will add failure reason in flow_execute.log
        if self.node_logger:
            self.node_logger.log_node_failure(
                node_id=op_def[OperatorConstants.Columns.ID],
                node_name=op_def[OperatorConstants.Columns.NAME],
                error=e,
                global_config=global_config
            )

    def _handle_active_execution(
        self, *, op_def, executor: AbstractOperatorExecutor, prev_data_access: dict[str, DataAccess]
    ):
        if executor.get_operator().short_name == OperatorConstants.Operators.DESIGN_FLOW_OUTPUT_OPERATOR:
            # save the deleted rows as this is needed for DESIGN_FLOW_OUTPUT_OPERATOR
            self._check_and_upload_deleted_rows()

        # LATER: based on some config, pass None to deleted_rows_list to skip tracking deleted rows
        data_accesses, metadata = executor.execute(
            data_access=prev_data_access, deleted_rows_list=self.deleted_rows_list
        )

        # Removing the internal metrics from the operator metadata if any to another dict
        internal_metadata = OperatorUtils.remove_internal_metrics_from_metadata(metadata=metadata)

        operator = executor.get_operator()
        retain_deleted = operator.config.get(
            DatasiftConstants.RETAIN_DELETED_DOCS,
            DatasiftConstants.RETAIN_DELETED_DOCS_DEFAULT,
        )
        force_ingest = operator.config.get(DatasiftConstants.FORCE_INGEST, False)

        if operator.category == OperatorCategory.Ingest and not force_ingest:
            if not retain_deleted:
                metadata[Metrics.Internal.DELETED_FROM_LAST_RUN] = internal_metadata.get(
                    Metrics.Internal.DELETED_FROM_LAST_RUN, 0
                )
            else:
                metadata[Metrics.Internal.DELETED_FROM_LAST_RUN] = "N/A"

        tables = self.__get_tables_from_data_accesses(executor=executor, data_accesses=data_accesses)

        # storing node metadata to a json file
        OperatorUtils.store_node_metadata(op_def, metadata)

        return data_accesses, tables, metadata, internal_metadata

    def _handle_skipped_execution(
        self,
        *,
        op_def,
        executor: AbstractOperatorExecutor,
        prev_results: ExecuteStepResults | dict[str, ExecuteStepResults],
        global_config,
        start
    ):
        node_id = op_def.get(OperatorConstants.Columns.ID)
        node_name = op_def.get(OperatorConstants.Columns.NAME)
        operator_type = op_def.get(OperatorConstants.Misc.OPERATOR)

        tables = (
            prev_results.tables
            if isinstance(prev_results, ExecuteStepResults)
            else [res.tables[0] for res in prev_results.values()]
        )
        data_accesses = executor.create_data_accesses(tables)
        end_time = get_current_timestamp()

        node_stats = {
            "name": node_name,
            "node_status": ExecutionStatus.SKIPPED.value,
            "start_time": start,
            "end_time": end_time,
            "col_names": prev_results.tables[0].column_names
            if isinstance(prev_results, ExecuteStepResults) and len(prev_results.tables) == 1
            else [],
            "time_taken": end_time - start,
        }

        if self.node_logger:
            self.node_logger.log_skipped_execution(
                node_id=node_id, node_name=node_name, operator_type=operator_type, global_config=global_config
            )

        self.job_tracker.update_node_stats(self.job_run_id, node_id=node_id, node_stats=node_stats)

        return data_accesses, tables

    def _execute_step(
        self,
        *,
        op_def,
        global_config,
        prev_results: ExecuteStepResults | dict[str, ExecuteStepResults],
        deleted_docs_count,
    ):
        start = get_current_timestamp()
        executor = self.create_executor(op_def=op_def, global_config=global_config)

        if isinstance(prev_results, ExecuteStepResults):
            prev_data_access = prev_results.data_accesses[0]
            prev_table = prev_results.tables[0]
        else:
            # prev_results is a dictionary of [str, ExecuteStepResults]
            prev_data_access = {link_name: res.data_accesses[0] for link_name, res in prev_results.items()}
            prev_table = [res.tables[0] for res in prev_results.values()]
        skip = self.evaluate_execution_skip(executor=executor, tables=prev_table, deleted_docs_count=deleted_docs_count)
        metadata = {}
        internal_metadata = {}
        if skip:
            data_accesses, tables = self._handle_skipped_execution(
                op_def=op_def, executor=executor, prev_results=prev_results, global_config=global_config, start=start
            )
        else:
            data_accesses, tables, metadata, internal_metadata = self._handle_active_execution(
                op_def=op_def, executor=executor, prev_data_access=prev_data_access
            )

        processed_docs_count = OperatorUtils.find_doc_count_from_tables(tables=tables)
        if Metrics.External.PROCESSED_DOCS not in metadata:
            metadata[Metrics.External.PROCESSED_DOCS] = processed_docs_count
        operator_category = executor.get_operator().category
        if internal_metadata.get(Metrics.Internal.DELETED_FROM_LAST_RUN):
            metadata[Metrics.External.DELETED_DOC_COUNT] = internal_metadata.get(Metrics.Internal.DELETED_FROM_LAST_RUN)
        self.job_tracker.update_doc_counts(
            job_run_id=self.job_run_id,
            metadata=metadata,
            operator_category=operator_category,
        )

        job_stats = self.job_tracker.get_job(job_run_id=self.job_run_id)
        jobs_framework_state = job_stats.status

        if jobs_framework_state == ExecutionStatus.CANCELING:
            self.canceling = True
        log_elapsed_time(start_time=start, operator=op_def[OperatorConstants.Misc.OPERATOR])

        return ExecuteStepResults(data_accesses, tables, internal_metadata)

    def __get_tables_from_data_accesses(self, *, executor, data_accesses):
        tables = []
        for data_access in data_accesses:
            output_file_path = executor.get_output_file_path(data_access=data_access)
            table, _ = data_access.get_table(output_file_path)
            if table is None:
                raise FlowExecutionFailedException(f"Failed while reading data from file: {output_file_path}")
            tables.append(table)
        return tables

    def evaluate_execution_skip(
        self,
        *,
        executor: AbstractOperatorExecutor,
        tables: pa.Table | list[pa.Table] | None,
        deleted_docs_count,
    ):
        def all_tables_are_empty():
            if tables is None:
                return True
            if isinstance(tables, list):
                return all(table.num_rows == 0 for table in tables)
            return tables.num_rows == 0

        if executor.get_operator().category != OperatorCategory.Ingest:
            # Special case to delete the data from vector store when input documents are deleted,
            # and no new documents are added for this flow execution
            if executor.get_operator().category == OperatorCategory.VectorDB and deleted_docs_count > 0:
                return False
            if all_tables_are_empty():
                return True
        return False

    def _check_and_upload_deleted_rows(self):
        if not self.deleted_rows_list.empty():
            try:
                cumulative_deleted_rows = combine_cumulative_deleted_rows(self.deleted_rows_list)
                deleted_rows_table_path = construct_deleted_rows_table_path(
                    job_id=self.job_id, job_run_id=self.job_run_id
                )
                parquet_table_handler: BaseParquetTableHandler = get_parquet_table_handler()
                # delete table if exists already
                parquet_table_handler.delete_file(path=deleted_rows_table_path)
                parquet_table_handler.save_table(path=deleted_rows_table_path, table=cumulative_deleted_rows)
                self.logger.info(f"Successfully captured {cumulative_deleted_rows.num_rows} deleted documents.")
            except Exception as e:
                self.logger.warning(f"Failed to save unprocessed docs table — skipping it. Error: {e}")

    def cancel(self):
        """
        Request for cancelling a running job
        """
        self.canceling = True

    def pause(self):  # noqa: B027
        """
        Request for pausing a running job
        """
        pass

    def resume(self):  # noqa: B027
        """
        Request for resuming a paused job
        """
        pass

    def get_type(self):  # noqa: B027
        """
        Returns the type of the orchestrator, Python or Spark
        """
        pass

    def create_log_folders(self, *, job_id, type_):
        """
        Created 3 folders, UDP_logs/jobId/JobrunID. The log for that job will be stored there
        """
        # PLACEHOLDER log TILL LOG LOCATION IS DECIDED
        log_location_path = get_data_path()
        log_app_location = DatasiftConstants.UDP_LOGS

        log_job_folder_name = job_id
        log_job_location = os.path.join(
            log_location_path,
            log_app_location,
            log_job_folder_name,
            str(self.job_run_id),
        )
        os.makedirs(log_job_location, exist_ok=True)
        if type_ == "flow":
            log_job_run_file_name = "flow_execute.log"
        elif type_ == "job":
            log_job_run_file_name = "job_stats.json"

        log_final_path = os.path.join(log_job_location, log_job_run_file_name)
        return log_final_path

    def create_executor(self, *, op_def: dict, global_config: dict) -> AbstractOperatorExecutor:
        # note: In the union of 2 dictionaries below, if an element exists in both global config and local config (
        # op_def['config']), the value from global_config will be overwritten by the local config
        global_config = {} if global_config is None else global_config
        operator_config = op_def.get(OperatorConstants.Config.CONFIG, {})
        operator_config_params = global_config.get(
            op_def[OperatorConstants.Columns.NAME],
            global_config.get(
                op_def[OperatorConstants.Columns.ID],
                global_config.get(op_def[OperatorConstants.Misc.OPERATOR], {}),
            ),
        )
        operator_name = op_def[OperatorConstants.Columns.NAME]
        operator_id = op_def[OperatorConstants.Columns.ID]
        # 1. Configuration defined for the operator takes precedence over the global configuration in the flow.
        # 2. The operator configuration passed through parameters would override the operator config defined in the flow
        config = (
            {OperatorConstants.Columns.NAME: operator_name}
            | {OperatorConstants.Columns.ID: operator_id}
            | global_config
            | operator_config
            | operator_config_params
        )
        return self.create_executor_impl(
            name=operator_name,
            operator=op_def[OperatorConstants.Misc.OPERATOR],
            params=config,
        )

    @abstractmethod
    def create_executor_impl(self, *, name: str, operator: str, params: dict) -> AbstractOperatorExecutor:
        """The concrete subclasses needs to implement this method"""
        pass

    def visualize(self):  # noqa: B027
        # The concrete subclasses needs to implement this method
        pass

    def _inner_task(
        self,
        op_def,
        global_config,
        prev_results: ExecuteStepResults | dict[str, ExecuteStepResults],
        session_info: SessionInfo,
        deleted_docs_count,
        link_id=None,
    ) -> ExecuteStepResults | None:
        if prev_results is None:
            if self.node_logger:
                self.node_logger.log_error_in_previous_step(
                    node_id=op_def[OperatorConstants.Columns.ID],
                    node_name=op_def[OperatorConstants.Columns.NAME],
                    global_config=global_config
                )
            return None
        # exit early if the execution was cancelled or aborted.
        if self.failing or self.canceling:
            if self.node_logger:
                self.node_logger.log_cancellation_or_abort(
                    node_id=op_def[OperatorConstants.Columns.ID],
                    node_name=op_def[OperatorConstants.Columns.NAME],
                    is_cancelling=self.canceling,
                    global_config=global_config
                )
            return None
        set_session_info(session_info)

        # Get operator semaphore from batch manager (for micro-batching)
        operator_semaphore = self.batch_manager.get_operator_semaphore()

        try:
            if link_id and prev_results.internal_metadata:
                if len(prev_results.tables) != len(prev_results.internal_metadata.get(Metrics.Internal.BRANCHES)):
                    raise FlowExecutionFailedException(
                        f"Number of tables ({len(prev_results.tables)}) in previous operator output do not match branches ({len(prev_results.internal_metadata.get(Metrics.Internal.BRANCHES))}) created."
                    )
                result_index = (
                    prev_results.internal_metadata.get(Metrics.Internal.BRANCHES, {})
                    .get(link_id, {})
                    .get("result_index")
                )
                table = prev_results.tables[result_index]
                data_access = prev_results.data_accesses[result_index]
                internal_metadata = prev_results.internal_metadata.get(Metrics.Internal.BRANCHES, {}).get(link_id, {})
                prev_results = ExecuteStepResults([data_access], [table], internal_metadata)

            # If micro-batching enabled, acquire semaphore before executing operator
            if operator_semaphore:  # pragma: no cover
                operator_semaphore.acquire()
                try:
                    self.logger.debug(
                        f"Operator {op_def[OperatorConstants.Columns.NAME]}: acquired semaphore slot",
                        extra=self.common_log_arguments,
                    )
                    result = self._execute_step(
                        op_def=op_def,
                        global_config=global_config,
                        prev_results=prev_results,
                        deleted_docs_count=deleted_docs_count,
                    )
                finally:
                    operator_semaphore.release()
                    self.logger.debug(
                        f"Operator {op_def[OperatorConstants.Columns.NAME]}: released semaphore slot",
                        extra=self.common_log_arguments,
                    )
            else:
                # No semaphore - execute normally
                self.logger.debug(
                    f"Operator {op_def[OperatorConstants.Columns.NAME]}: acquired semaphore slot",
                    extra=self.common_log_arguments,
                )
                result = self._execute_step(
                    op_def=op_def,
                    global_config=global_config,
                    prev_results=prev_results,
                    deleted_docs_count=deleted_docs_count,
                )

            if not op_def.get(DatasiftConstants.OUTPUT_EDGES):
                if self.node_logger:
                    self.node_logger.log_branch_completion(
                        node_id=op_def[OperatorConstants.Columns.ID],
                        node_name=op_def[OperatorConstants.Columns.NAME],
                        global_config=global_config
                    )
            return result
        except Exception as e:
            self._handle_node_failure(e=e, op_def=op_def, global_config=global_config)
            # steps in output edges will exit early
            return None

    def _finalize_dag_flow(self, *, op_flow):
        if self.canceling or self.failing:
            status = ExecutionStatus.CANCELED if self.canceling else ExecutionStatus.FAILED
            self.job_tracker.end_job(
                job_run_id=self.job_run_id, status=status, message=self.message, job_log_path=self.job_log_path
            )
            self.logger.info(f">>> Job status is {status}.", extra=self.common_log_arguments)
            return

        job_stats = self.job_tracker.get_job(job_run_id=self.job_run_id)
        self.job_tracker.determine_and_update_final_documents_count(job_stats=job_stats, dag_nodes=op_flow)
        job_status = OperatorUtils.determine_final_job_status(node_stats_list=job_stats.node_stats)
        job_stats.status = job_status
        self.job_tracker.end_job(
            job_run_id=self.job_run_id, status=job_status, message=self.message, job_log_path=self.job_log_path
        )
        self.logger.info(f">>> Job status is {job_status}.", extra=self.common_log_arguments)

    # ??? insert some of the parameters to self.
    def execute_flow(self, *, op_flow, global_config):
        """
        Execute DAG flow with unified batching approach.
        Supports both batch mode (multiple batches) and non-batch mode (single table).

        Batch Creation Rules:
        - Batches are created ONLY when ALL conditions are met:
          1. ENABLE_MICRO_BATCHING is True (batching feature enabled)
          2. orchestrator_type is NOT SPARK (Spark doesn't support micro-batching)
        - When batching is enabled, MICRO_BATCH_SIZE is read (defaults to DEFAULT_MICRO_BATCH_SIZE)
        - Otherwise, entire ingested table is treated as single "batch" for unified execution

        Note: Micro-batching is only applied for Python orchestrator, not for Spark.
        """

        # Configure prefect server logging
        _ = get_logger(name="prefect")

        self.logger.info(">>> Starting flow execution with unified batching approach", extra=self.common_log_arguments)

        # Execute ingest operator to get initial table
        ingest_operator = op_flow[0]

        initial_result = self._create_empty_result()
        ingest_results = self._execute_step(
            op_def=ingest_operator, global_config=global_config, prev_results=initial_result, deleted_docs_count=0
        )

        deleted_docs_count = ingest_results.internal_metadata.get(Metrics.Internal.DELETED_FROM_LAST_RUN, 0)
        self.message = self._get_ingest_summary_message(
            output_table=ingest_results.tables[0], deleted_docs_count=deleted_docs_count, operator=ingest_operator
        )

        incremental_update_util = IncrementalUpdateUtil()
        doc_ids = ingest_results.internal_metadata.get(Metrics.Internal.ALL_DOC_IDS, [])
        incremental_update_util.process_ingested_docs(config=global_config, job_id=self.job_id, doc_ids=doc_ids)

        # Get the ingested table
        ingested_table = ingest_results.tables[0]

        # Check if table is empty
        if ingested_table.num_rows == 0:
            self.logger.info(">>> No data to process - skipping flow execution", extra=self.common_log_arguments)
            clean_up_prefect_home()
            self._finalize_dag_flow(op_flow=op_flow)
            return

        # Prepare batches using batch manager
        batches, global_config = self.batch_manager.prepare_batches(
            ingested_table=ingested_table, global_config=global_config, common_log_arguments=self.common_log_arguments
        )

        # Store ingest node ID for batch processing (needed to handle references to excluded ingest operator)
        ingest_node_id = op_flow[0].get(OperatorConstants.Columns.ID) if op_flow else None
        global_config[DatasiftConstants.INGEST_NODE_ID] = ingest_node_id

        # Build and execute batch flow (works for both single and multiple batches)
        self.flow_engine.execute_batch_flow(op_flow=op_flow, batches=batches, global_config=global_config)

        clean_up_prefect_home()
        self._finalize_dag_flow(op_flow=op_flow)

    def _create_empty_result(self):
        data_access_factory = DataAccessFactory()
        config = {"data_config": {"da_class": "data_processing.data_access.DataAccessMemory"}}
        data_access_factory.apply_input_params(config)
        data_access = data_access_factory.create_data_access()
        data_access.save_table(path="", table=pa.Table.from_arrays([], names=[]))
        return ExecuteStepResults([data_access], [pa.Table.from_arrays(arrays=[], names=[])], None)

    @staticmethod
    def _collect_failed_doc_ids(*, job_stats: JobStatsDto | None) -> list[str]:
        """Collect all failed document IDs from node stats"""
        if not job_stats:
            return []

        failed_doc_ids: list[str] = []
        for node_stats in job_stats.node_stats.values():
            if node_stats.failed_docs:
                failed_doc_ids.extend(node_stats.failed_docs)
        return failed_doc_ids
