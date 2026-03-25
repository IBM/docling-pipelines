import json
import os
import threading
from abc import ABC
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from operator import itemgetter
from queue import Queue
from typing import ParamSpec, TypeVar

import pyarrow as pa
from data_processing.data_access import DataAccess, DataAccessFactory

from common.constants.constants import DatasiftConstants, ExecutionStatus, Metrics
from common.constants.operator_constants import OperatorConstants
from common.exceptions.datasift_exceptions import FlowExecutionFailedException
from common.models.session_info import SessionInfo, get_session_info, set_session_info
from common.util.datasift_utils import get_current_timestamp
from common.util.iceberg_util import get_warehouse_path
from common.util.incremental_update_util import IncrementalUpdateUtil
from common.util.job_tracker.tracker.job_tracker import JobStatsDto, JobTracker
from common.util.log import get_logger

# Note that get_logs is imported for the test cases
from common.util.operator_utils import find_doc_count_from_tables, remove_internal_metrics_from_metadata

from common.util.orchestrator_utils import (
    clean_up_prefect_home,
    combine_cumulative_deleted_rows,
    construct_deleted_rows_table_path
)
from common.util.parquet_table_handler import BaseParquetTableHandler, get_parquet_table_handler
from common.util.perf_utils import log_elapsed_time
from core.operators.abstract_operator import OperatorCategory
from core.operators.operator_utils import OperatorUtils
from core.orchestrator.abstract_operator_executor import AbstractOperatorExecutor
from core.orchestrator.batch_manager import BatchManager
from core.orchestrator.prefect_flow_executor import PrefectFlowExecutor, ExecuteStepResults  # noqa: E402

logger = get_logger()
CANCELLED_MSG = ">>> Cancelled the execution: %s"

R = TypeVar("R")  # The return type of the user's function
P = ParamSpec("P")
thread_pool_executor = ThreadPoolExecutor(max_workers=20)


class AbstractOrchestrator(ABC):
    def __init__(self) -> None:
        self.__canceling = False
        self.__failing = False
        self.__job_run_id: str | None = None
        self.__job_id: str | None = None
        self.context_id: str | None = None
        self.jobs_client = None
        self.logger = get_logger()
        self.message = ""
        # Note: test_mode env variable is set only while running cliapp test cases
        self.test_mode = os.environ.get("test_mode", "False") == "True"
        self.flow_id = get_session_info().flow_id
        self.deleted_rows_list: Queue[pa.Table] = Queue()
        # Initialize batch manager
        self.batch_manager = BatchManager()
        # Initialize Prefect flow executor
        self.prefect_executor = PrefectFlowExecutor(self)
        self.common_log_arguments = None

    def set_job_ids(self, *, job_id, job_run_id):
        self.__job_id = job_id
        self.__job_run_id = job_run_id
        self.common_log_arguments = {DatasiftConstants.JOB_ID: self.__job_id, DatasiftConstants.JOB_RUN_ID: self.__job_run_id}
        self.prefect_executor.set_job_ids(job_id=job_id, job_run_id=job_run_id)

    def get_job_run_id(self):
        return self.__job_run_id

    def get_job_id(self):
        return self.__job_id

    def get_cancelling(self):
        return self.__canceling

    def execute(self, *, flow_def: dict, params: dict):
        """
        Executes the given flow
        """
        job_id, job_run_id = itemgetter(DatasiftConstants.JOB_ID, DatasiftConstants.JOB_RUN_ID)(params)
        self.__job_id = params.get(DatasiftConstants.JOB_ID)
        self.__job_run_id = params.get(DatasiftConstants.JOB_RUN_ID)
        global_config = (
            flow_def.get(OperatorConstants.Config.GLOBAL_CONFIG, {})
            | params
            | {DatasiftConstants.FLOW_DEFINITION: flow_def}
        )

        if DatasiftConstants.DAG not in flow_def:
            raise FlowExecutionFailedException("Invalid flow: 'dag' not found in the flow definition")

        op_flow = flow_def.get(DatasiftConstants.DAG, [])

        job_tracker = JobTracker()
        if job_tracker.get_job(job_run_id=self.__job_run_id) is None:
            if job_tracker.cancel_job_run_if_cancelling(job_run_id=job_run_id):
                self.logger.info(CANCELLED_MSG, job_run_id)
                return
            job_tracker.start_tracking_job(orchestrator=self, job_id=self.__job_id, job_run_id=self.__job_run_id)
        job_log_final_path = self.create_log_folders_cpd(job_id=self.__job_id, type_="job")
        self.context_id = params.get(DatasiftConstants.CONTEXT_ID, self.__job_id)
        try:
            self.execute_flow(op_flow=op_flow, global_config=global_config, job_log_final_path=job_log_final_path)
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

    def _handle_exception(self, *, e, op_def, job_log_final_path, global_config):
        self.__failing = True
        node_stats = {
            "name": op_def["name"],
            "node_status": ExecutionStatus.FAILED.value,
            "error": str(e),
        }
        job_tracker = JobTracker()
        job_tracker.update_node_stats(
            job_run_id=self.__job_run_id,
            node_id=op_def[OperatorConstants.Columns.ID],
            node_stats=node_stats,
        )
        logger.error(e, stack_info=True, exc_info=True, extra=self.common_log_arguments)
        # if any exception occur for any operator,
        # we should add node_stats in above format in job_stats.json file
        job_stats = job_tracker.get_job(job_run_id=self.__job_run_id)
        self.write_jobs_logs(job_stats=job_stats, job_log_final_path=job_log_final_path)
        # below logger will add failure reason in flow_execute.log
        node_logger = self._get_node_logger(
            node_id=op_def[OperatorConstants.Columns.ID],
            node_name=op_def[OperatorConstants.Columns.NAME],
            global_config=global_config,
        )
        node_logger.error(
            ">>> Node %s failed and caused aborting the branch execution: %s transaction_ID: %s",
            op_def["name"],
            e,
            get_session_info().transaction_id,
            extra=self.common_log_arguments
        )
        """
        This gets called only when you are running flow executor from local settings and not through web_flow_executor
        """
        if self.test_mode:
            job_tracker.end_job(
                job_run_id=self.__job_run_id,
                status=ExecutionStatus.FAILED,
                message=str(e),
            )
            job_stats = job_tracker.get_job(job_run_id=self.__job_run_id)
            self.write_job_logs_local(job_stats=job_stats, job_log_final_path=job_log_final_path)

    def _handle_active_execution(self,
        *,
        op_def,
        executor: AbstractOperatorExecutor,
        prev_data_access: dict[str, DataAccess]
    ):
        if executor.get_operator().short_name == OperatorConstants.Operators.DESIGN_FLOW_OUTPUT_OPERATOR:
            # save the deleted rows as this is needed for DESIGN_FLOW_OUTPUT_OPERATOR
            self._check_and_upload_deleted_rows()

        # LATER: based on some config, pass None to deleted_rows_list to skip tracking deleted rows
        data_accesses, metadata = executor.execute(
            data_access=prev_data_access, deleted_rows_list=self.deleted_rows_list
        )

        # Removing the internal metrics from the operator metadata if any to another dict
        internal_metadata = remove_internal_metrics_from_metadata(metadata=metadata)

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

    def _handle_skipped_execution(self,
        *,
        op_def,
        executor: AbstractOperatorExecutor,
        prev_results,
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

        op_logger = self._get_node_logger(node_id=node_id, node_name=node_name, global_config=global_config)
        op_logger.info(
            ">>> ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~",
            extra=self.common_log_arguments,
        )
        application_id: str = f" ApplicationId:{os.getenv('JOB_ID')}" if os.getenv("JOB_ID") else ""
        op_logger.info(f"Orchestrator Type: {str(get_session_info().orchestrator).upper()}{application_id}")
        op_logger.info("Step ID: %s", op_def[OperatorConstants.Columns.ID], extra=self.common_log_arguments)
        op_logger.info(
            ">>> Skipped execution for Step Name: %s, operator: %s because no input data available for processing.",
            node_name,
            operator_type,
            extra=self.common_log_arguments,
        )

        JobTracker().update_node_stats(self.__job_run_id, node_id=node_id, node_stats=node_stats)

        op_logger.info(
            ">>> ================================================================",
            extra=self.common_log_arguments,
        )

        return data_accesses, tables

    def _get_node_logger(self, *, node_id, node_name, global_config):
        pg_params = {
            DatasiftConstants.JOB_ID: global_config.get(DatasiftConstants.JOB_ID),
            DatasiftConstants.JOB_RUN_ID: global_config.get(DatasiftConstants.JOB_RUN_ID),
            DatasiftConstants.NODE_ID: node_id,
            OperatorConstants.Columns.NAME: node_name,
        }
        return get_logger(
            name=f"{DatasiftConstants.LOGGER_NAME} : NodeLogger : {node_id}",
            level="INFO",
            is_pg=True,
            pg_params=pg_params,
        )

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
                op_def=op_def,
                executor=executor,
                prev_results=prev_results,
                global_config=global_config,
                start=start
            )
        else:
            data_accesses, tables, metadata, internal_metadata = self._handle_active_execution(
                op_def=op_def,
                executor=executor,
                prev_data_access=prev_data_access
            )

        processed_docs_count = find_doc_count_from_tables(tables=tables)
        if Metrics.External.PROCESSED_DOCS not in metadata:
            metadata[Metrics.External.PROCESSED_DOCS] = processed_docs_count
        operator_category = executor.get_operator().category
        job_tracker = JobTracker()
        if internal_metadata.get(Metrics.Internal.DELETED_FROM_LAST_RUN):
            metadata[Metrics.External.DELETED_DOC_COUNT] = internal_metadata.get(Metrics.Internal.DELETED_FROM_LAST_RUN)
        job_tracker.update_doc_counts(
            job_run_id=self.__job_run_id,
            metadata=metadata,
            operator_category=operator_category,
        )

        job_stats = job_tracker.get_job(job_run_id=self.__job_run_id)
        jobs_framework_state = job_stats.status

        if jobs_framework_state == ExecutionStatus.CANCELING:
            self.__canceling = True
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
                    job_id=self.__job_id, job_run_id=self.__job_run_id
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
        self.__canceling = True

    def pause(self):
        """
        Request for pausing a running job
        """
        pass

    def resume(self):
        """
        Request for resuming a paused job
        """
        pass

    def get_type(self):
        """
        Returns the type of the orchestrator, Python or Spark
        """
        pass

    def create_log_folders_cpd(self, *, job_id, type_):
        """
        Created 3 folders, UDP_logs/jobId/JobrunID. The log for that job will be stored there
        """
        # PLACEHOLDER log TILL LOG LOCATION IS DECIDED
        log_location_path = get_warehouse_path(path="")
        log_app_location = DatasiftConstants.UDP_LOGS

        log_job_folder_name = job_id
        log_job_location = os.path.join(
            log_location_path,
            log_app_location,
            log_job_folder_name,
            str(self.__job_run_id),
        )
        os.makedirs(log_job_location, exist_ok=True)
        if type_ == "flow":
            log_job_run_file_name = "flow_execute.log"
        elif type_ == "job":
            log_job_run_file_name = "job_stats.json"

        log_final_path = os.path.join(log_job_location, log_job_run_file_name)
        return log_final_path

    def write_job_logs_local(self, *, job_stats, job_log_final_path):
        with open(job_log_final_path, "w") as file:
            json.dump(job_stats.model_dump(), file, indent=4)

    def write_jobs_logs(self, *, job_stats, job_log_final_path):
        stats = deepcopy(job_stats)
        self._remove_node_metadata_from_node_stats(job_stats=stats)
        self.write_job_logs_local(job_stats=stats, job_log_final_path=job_log_final_path)

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

    def create_executor_impl(self, *, name: str, operator: str, params: dict) -> AbstractOperatorExecutor:
        # The concrete subclasses needs to implement this method
        pass

    def visualize(self):
        # The concrete subclasses needs to implement this method
        pass


    def _inner_task(
        self,
        op_def,
        global_config,
        prev_results: ExecuteStepResults | dict[str, ExecuteStepResults],
        job_log_final_path,
        session_info: SessionInfo,
        deleted_docs_count,
        link_id=None
    ) -> ExecuteStepResults | None:
        node_logger = self._get_node_logger(
            node_id=op_def[OperatorConstants.Columns.ID],
            node_name=op_def[OperatorConstants.Columns.NAME],
            global_config=global_config
        )
        if prev_results is None:
            node_logger.info(
                ">>> Error detected in previous step — node %s skipped. ",
                op_def["name"],
                extra=self.common_log_arguments
            )
            return None
        # exit early if the execution was cancelled or aborted.
        if self.__failing or self.__canceling:
            msg = "Cancelling" if self.__canceling else "Aborting"
            node_logger.info(
                ">>> %s the branch execution at node name: %s ",
                msg,
                op_def["name"],
                extra=self.common_log_arguments
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
                        extra=self.common_log_arguments
                    )
                    result = self._execute_step(
                        op_def=op_def,
                        global_config=global_config,
                        prev_results=prev_results,
                        deleted_docs_count=deleted_docs_count
                    )
                finally:
                    operator_semaphore.release()
                    self.logger.debug(
                        f"Operator {op_def[OperatorConstants.Columns.NAME]}: released semaphore slot",
                        extra=self.common_log_arguments
                    )
            else:
                # No semaphore - execute normally
                self.logger.debug(
                    f"Operator {op_def[OperatorConstants.Columns.NAME]}: acquired semaphore slot",
                    extra=self.common_log_arguments
                )
                result = self._execute_step(
                    op_def=op_def,
                    global_config=global_config,
                    prev_results=prev_results,
                    deleted_docs_count=deleted_docs_count,
                )

            if not op_def.get(DatasiftConstants.OUTPUT_EDGES):
                node_logger.info(
                    ">>> Branch execution completed at node name: %s ",
                    op_def["name"],
                    extra=self.common_log_arguments
                )
            return result
        except Exception as e:
            self._handle_exception(
                e=e,
                op_def=op_def,
                job_log_final_path=job_log_final_path,
                global_config=global_config
            )
            # steps in output edges will exit early
            return None

    def _finalize_dag_flow(self, *, op_flow, job_log_final_path):
        job_tracker = JobTracker()
        if self.__canceling or self.__failing:
            status = ExecutionStatus.CANCELED if self.__canceling else ExecutionStatus.FAILED
            job_tracker.end_job(self.__job_run_id, status=status, message=self.message)
            job_stats = job_tracker.get_job(job_run_id=self.__job_run_id)
            self.write_jobs_logs(job_stats=job_stats, job_log_final_path=job_log_final_path)
            self.logger.info(f">>> Job status is {status}.", extra=self.common_log_arguments)
            return

        job_stats = job_tracker.get_job(job_run_id=self.__job_run_id)
        job_tracker.determine_and_update_final_documents_count(job_stats=job_stats, dag_nodes=op_flow)
        job_status = OperatorUtils.determine_final_job_status(node_stats_list=job_stats.node_stats)
        job_stats.status = job_status
        job_tracker.end_job(self.__job_run_id, status=job_status, message=self.message)
        self.write_jobs_logs(job_stats=job_stats, job_log_final_path=job_log_final_path)
        self.logger.info(f">>> Job status is {job_status}.", extra=self.common_log_arguments)

    # ??? insert some of the parameters to self.
    def execute_flow(self, *, op_flow, global_config, job_log_final_path):
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

        if JobTracker().cancel_job_run_if_cancelling(self.__job_run_id):
            self.logger.info(CANCELLED_MSG, self.__job_run_id)
            return None

        # Configure prefect server logging
        _ = get_logger(name="prefect")

        self.logger.info(
            ">>> Starting flow execution with unified batching approach",
            extra=self.common_log_arguments
        )

        # Execute ingest operator to get initial table
        ingest_operator = op_flow[0]

        initial_result = self._create_empty_result()
        ingest_results = self._execute_step(
            op_def=ingest_operator, global_config=global_config, prev_results=initial_result, deleted_docs_count=0
        )

        deleted_docs_count = ingest_results.internal_metadata.get(Metrics.Internal.DELETED_FROM_LAST_RUN, 0)
        self.message = self._get_ingest_summary_message(
            output_table=ingest_results.tables[0],
            deleted_docs_count=deleted_docs_count,
            operator=ingest_operator
        )

        incremental_update_util = IncrementalUpdateUtil()
        doc_ids = ingest_results.internal_metadata.get(Metrics.Internal.ALL_DOC_IDS, [])
        incremental_update_util.process_ingested_docs(config=global_config, job_id=self.__job_id, doc_ids=doc_ids)

        # Get the ingested table
        ingested_table = ingest_results.tables[0]

        # Check if table is empty
        if ingested_table.num_rows == 0:
            self.logger.info(">>> No data to process - skipping flow execution", extra=self.common_log_arguments)
            clean_up_prefect_home()
            self._finalize_dag_flow(op_flow=op_flow, job_log_final_path=job_log_final_path)
            return

        # Prepare batches using batch manager
        batches, global_config = self.batch_manager.prepare_batches(
            ingested_table=ingested_table,
            global_config=global_config,
            common_log_arguments=self.common_log_arguments
        )

        # Store ingest node ID for batch processing (needed to handle references to excluded ingest operator)
        ingest_node_id = op_flow[0].get(OperatorConstants.Columns.ID) if op_flow else None
        global_config[DatasiftConstants.INGEST_NODE_ID] = ingest_node_id

        # Build and execute batch flow (works for both single and multiple batches)
        batch_outer_flow = self.prefect_executor.build_flow(name="batch_outer_flow",
                                                            flow_impl=self.prefect_executor.batch_outer_flow_impl)
        batch_futures = batch_outer_flow(
            op_flow=op_flow[1:],  # Skip ingest operator
            batches=batches,
            global_config=global_config,
            job_log_final_path=job_log_final_path,
        )

        # Wait for all sub-flows to complete
        # Note: Metadata is saved incrementally by each sub-flow in inner_flow() at line 1194
        # so we don't need to merge and save results here
        self.wait_for_sub_flows(batch_futures=batch_futures)

        clean_up_prefect_home()
        self._finalize_dag_flow(op_flow=op_flow, job_log_final_path=job_log_final_path)

    def _create_empty_result(self):
        data_access_factory = DataAccessFactory()
        config = {"data_config": {"da_class": "data_processing.data_access.DataAccessMemory"}}
        data_access_factory.apply_input_params(config)
        data_access = data_access_factory.create_data_access()
        data_access.save_table(path="", table=pa.Table.from_arrays([], names=[]))
        return ExecuteStepResults([data_access], [pa.Table.from_arrays(arrays=[], names=[])], None)

    def wait_for_sub_flows(self, *, batch_futures):
        """
        Wait for all sub-flows (batches) to complete with fail-fast cancellation.

        Note: This method does not return batch results to avoid loading all PyArrow tables
        into memory. Each sub-flow saves its metadata incrementally.
        """
        failed_batch = None
        cancellation_event = threading.Event()

        for batch_num, future in batch_futures:
            # Check if another batch already failed
            if cancellation_event.is_set():
                try:
                    future.cancel()
                    self.logger.info(
                        f"Cancelled batch {batch_num} due to failure in batch {failed_batch}",
                        extra=self.common_log_arguments,
                    )
                except Exception as e:
                    self.logger.warning(f"Could not cancel batch {batch_num}: {e}")
                continue

            try:
                future.result()
                self.logger.info(
                    f"Batch {batch_num} completed successfully",
                    extra=self.common_log_arguments,
                )

            except Exception as e:
                # Batch failed - trigger cancellation
                cancellation_event.set()

                self.logger.error(
                    f"Batch {batch_num} failed, cancelling all remaining batches: {e}",
                    extra=self.common_log_arguments,
                    exc_info=True,
                )

                for remaining_num, remaining_future in batch_futures[batch_num + 1 :]:
                    try:
                        remaining_future.cancel()
                        self.logger.info(
                            f"Cancelled batch {remaining_num}",
                            extra=self.common_log_arguments,
                        )
                    except Exception as cancel_error:
                        self.logger.warning(f"Could not cancel batch {remaining_num}: {cancel_error}")

                self.batch_manager.reset_operator_semaphore()
                # Re-raise the exception to fail the entire job
                raise FlowExecutionFailedException(f"Batch {batch_num} failed, all batches cancelled") from e

        self.batch_manager.reset_operator_semaphore()

    @staticmethod
    def _remove_node_metadata_from_node_stats(*, job_stats):
        for node_id, node_stat in job_stats.node_stats.items():
            if hasattr(node_stat, OperatorConstants.Config.NODE_METADATA):
                node_stat.node_metadata = None


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
