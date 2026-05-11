from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from operator import itemgetter
from queue import Queue
from typing import ParamSpec, TypeVar

import pyarrow as pa
from data_processing.data_access import DataAccess, DataAccessFactory

from datasift.core.constants.constants import DatasiftConstants, ExecutionStatus, Metrics
from datasift.core.constants.operator_constants import OperatorConstants
from datasift.core.job_management.domain.ports import JobRunManager, JobStatsService
from datasift.core.models.session_info import SessionInfo, get_session_info, set_session_info
from datasift.core.operators.abstract_operator import OperatorCategory
from datasift.core.operators.operator_utils import OperatorUtils
from datasift.core.orchestration.abstract_operator_executor import AbstractOperatorExecutor
from datasift.core.orchestration.batch_manager import BatchManager
from datasift.core.orchestration.flow_execution_event_handler import FlowExecutionEventHandler
from datasift.core.orchestration.prefect.prefect_engine import AbstractFlowEngine, ExecuteStepResults, PrefectEngine
from datasift.exceptions.datasift_exceptions import FlowExecutionFailedException
from datasift.utils.core.datetime import get_current_timestamp
from datasift.utils.data.incremental_update import IncrementalUpdateUtil
from datasift.utils.data.pyarrow_handler import BaseParquetTableHandler, get_parquet_table_handler
from datasift.utils.infrastructure.logging import get_logger
from datasift.utils.orchestration.deleted_rows_tracker import (
    combine_cumulative_deleted_rows,
)
from datasift.utils.orchestration.flow_utils import construct_deleted_rows_table_path
from datasift.utils.orchestration.prefect_config import (
    clean_up_prefect_home,
)

logger = get_logger()

R = TypeVar("R")  # The return type of the user's function
P = ParamSpec("P")
thread_pool_executor = ThreadPoolExecutor(max_workers=20)


class AbstractOrchestrator(ABC):
    def __init__(
        self,
        job_stats_service: JobStatsService | None = None,
        job_run_manager: JobRunManager | None = None,
        enable_custom_operators: bool = True,
        custom_operator_packages: list[str] | None = None,
    ) -> None:
        """
        Initialize orchestrator with optional job services.

        Args:
            job_stats_service: Optional job statistics service for tracking job execution
            job_run_manager: Optional framework job run manager for external status updates
            enable_custom_operators: Whether to enable custom operators (passed to operator factory)
            custom_operator_packages: List of custom operator packages (passed to operator factory)
        """
        self.enable_custom_operators = enable_custom_operators
        self.custom_operator_packages = custom_operator_packages
        self.job_status = ExecutionStatus.RUNNING
        self.job_run_id: str | None = None
        self.job_id: str | None = None
        self.context_id: str | None = None
        self.jobs_client = None
        self.logger = get_logger()
        self.message = ""
        self.flow_id = None
        self.deleted_rows_list: Queue[pa.Table] = Queue()
        self.job_stats_service = job_stats_service
        self.job_run_manager = job_run_manager
        self.flow_execution_event_handler = FlowExecutionEventHandler(
            job_stats_service=job_stats_service,
            job_run_manager=job_run_manager,
        )
        self.batch_manager = BatchManager()
        self.flow_engine: AbstractFlowEngine | None = None
        self.common_log_arguments = None

    def initialize(self, *, job_id, job_run_id):
        """
        Initialize orchestrator for a specific job run.

        Args:
            job_id: Job identifier
            job_run_id: Job run identifier
        """
        self.flow_id = get_session_info().flow_id
        self.job_id = job_id
        self.job_run_id = job_run_id
        self.common_log_arguments = {
            DatasiftConstants.JOB_ID: self.job_id,
            DatasiftConstants.JOB_RUN_ID: self.job_run_id,
        }

        # Initialize event handler for this job run
        self.flow_execution_event_handler.initialize(
            job_id=job_id, job_run_id=job_run_id, common_log_arguments=self.common_log_arguments
        )

        # Create Prefect engine for this job run
        self.flow_engine = PrefectEngine(
            orchestrator=self,
            batch_manager=self.batch_manager,
            job_id=job_id,
            job_run_id=job_run_id,
            job_log_path=self.flow_execution_event_handler.job_log_path,
        )

    def execute(self, *, flow_def: dict, params: dict):
        """
        Executes the given flow
        """
        job_id, job_run_id = itemgetter(DatasiftConstants.JOB_ID, DatasiftConstants.JOB_RUN_ID)(params)

        # Initialize the orchestrator with job_id and job_run_id
        self.initialize(job_id=job_id, job_run_id=job_run_id)

        global_config = (
            flow_def.get(OperatorConstants.Config.GLOBAL_CONFIG, {})
            | params
            | {DatasiftConstants.FLOW_DEFINITION: flow_def}
        )

        if DatasiftConstants.DAG not in flow_def:
            raise FlowExecutionFailedException("Invalid flow: 'dag' not found in the flow definition")

        op_flow = flow_def.get(DatasiftConstants.DAG, [])

        self.flow_execution_event_handler.before_flow_execution_start(orchestrtor=self)
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
        self.job_status = ExecutionStatus.FAILING
        self.flow_execution_event_handler.after_node_failure(
            node_id=op_def[OperatorConstants.Columns.ID],
            node_name=op_def[OperatorConstants.Columns.NAME],
            global_config=global_config,
            e=e,
        )

    def _handle_active_execution(
        self,
        *,
        op_def,
        executor: AbstractOperatorExecutor,
        prev_data_access: dict[str, DataAccess | None] | DataAccess | None,
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

        return data_accesses, tables, metadata, internal_metadata

    def _handle_skipped_execution(
        self,
        *,
        op_def,
        executor: AbstractOperatorExecutor,
        prev_results: ExecuteStepResults | dict[str, ExecuteStepResults],
        global_config,
        start,
    ):
        tables = (
            prev_results.tables
            if isinstance(prev_results, ExecuteStepResults)
            else [res.tables[0] for res in prev_results.values()]
        )
        data_accesses = executor.create_data_accesses(tables)
        end_time = get_current_timestamp()

        column_names = (
            prev_results.tables[0].column_names
            if isinstance(prev_results, ExecuteStepResults) and len(prev_results.tables) == 1
            else []
        )

        self.flow_execution_event_handler.after_node_skipped(
            node_id=op_def.get(OperatorConstants.Columns.ID),
            node_name=op_def.get(OperatorConstants.Columns.NAME),
            operator_type=op_def.get(OperatorConstants.Misc.OPERATOR),
            global_config=global_config,
            start_time=start,
            end_time=end_time,
            column_names=column_names,
        )

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
            prev_data_access = prev_results.data_accesses[0] if prev_results.data_accesses else None
            prev_table = prev_results.tables[0] if prev_results.tables else None
        else:
            # prev_results is a dictionary of [str, ExecuteStepResults]
            prev_data_access = {
                link_name: res.data_accesses[0] if res.data_accesses else None
                for link_name, res in prev_results.items()
            }
            prev_table = [res.tables[0] if res.tables else None for res in prev_results.values()]
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
        if internal_metadata.get(Metrics.Internal.DELETED_FROM_LAST_RUN):
            metadata[Metrics.External.DELETED_DOC_COUNT] = internal_metadata.get(Metrics.Internal.DELETED_FROM_LAST_RUN)

        self.flow_execution_event_handler.after_step_execution_complete(
            node_id=op_def[OperatorConstants.Columns.ID],
            node_name=op_def[OperatorConstants.Columns.NAME],
            operator_category=executor.get_operator().category,
            operator=op_def[OperatorConstants.Misc.OPERATOR],
            global_config=global_config,
            is_last_step=not op_def.get(DatasiftConstants.OUTPUT_EDGES),
            metadata=metadata,
            start_time=start,
        )

        # Update job status from job stats service
        if self.job_stats_service and self.job_run_id:
            job_stats = self.job_stats_service.get_job(job_run_id=self.job_run_id, include_node_stats=False)
            if job_stats:
                self.job_status = ExecutionStatus(job_stats.status)

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
        self.job_status = ExecutionStatus.CANCELING

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

        # Pass job stats service explicitly via constructor (not params)
        return self.create_executor_impl(
            name=operator_name,
            operator=op_def[OperatorConstants.Misc.OPERATOR],
            params=config,
            job_stats_service=self.job_stats_service,
        )

    @abstractmethod
    def create_executor_impl(
        self,
        *,
        name: str,
        operator: str,
        params: dict,
        job_stats_service: JobStatsService | None = None,
    ) -> AbstractOperatorExecutor:
        """The concrete subclasses needs to implement this method"""
        pass

    def visualize(self):
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

        self.flow_execution_event_handler.before_step_execution_start(
            node_id=op_def[OperatorConstants.Columns.ID],
            node_name=op_def[OperatorConstants.Columns.NAME],
            global_config=global_config,
            job_status=self.job_status,
            prev_results=prev_results,
        )

        # Record skipped node when upstream failure prevents execution
        if prev_results is None or self.job_status in (ExecutionStatus.FAILING, ExecutionStatus.CANCELING):
            # Determine user-friendly skip reason based on specific condition
            if self.job_status == ExecutionStatus.CANCELING:
                skip_reason = "Skipped - job cancellation requested by user"
            elif self.job_status == ExecutionStatus.FAILING:
                skip_reason = "Skipped - cannot proceed due to failure in pipeline"
            else:  # prev_results is None
                skip_reason = "Skipped - no data received from previous step"

            # Record skipped node via event handler (which extracts batch context from global_config)
            self.flow_execution_event_handler.after_node_skipped(
                node_id=op_def[OperatorConstants.Columns.ID],
                node_name=op_def[OperatorConstants.Columns.NAME],
                operator_type=op_def[OperatorConstants.Misc.OPERATOR],
                global_config=global_config,
                start_time=get_current_timestamp(),
                end_time=get_current_timestamp(),
                column_names=[],
                reason=skip_reason,
            )
            return None

        set_session_info(session_info)

        try:
            if link_id and isinstance(prev_results, ExecuteStepResults):
                if isinstance(prev_results.internal_metadata, dict):
                    branches = prev_results.internal_metadata.get(Metrics.Internal.BRANCHES)
                    if branches is None or not isinstance(branches, list):
                        raise FlowExecutionFailedException(
                            "Expected branches metadata as a list but found None or wrong type"
                        )

                    if len(prev_results.tables) != len(branches):
                        raise FlowExecutionFailedException(
                            f"Number of tables ({len(prev_results.tables)}) in previous operator output "
                            f"do not match branches ({len(branches)}) created."
                        )

                    branch_info = prev_results.internal_metadata.get(Metrics.Internal.BRANCHES, {}).get(link_id, {})
                    result_index = branch_info.get("result_index")
                    if result_index is None:
                        raise FlowExecutionFailedException(f"Result index not found for link_id {link_id}")

                    table = prev_results.tables[result_index]
                    data_access = prev_results.data_accesses[result_index]
                    internal_metadata = branch_info

                    prev_results = ExecuteStepResults([data_access], [table], internal_metadata)

            result = self._execute_step(
                op_def=op_def,
                global_config=global_config,
                prev_results=prev_results,
                deleted_docs_count=deleted_docs_count,
            )

            return result
        except Exception as e:
            self._handle_node_failure(e=e, op_def=op_def, global_config=global_config)
            # steps in output edges will exit early
            return None

    def _finalize_dag_flow(self, *, op_flow):
        self.flow_execution_event_handler.after_flow_execution_complete(
            op_flow=op_flow, present_job_status=self.job_status, message=self.message
        )

    # ??? insert some of the parameters to self.
    def execute_flow(self, *, op_flow, global_config):
        """
        Execute DAG flow with unified batching approach.
        Supports both batch mode (multiple batches) and non-batch mode (single table).

        Batch Creation Rules:
        - Batches are created ONLY when ALL conditions are met:
          1. ENABLE_MICRO_BATCHING is True (batching feature enabled)
        - When batching is enabled, MICRO_BATCH_SIZE is read (defaults to DEFAULT_MICRO_BATCH_SIZE)
        - Otherwise, entire ingested table is treated as single "batch" for unified execution

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

        flow_incremental_config = global_config.get(DatasiftConstants.INCREMENTAL_METADATA)
        incremental_update_util = IncrementalUpdateUtil(flow_config=flow_incremental_config)
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

        # Initialize pending batch node stats after batches are materialized
        self.flow_execution_event_handler.after_batches_prepared(
            batches=batches, op_flow=op_flow, global_config=global_config
        )

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
