"""
Prefect Flow Executor - Handles all Prefect-specific execution logic.

This class encapsulates Prefect flow building, task creation, and execution management,
separating these concerns from the main orchestrator logic.
"""

import copy
import threading
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any, ParamSpec, TypeVar

from prefect import flow, task
from prefect.futures import PrefectFuture
from prefect.runtime import task_run
from prefect.states import Completed
from prefect.task_runners import ThreadPoolTaskRunner

from common.constants.constants import DatasiftConstants, TaskType
from common.constants.operator_constants import OperatorConstants
from common.exceptions.datasift_exceptions import (
    ErrorCode,
    FlowExecutionFailedException,
    FlowValidationException,
    PrefectFlowFailed,
)
from common.models.session_info import get_session_info
from common.util.data.incremental_update import IncrementalUpdateUtil
from common.util.infrastructure.logging import get_logger
from common.util.job_tracker.tracker.job_tracker import JobTracker
from common.util.orchestration.flow_utils import create_node_id_to_index_map
from common.util.orchestration.prefect_config import set_prefect_env_variables
from core.orchestrator.futured_list import FuturedList

set_prefect_env_variables()

logger = get_logger()

R = TypeVar("R")  # The return type of the user's function
P = ParamSpec("P")


class ExecuteStepResults:
    """Results from executing a single step/operator."""

    def __init__(self, data_accesses: list, tables: list, internal_metadata):
        self.data_accesses = data_accesses
        self.tables = tables
        self.internal_metadata = internal_metadata


class AbstractFlowEngine(ABC):
    def __init__(self, *, orchestrator, batch_manager, job_id, job_run_id, job_log_path):
        """
        Initialize the Prefect flow executor.

        Args:
            orchestrator: Reference to the parent AbstractOrchestrator instance
        """
        self.orchestrator = orchestrator
        self.batch_manager = batch_manager
        self.logger = get_logger()
        self.job_id = job_id
        self.job_run_id = job_run_id
        self.job_log_path = job_log_path
        self.common_log_arguments = {
            DatasiftConstants.JOB_ID: self.job_id,
            DatasiftConstants.JOB_RUN_ID: self.job_run_id,
        }

    @abstractmethod
    def execute_batch_flow(self, *, op_flow, batches, global_config):
        pass

    @abstractmethod
    def execute_non_execute_flow(self, *, flow_name=None, task, dag):
        pass


class PrefectEngine(AbstractFlowEngine):
    """
    Handles Prefect-specific flow execution logic.

    This class is responsible for:
    - Building Prefect flows with appropriate configuration
    - Creating and managing Prefect tasks
    - Executing flows with proper task orchestration
    - Managing batch execution with parallelism control
    """

    def __init__(self, *, orchestrator, batch_manager, job_id, job_run_id, job_log_path):
        super().__init__(
            orchestrator=orchestrator,
            batch_manager=batch_manager,
            job_id=job_id,
            job_run_id=job_run_id,
            job_log_path=job_log_path,
        )

    def execute_batch_flow(self, *, op_flow, batches, global_config):
        batch_outer_flow = self._build_flow(name="batch_outer_flow", flow_impl=self.batch_outer_flow_impl)
        batch_futures = batch_outer_flow(
            op_flow=op_flow[1:],  # Skip ingest operator
            batches=batches,
            global_config=global_config,
        )

        # Wait for all sub-flows to complete
        # Note: Metadata is saved incrementally by each sub-flow in inner_flow() at line 1194
        # so we don't need to merge and save results here
        self._wait_for_sub_flows(batch_futures=batch_futures)

    def execute_non_execute_flow(self, *, flow_name=None, task, dag):

        flow = self.build_non_execute_flow(flow_name=flow_name)
        flow(TaskType.VALIDATE_FLOW, task, dag, None)

    def _build_flow(self, *, name, flow_impl):
        """Build a Prefect flow for operator execution."""
        prefect_config = self.__get_prefect_config()

        return flow(
            name=name,
            timeout_seconds=prefect_config["timeout_seconds"],
            retries=prefect_config["flow_retries"],
            retry_delay_seconds=prefect_config["retry_delay_seconds"],
            log_prints=prefect_config["log_prints"],
            task_runner=ThreadPoolTaskRunner(max_workers=prefect_config["max_workers"]),
        )(flow_impl)

    def build_non_execute_flow(self, *, flow_name=None):
        """Build a Prefect flow for non-execution tasks (validation, etc.)."""
        prefect_config = self.__get_prefect_config()

        return flow(
            name="task_pipeline" if flow_name is None else flow_name,
            timeout_seconds=prefect_config["timeout_seconds"],
            retries=prefect_config["flow_retries"],
            retry_delay_seconds=prefect_config["retry_delay_seconds"],
            log_prints=prefect_config["log_prints"],
            task_runner=ThreadPoolTaskRunner(max_workers=prefect_config["max_workers"]),
        )(self.__non_execute_inner_flow)

    def batch_outer_flow_impl(self, op_flow, batches, global_config):
        """
        Process batches using Prefect sub-flows with DAG parallelism.

        Each batch executes as an independent Prefect sub-flow that processes
        the entire DAG with full operator-level parallelism.

        Manages batch semaphore lifecycle:
        - Initializes semaphore at start
        - Resets semaphore in finally block (via _wait_for_sub_flows)
        """
        # Initialize batch semaphore for batch-level concurrency control
        max_concurrent_batches = global_config.get(
            DatasiftConstants.MAX_CONCURRENT_BATCHES,
            DatasiftConstants.DEFAULT_MAX_CONCURRENT_BATCHES,
        )
        if not isinstance(max_concurrent_batches, int) or max_concurrent_batches <= 0:
            raise FlowExecutionFailedException(
                f"{DatasiftConstants.MAX_CONCURRENT_BATCHES} must be a positive integer, got {max_concurrent_batches!r}"
            )

        self.batch_manager.initialize_batch_semaphore(max_concurrent_batches=max_concurrent_batches)

        # 1. Build the inner flow to execute a batch once (reusable for all batches)
        inner_flow = self._build_flow(name="batch_sub_flow", flow_impl=self.__flow_impl)

        # Create a task wrapper for subflow execution
        def batch_cache_key_fn(context, parameters):
            """Custom cache key that excludes batch_data_access to avoid serialization errors."""
            return f"{parameters.get('batch_num')}_{self.job_run_id}"

        # 2. Define a task to execute inner flow
        @task(cache_key_fn=batch_cache_key_fn)
        def batch_subflow_task(batch_num, op_flow, global_config, batch_data_access):
            """Execute a single batch as a Prefect subflow."""
            batch_semaphore = self.batch_manager.get_batch_semaphore()

            # Acquire batch semaphore before batch execution
            if batch_semaphore:
                batch_semaphore.acquire()
                self.logger.info(
                    f"Batch {batch_num}: acquired batch semaphore slot",
                    extra=self.common_log_arguments,
                )

            try:
                self.logger.info(f"Batch {batch_num}: starting execution", extra=self.common_log_arguments)
                batch_global_config = global_config.copy()
                if global_config.get(DatasiftConstants.ENABLE_MICRO_BATCHING, False):
                    batch_global_config[DatasiftConstants.BATCH_NUM] = batch_num

                result = inner_flow(op_flow=op_flow, data_access=batch_data_access, global_config=batch_global_config)
                self.logger.info(f"Batch {batch_num}: completed execution", extra=self.common_log_arguments)
                return result
            finally:
                # Release batch semaphore in finally block to ensure cleanup
                if batch_semaphore:
                    batch_semaphore.release()
                    self.logger.info(
                        f"Batch {batch_num}: released batch semaphore slot",
                        extra=self.common_log_arguments,
                    )

        # Submit all batches as tasks
        batch_futures = []

        for batch_num, batch_table in enumerate(batches):
            batch_data_access = self.batch_manager.create_batch_data_access(batch_table=batch_table)

            # 3. Submit task that executes sub flow for each batch
            future = batch_subflow_task.submit(
                batch_num=batch_num, op_flow=op_flow, global_config=global_config, batch_data_access=batch_data_access
            )
            batch_futures.append((batch_num, future))

        return batch_futures

    def _wait_for_sub_flows(self, *, batch_futures):
        """
        Wait for all sub-flows (batches) to complete with fail-fast cancellation.

        Note: This method does not return batch results to avoid loading all PyArrow tables
        into memory. Each sub-flow saves its metadata incrementally.
        """
        failed_batch = None
        cancellation_event = threading.Event()
        cancelled_futures: list[tuple[int, PrefectFuture]] = []

        try:
            for future_index, (batch_num, future) in enumerate(batch_futures):
                # Check if another batch already failed
                if cancellation_event.is_set():
                    try:
                        future.cancel()
                        cancelled_futures.append((batch_num, future))
                        self.logger.info(
                            f"Cancelled batch {batch_num} due to failure in batch {failed_batch}",
                            extra=self.common_log_arguments,
                        )
                    except Exception as cancel_error:
                        self.logger.warning(
                            f"Could not cancel batch {batch_num}: {cancel_error}",
                            extra=self.common_log_arguments,
                        )
                    continue

                try:
                    future.result()
                    self.logger.info(
                        f"Batch {batch_num} completed successfully",
                        extra=self.common_log_arguments,
                    )

                except Exception as e:
                    # Batch failed - trigger cancellation
                    failed_batch = batch_num
                    cancellation_event.set()

                    self.logger.error(
                        f"Batch {batch_num} failed, cancelling all remaining batches: {e}",
                        extra=self.common_log_arguments,
                        exc_info=True,
                    )

                    for remaining_num, remaining_future in batch_futures[future_index + 1 :]:
                        try:
                            remaining_future.cancel()
                            cancelled_futures.append((remaining_num, remaining_future))
                            self.logger.info(
                                f"Cancelled batch {remaining_num}",
                                extra=self.common_log_arguments,
                            )
                        except Exception as cancel_error:
                            self.logger.warning(
                                f"Could not cancel batch {remaining_num}: {cancel_error}",
                                extra=self.common_log_arguments,
                            )

                    # Re-raise the exception to fail the entire job
                    raise FlowExecutionFailedException(
                        f"Batch {batch_num} failed during sub-flow execution: {e}"
                    ) from e
        finally:
            for cancelled_batch_num, cancelled_future in cancelled_futures:
                try:
                    cancelled_future.wait()
                    self.logger.info(
                        f"Cancelled batch {cancelled_batch_num} reached terminal state before semaphore reset",
                        extra=self.common_log_arguments,
                    )
                except Exception as wait_error:
                    self.logger.warning(
                        f"Error while waiting for cancelled batch {cancelled_batch_num} to finish: {wait_error}",
                        extra=self.common_log_arguments,
                    )

            self.logger.info(
                "Resetting batch semaphore after sub-flow completion",
                extra=self.common_log_arguments,
            )
            self.batch_manager.reset_batch_semaphore()

    def __get_prefect_config(self) -> dict:
        """Get the default values for Prefect settings."""
        return {
            "task_retries": 0,
            "persist_result": False,
            "flow_retries": 0,
            "max_workers": 50,
            "log_prints": True,
            "retry_delay_seconds": 60,
            "timeout_seconds": 60000,
        }

    def __create_task(self, *, task_func, retries=0, persist_result=False) -> task:
        """Create a Prefect task for operator execution."""

        def generate_task_name():
            parameters = task_run.parameters
            return parameters["op_def"]["name"]

        return task(
            task_func,
            task_run_name=generate_task_name,
            retries=retries,
            persist_result=persist_result,
        )

    def __create_main_task(self, main_task, retries=0, persist_result=False) -> task:
        """Create a Prefect task for non-execution flows."""

        def generate_task_name():
            parameters = task_run.parameters
            return parameters["task_name"]

        return task(
            main_task,
            task_run_name=generate_task_name,
            retries=retries,
            persist_result=persist_result,
        )

    def __flow_impl(self, op_flow, data_access, global_config):
        """
        Execute the inner flow with Prefect task orchestration.

        This method builds and executes a DAG of operators using Prefect tasks,
        handling dependencies and parallelism automatically.
        """
        # In batch mode, get the ingest operator ID from global_config
        ingest_node_id = global_config.get(DatasiftConstants.INGEST_NODE_ID)
        batch_num = global_config.get(DatasiftConstants.BATCH_NUM)

        self.logger.info(
            f"inner_flow: batch_num={batch_num}, ingest_node_id={ingest_node_id}, op_flow_length={len(op_flow)}",
            extra=self.common_log_arguments,
        )

        def get_prev_results(op_definitions, results_: FuturedList, initial_batch_result) -> PrefectFuture | dict[str, PrefectFuture]:
            prev_res: dict[str, PrefectFuture] = {}
            has_ingest_dependency = False

            for prev_node in op_definitions.get(DatasiftConstants.INPUT_EDGES, []):
                node_id_ref = prev_node["node_id_ref"]

                if node_id_ref not in node_id_to_index_map:
                    self.logger.debug(
                        f"Node {node_id_ref} not in node_id_to_index_map. Checking: ingest_node_id={ingest_node_id}, match={node_id_ref == ingest_node_id}",
                        extra=self.common_log_arguments,
                    )

                    if ingest_node_id and node_id_ref == ingest_node_id:
                        self.logger.debug(
                            f"Found ingest node dependency {node_id_ref} - will use batch data",
                            extra=self.common_log_arguments,
                        )
                        has_ingest_dependency = True
                        continue
                    else:
                        self.logger.error(
                            f"Node {node_id_ref} not found in flow. ingest_node_id={ingest_node_id}",
                            extra=self.common_log_arguments,
                        )
                        raise FlowExecutionFailedException(f"Node {node_id_ref} not found in flow")

                prev_index = node_id_to_index_map[node_id_ref]
                prev_res[prev_node.get(DatasiftConstants.LINK_NAME)] = results_.get_future(prev_index)

            # If the only dependency is the ingest node, return the initial batch result
            if not prev_res and has_ingest_dependency:
                return initial_batch_result

            if len(prev_res) == 1:
                return next(iter(prev_res.values()))
            return prev_res

        prefect_config = self.__get_prefect_config()
        task_retries = prefect_config["task_retries"]
        persist_result = prefect_config["persist_result"]
        inner_task = self.__create_task(
            task_func=self.orchestrator._inner_task,
            retries=task_retries,
            persist_result=persist_result,
        )
        session_info = get_session_info()

        results: FuturedList = FuturedList.from_size(len(op_flow))
        destinations: list[tuple[PrefectFuture, Any]] = []
        node_id_to_index_map = create_node_id_to_index_map(flow_def=op_flow)
        deleted_docs_count = 0
        incremental_update_util = IncrementalUpdateUtil()

        is_sequential_flow = (
            False
            if op_flow[0].get(DatasiftConstants.INPUT_EDGES) or op_flow[0].get(DatasiftConstants.OUTPUT_EDGES)
            else True
        )
        prev_index = None

        # Create initial batch result for first operator after ingest
        batch_table = data_access.get_table("")[0]
        initial_batch_result = ExecuteStepResults([data_access], [batch_table], {})

        for op_def in op_flow:
            index = node_id_to_index_map[op_def[OperatorConstants.Columns.ID]]
            try:
                link_id = op_def.get(OperatorConstants.Misc.LINK_ID, None)
                if prev_index is None:
                    prev_results = initial_batch_result
                else:
                    prev_results = (
                        results.get_future(prev_index) if is_sequential_flow else get_prev_results(op_def, results, initial_batch_result)
                    )

                future = inner_task.submit(
                    op_def=op_def,
                    global_config=global_config,
                    prev_results=prev_results,
                    session_info=session_info,
                    deleted_docs_count=deleted_docs_count,
                    link_id=link_id,
                )

                if is_sequential_flow:
                    destinations = [(future, op_def)]
                    results.set_entry(index, future, 1)
                else:
                    if not op_def.get(DatasiftConstants.OUTPUT_EDGES):
                        destinations.append((future, op_def))
                    else:
                        results.set_entry(index, future, len(op_def.get(DatasiftConstants.OUTPUT_EDGES)))
                prev_index = index
            except Exception as e:
                self.orchestrator._handle_node_failure(e=e, op_def=op_def, global_config=global_config)

        self.__wait_for_tasks(destinations=destinations)
        failed_doc_ids = self._collect_failed_doc_ids()

        tables = [
            destination[0].result().tables[0]
            for destination in destinations
            if hasattr(destination[0], "result")
            and destination[0].result()
            and hasattr(destination[0].result(), "tables")
        ]
        incremental_update_util.save_metadata_for_incremental_update(
            job_id=self.orchestrator.context_id,
            job_run_id=self.job_run_id,
            tables=tables,
            failed_doc_ids=failed_doc_ids,
        )

    def __non_execute_inner_flow(
        self,
        task_type: TaskType,
        inner_task: Callable[P, R],
        op_flow,
        local_result,
        **kwargs,
    ):
        """Execute non-execution flow (validation, etc.) with Prefect tasks."""
        prefect_config = self.__get_prefect_config()
        task_retries = prefect_config["task_retries"]
        persist_result = prefect_config["persist_result"]
        main_task = self.__create_main_task(main_task=inner_task, retries=task_retries, persist_result=persist_result)
        results: FuturedList = FuturedList.from_size(len(op_flow))
        destinations: list[tuple[PrefectFuture, Any]] = []
        final_destination = None
        node_id_to_index_map = create_node_id_to_index_map(flow_def=op_flow)
        stop_submission = False
        submitted_futures: list[tuple[PrefectFuture, Any]] = []
        result = copy.copy(local_result)

        for op_def in op_flow:
            if stop_submission:
                continue
            index = node_id_to_index_map[op_def.get("id")]
            try:
                if op_def["input_edges"]:
                    link_name = op_def.get(OperatorConstants.Misc.LINK_NAME)
                    prev_futures = []
                    for edge in op_def["input_edges"]:
                        prev_index = node_id_to_index_map[edge["node_id_ref"]]
                        prev_future = results.get_future(prev_index)
                        prev_futures.append(prev_future)

                    if len(prev_futures) == 1:
                        prev_results = prev_futures[0]
                    else:
                        prev_results = prev_futures

                    future = main_task.submit(op_def[OperatorConstants.Columns.NAME], op_def, prev_results, link_name)

                else:
                    future = main_task.submit(op_def[OperatorConstants.Columns.NAME], op_def, result, None)
                submitted_futures.append((future, op_def))

                if not op_def.get(DatasiftConstants.OUTPUT_EDGES):
                    destinations.append((future, op_def))
                else:
                    results.set_entry(index, future, len(op_def.get(DatasiftConstants.OUTPUT_EDGES)))

                if kwargs.get("stop_node_id") == op_def.get(OperatorConstants.Columns.ID):
                    logger.info(
                        f"Stop node reached: {op_def.get(OperatorConstants.Columns.NAME)} id:{op_def.get(OperatorConstants.Columns.ID)}"
                    )
                    logger.info(
                        f"No more tasks will be submitted, waiting for current tasks: {len(submitted_futures)} to complete"
                    )
                    stop_submission = True
                    final_destination = future

            except Exception as e:
                error = f"Branched flow task execution failed for {task_type.value} in non operator execution flow with error:{e!s}"
                logger.error(error, stack_info=True, exc_info=True)
                raise PrefectFlowFailed(message=error, error_code=ErrorCode.PREFECT_FLOW_TASK_FAILED) from e

        self.__wait_for_tasks_with_exceptions(destinations=submitted_futures, task_type=task_type)
        self.__wait_for_tasks_with_exceptions(destinations=destinations, task_type=task_type)
        if stop_submission:
            if final_destination is not None:
                local_result.update_final_result(final_destination.result())
            return Completed(
                message=f"Flow stopped after node but allowed {len(submitted_futures)} tasks to complete",
                name="EarlyStopped",
            )

    def __wait_for_tasks(self, *, destinations):
        """Wait for all tasks to complete."""
        futures = [item[0] for item in destinations]
        for future in futures:
            if hasattr(future, "wait"):
                future.wait()

    def __wait_for_tasks_with_exceptions(self, *, destinations, task_type: TaskType):
        """Wait for all tasks to complete and handle exceptions."""
        futures = [item[0] for item in destinations]
        try:
            for future in futures:
                future.result()
        except FlowValidationException as se:
            error = f"Branched flow task execution failed for {task_type.value} in non operator execution flow with error:{se!s}"
            logger.error(error, stack_info=True, exc_info=True)
            raise se
        except Exception as e:
            error = f"Branched flow task execution failed for {task_type.value} in non operator execution flow with error:{e!s}"
            logger.error(error, stack_info=True, exc_info=True)
            raise PrefectFlowFailed(message=error, error_code=ErrorCode.PREFECT_FLOW_TASK_FAILED) from e

    def _collect_failed_doc_ids(self) -> list[str]:
        """Collect all failed document IDs from node stats"""

        job_tracker = JobTracker()
        job_stats = job_tracker.get_job(job_run_id=self.job_run_id)
        if not job_stats:
            return []

        failed_doc_ids: list[str] = []
        for node_stats in job_stats.node_stats.values():
            if node_stats.failed_docs:
                failed_doc_ids.extend(node_stats.failed_docs)
        return failed_doc_ids


# Made with Bob
