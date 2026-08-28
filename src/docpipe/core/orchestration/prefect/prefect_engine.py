"""
Prefect Flow Engine - Prefect-specific implementation of FlowEnginePort.

This adapter implements flow execution using Prefect's task orchestration,
following hexagonal architecture principles by implementing the FlowEnginePort interface.
"""

import copy
import threading
from typing import Any, Callable, ParamSpec, Protocol, TypeVar, cast

# CRITICAL: Set Prefect env vars BEFORE importing Prefect modules
from docpipe.utils.orchestration.prefect_config import set_prefect_env_variables

set_prefect_env_variables()

from prefect import flow, task  # noqa: E402
from prefect.futures import PrefectFuture  # noqa: E402
from prefect.runtime import task_run  # noqa: E402
from prefect.states import Completed  # noqa: E402
from prefect.task_runners import TaskRunner, ThreadPoolTaskRunner  # noqa: E402

from docpipe.core.constants.constants import DocpipeConstants, ExecutionStatus, TaskType  # noqa: E402
from docpipe.core.constants.operator_constants import OperatorConstants  # noqa: E402
from docpipe.core.incremental_metadata import get_incremental_update_service  # noqa: E402
from docpipe.core.models.session_info import get_session_info  # noqa: E402
from docpipe.core.orchestration.futured_list import FuturedList  # noqa: E402
from docpipe.core.orchestration.ports.flow_engine import ExecuteStepResults, FlowEnginePort  # noqa: E402
from docpipe.core.orchestration.prefect.ports.batch_execution_port import (  # noqa: E402
    BatchExecutionPort,
)
from docpipe.exceptions.docpipe_exceptions import (  # noqa: E402
    ErrorCode,
    FlowExecutionFailedException,
    FlowValidationException,
    PrefectFlowFailed,
)
from docpipe.utils.infrastructure.logging import get_logger  # noqa: E402
from docpipe.utils.orchestration.flow_utils import create_node_id_to_index_map  # noqa: E402

logger = get_logger()

R = TypeVar("R")  # The return type of the user's function
P = ParamSpec("P")


class SupportsSubmit(Protocol):
    """Supportssubmit."""

    def submit(self, *args: Any, **kwargs: Any) -> PrefectFuture: ...


class BatchFuture:
    """Container for batch execution future with metadata."""

    def __init__(self, *, batch_id: str, batch_num: int, future: PrefectFuture):
        self.batch_id = batch_id
        self.batch_num = batch_num
        self.future = future

    def describe_state(self) -> str:
        """Describe state."""
        state_parts: list[str] = []

        try:
            state_parts.append(f"is_completed={self.future.state.is_completed()}")
            state_parts.append(f"is_failed={self.future.state.is_failed()}")
            state_parts.append(f"is_crashed={self.future.state.is_crashed()}")
            state_parts.append(f"is_cancelled={self.future.state.is_cancelled()}")
            state_parts.append(f"state_type={getattr(self.future.state.type, 'value', self.future.state.type)}")
            state_parts.append(f"state_name={getattr(self.future.state, 'name', 'unknown')}")
        except Exception as exc:
            state_parts.append(f"state_unavailable={exc}")

        wrapped_future = getattr(self.future, "_wrapped_future", None)
        if wrapped_future is not None:
            try:
                state_parts.append(f"wrapped_done={wrapped_future.done()}")
                state_parts.append(f"wrapped_cancelled={wrapped_future.cancelled()}")
                state_parts.append(f"wrapped_running={wrapped_future.running()}")
            except Exception as exc:
                state_parts.append(f"wrapped_state_unavailable={exc}")

        return ", ".join(state_parts)


class PrefectEngine(FlowEnginePort):
    """
    Prefect-specific implementation of FlowEnginePort.

    This adapter implements flow execution using Prefect's task orchestration.
    It is responsible for:
    - Building Prefect flows with appropriate configuration
    - Creating and managing Prefect tasks
    - Executing flows with proper task orchestration
    - Managing batch execution with parallelism control
    """

    def __init__(self, *, orchestrator, batch_manager, job_id: str, job_run_id: str, job_log_path: str):
        super().__init__(
            orchestrator=orchestrator,
            batch_manager=batch_manager,
            job_id=job_id,
            job_run_id=job_run_id,
            job_log_path=job_log_path,
        )
        self.logger = get_logger()
        self.common_log_arguments = {
            DocpipeConstants.JOB_ID: self.job_id,
            DocpipeConstants.JOB_RUN_ID: self.job_run_id,
        }

    def execute_batch_flow(self, *, op_flow, batches, global_config):
        """
        Execute batches using configured strategy (ThreadPool or WorkPool).

        Strategy is selected based on global_config.prefect.batch_execution.strategy:
        - "thread-pool" (default): Local execution using ThreadPoolTaskRunner
        - "work-pool-*": Distributed execution via Prefect work pools

        The strategy pattern enables seamless switching between local and distributed
        execution without changing the orchestrator code.
        """
        from docpipe.core.orchestration.prefect.adapters.factories.batch_execution_factory import BatchExecutionFactory

        # Create appropriate strategy based on configuration
        strategy: BatchExecutionPort = BatchExecutionFactory.create_strategy(
            config=global_config, prefect_engine=self, batch_manager=self.batch_manager
        )

        # Execute batches using the selected strategy
        strategy.execute_batches(
            batches=batches,
            op_flow=op_flow[1:],  # Skip ingest operator
            global_config=global_config,
            job_run_id=self.job_run_id,
        )

    def execute_non_execute_flow(self, *, flow_name: str, task: Any, dag: Any):
        """Execute non execute flow."""
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
            task_runner=cast(
                "TaskRunner[PrefectFuture[Any]]", ThreadPoolTaskRunner(max_workers=prefect_config["max_workers"])
            ),
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
            task_runner=cast(
                "TaskRunner[PrefectFuture[Any]]", ThreadPoolTaskRunner(max_workers=prefect_config["max_workers"])
            ),
        )(self.__non_execute_inner_flow)

    def batch_outer_flow_impl(self, op_flow, batches, global_config) -> list[BatchFuture]:
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
            DocpipeConstants.MAX_CONCURRENT_BATCHES,
            DocpipeConstants.DEFAULT_MAX_CONCURRENT_BATCHES,
        )
        if not isinstance(max_concurrent_batches, int) or max_concurrent_batches <= 0:
            raise FlowExecutionFailedException(
                f"{DocpipeConstants.MAX_CONCURRENT_BATCHES} must be a positive integer, got {max_concurrent_batches!r}"
            )

        self.batch_manager.initialize_batch_semaphore(max_concurrent_batches=max_concurrent_batches)

        # 1. Build the inner flow to execute a batch once (reusable for all batches)
        inner_flow = self._build_flow(name="batch_sub_flow", flow_impl=self.__flow_impl)

        # Create a task wrapper for subflow execution
        def batch_cache_key_fn(context, parameters):
            """Custom cache key that excludes batch_data_access to avoid serialization errors."""
            return f"{parameters.get('batch_id')}_{self.job_run_id}"

        # 2. Define a task to execute inner flow
        @task(cache_key_fn=batch_cache_key_fn)
        def batch_subflow_task(batch_id, batch_num, op_flow, global_config, batch_data_access):
            """Execute a single batch as a Prefect subflow."""
            batch_semaphore = self.batch_manager.get_batch_semaphore()

            # Acquire batch semaphore before batch execution
            if batch_semaphore:
                batch_semaphore.acquire()
                self.logger.info(
                    f"Batch {batch_num} (ID: {batch_id}): acquired batch semaphore slot",
                    extra=self.common_log_arguments,
                )

            try:
                self.logger.info(
                    f"Batch {batch_num} (ID: {batch_id}): starting execution", extra=self.common_log_arguments
                )
                from docpipe.core.constants.operator_constants import OperatorConstants

                self.logger.debug(
                    f"Batch {batch_num}: global_config has ingest_source={OperatorConstants.Config.INGEST_SOURCE in global_config}",
                    extra=self.common_log_arguments,
                )
                batch_global_config = global_config.copy()
                self.logger.debug(
                    f"Batch {batch_num}: batch_global_config (after copy) has ingest_source={OperatorConstants.Config.INGEST_SOURCE in batch_global_config}",
                    extra=self.common_log_arguments,
                )
                if global_config.get(DocpipeConstants.ENABLE_MICRO_BATCHING, False):
                    batch_global_config[DocpipeConstants.BATCH_NUM] = batch_num
                    batch_global_config[DocpipeConstants.BATCH_ID] = batch_id

                flow_def = global_config.get(DocpipeConstants.FLOW_DEFINITION, {})
                flow_name = flow_def.get(DocpipeConstants.FLOW_NAME) or flow_def.get(
                    DocpipeConstants.NAME, "docpipe_flow"
                )
                run_name = f"{flow_name}_batch_{batch_num}"
                result = inner_flow.with_options(flow_run_name=run_name)(
                    op_flow=op_flow,
                    data_access=batch_data_access,
                    global_config=batch_global_config,
                )
                self.logger.info(
                    f"Batch {batch_num} (ID: {batch_id}): completed execution", extra=self.common_log_arguments
                )
                return result
            finally:
                # Release batch semaphore in finally block to ensure cleanup
                if batch_semaphore:
                    batch_semaphore.release()
                    self.logger.info(
                        f"Batch {batch_num} (ID: {batch_id}): released batch semaphore slot",
                        extra=self.common_log_arguments,
                    )

        # Submit all batches as tasks
        batch_futures: list[BatchFuture] = []

        for batch_info in batches:
            batch_data_access = self.batch_manager.create_batch_data_access(batch_table=batch_info.table)

            flow_def = global_config.get(DocpipeConstants.FLOW_DEFINITION, {})
            flow_name = flow_def.get(DocpipeConstants.FLOW_NAME) or flow_def.get(DocpipeConstants.NAME, "docpipe_flow")
            run_name = f"{flow_name}_batch_{batch_info.batch_num}"
            # 3. Submit task that executes sub flow for each batch
            future = batch_subflow_task.with_options(task_run_name=run_name).submit(
                batch_id=batch_info.batch_id,
                batch_num=batch_info.batch_num,
                op_flow=op_flow,
                global_config=global_config,
                batch_data_access=batch_data_access,
            )
            batch_future = BatchFuture(batch_id=batch_info.batch_id, batch_num=batch_info.batch_num, future=future)
            batch_futures.append(batch_future)
            self.logger.info(
                f"Submitted batch {batch_future.batch_num} (ID: {batch_future.batch_id}) future: {batch_future.describe_state()}",
                extra=self.common_log_arguments,
            )

        # IMPORTANT: Wait for all batch futures INSIDE the outer flow.
        # When the @flow function returns, Prefect exits its run_context which
        # calls ThreadPoolTaskRunner.__exit__ → cancel_all() → executor.shutdown(cancel_futures=True).
        # Any tasks still running at that point get cancelled with CancelledError → Crashed state.
        # By resolving all futures here, we ensure the ThreadPoolTaskRunner is still active.
        self._wait_for_sub_flows(batch_futures=batch_futures, global_config=global_config)

        return batch_futures

    def _wait_for_sub_flows(self, *, batch_futures: list[BatchFuture], global_config: dict):
        """
        Wait for all sub-flows (batches) to complete with fail-fast cancellation.

        Behavior is controlled by the continue_on_batch_failure flag:
        - False (default): Fail-fast - cancel remaining batches on first failure
        - True: Continue execution - allow all batches to complete even if some fail,
                but raise exception if ALL batches fail

        Note: This method does not return batch results to avoid loading all PyArrow tables
        into memory. Each sub-flow saves its metadata incrementally.
        """
        continue_on_batch_failure = global_config.get(
            DocpipeConstants.CONTINUE_ON_BATCH_FAILURE,
            DocpipeConstants.CONTINUE_ON_BATCH_FAILURE_DEFAULT,
        )

        failed_batch = None
        cancellation_event = threading.Event()
        cancelled_batch_futures: list[BatchFuture] = []
        failed_batch_nums: list[int] = []

        try:
            for future_index, batch_future in enumerate(batch_futures):
                self.logger.info(
                    f"Resolving batch {batch_future.batch_num} (ID: {batch_future.batch_id}) future before result(): {batch_future.describe_state()}",
                    extra=self.common_log_arguments,
                )

                # Check if another batch already failed (only in fail-fast mode)
                if cancellation_event.is_set():
                    try:
                        # PrefectFuture.cancel() exists at runtime in Prefect 2.x
                        cancel_result = batch_future.future.cancel()  # type: ignore[attr-defined]
                        cancelled_batch_futures.append(batch_future)
                        self.logger.info(
                            f"Cancelled batch {batch_future.batch_num} (ID: {batch_future.batch_id}) due to failure in batch {failed_batch}; cancel_result={cancel_result}; state_after_cancel={batch_future.describe_state()}",
                            extra=self.common_log_arguments,
                        )
                    except Exception as cancel_error:
                        self.logger.warning(
                            f"Could not cancel batch {batch_future.batch_num} (ID: {batch_future.batch_id}): {cancel_error}; state_on_cancel_error={batch_future.describe_state()}",
                            extra=self.common_log_arguments,
                        )
                    continue

                try:
                    batch_future.future.result()
                    self.logger.info(
                        f"Batch {batch_future.batch_num} (ID: {batch_future.batch_id}) completed successfully; state_after_result={batch_future.describe_state()}",
                        extra=self.common_log_arguments,
                    )

                except Exception as e:
                    if continue_on_batch_failure:
                        # Track failed batch and continue
                        failed_batch_nums.append(batch_future.batch_num)
                        self.logger.warning(
                            f"Batch {batch_future.batch_num} failed but continuing with remaining batches due to continue_on_batch_failure=True: {e}",
                            extra=self.common_log_arguments,
                        )
                        continue

                    # Fail-fast mode: Batch failed - trigger cancellation
                    failed_batch = batch_future.batch_num
                    cancellation_event.set()

                    self.logger.error(
                        f"Batch {batch_future.batch_num} (ID: {batch_future.batch_id}) failed in future.result(); exception_type={type(e).__name__}; exception={e}; state_on_failure={batch_future.describe_state()}; cancelling all remaining batches",
                        extra=self.common_log_arguments,
                        exc_info=True,
                    )

                    for remaining_batch_future in batch_futures[future_index + 1 :]:
                        try:
                            # PrefectFuture.cancel() exists at runtime in Prefect 2.x
                            cancel_result = remaining_batch_future.future.cancel()  # type: ignore[attr-defined]
                            cancelled_batch_futures.append(remaining_batch_future)
                            self.logger.info(
                                f"Cancelled batch {remaining_batch_future.batch_num} (ID: {remaining_batch_future.batch_id}); cancel_result={cancel_result}; state_after_cancel={remaining_batch_future.describe_state()}",
                                extra=self.common_log_arguments,
                            )
                        except Exception as cancel_error:
                            self.logger.warning(
                                f"Could not cancel batch {remaining_batch_future.batch_num} (ID: {remaining_batch_future.batch_id}): {cancel_error}; state_on_cancel_error={remaining_batch_future.describe_state()}",
                                extra=self.common_log_arguments,
                            )

                    # Re-raise the exception to fail the entire job
                    raise FlowExecutionFailedException(
                        f"Batch {batch_future.batch_num} (ID: {batch_future.batch_id}) failed during sub-flow execution: {type(e).__name__}: {e}"
                    ) from e

            # After all batches complete, check failure scenarios in continue_on_batch_failure mode
            if continue_on_batch_failure and failed_batch_nums:
                if len(failed_batch_nums) == len(batch_futures):
                    # All batches failed - set job status to FAILING
                    # after_flow_execution_complete will convert FAILING → FAILED
                    self.orchestrator.job_status = ExecutionStatus.FAILING
                    self.orchestrator.message = f"All {len(batch_futures)} batches failed: {failed_batch_nums}"
                    self.logger.error(
                        f"All {len(batch_futures)} batches failed: {failed_batch_nums}",
                        extra=self.common_log_arguments,
                    )
                else:
                    # Some batches failed but not all - log warning
                    # Status will be determined by after_flow_execution_complete based on node stats
                    self.logger.warning(
                        f"Partial batch failure: {len(failed_batch_nums)} out of {len(batch_futures)} batches failed: {failed_batch_nums}",
                        extra=self.common_log_arguments,
                    )
        finally:
            for cancelled_batch_future in cancelled_batch_futures:
                try:
                    cancelled_batch_future.future.wait()
                    self.logger.info(
                        f"Cancelled batch {cancelled_batch_future.batch_num} (ID: {cancelled_batch_future.batch_id}) reached terminal state before semaphore reset",
                        extra=self.common_log_arguments,
                    )
                except Exception as wait_error:
                    self.logger.warning(
                        f"Error while waiting for cancelled batch {cancelled_batch_future.batch_num} (ID: {cancelled_batch_future.batch_id}) to finish: {wait_error}",
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

    def __create_task(
        self,
        *,
        task_func: Callable[..., Any],
        retries: int = 0,
        persist_result: bool = False,
    ) -> SupportsSubmit:
        """Create a Prefect task for operator execution."""

        def generate_task_name():
            """Generate task name."""
            parameters = task_run.parameters
            return parameters["op_def"]["name"]

        return task(
            task_run_name=generate_task_name,
            retries=retries,
            persist_result=persist_result,
        )(task_func)

    def __create_main_task(
        self,
        main_task: Callable[..., Any],
        retries: int = 0,
        persist_result: bool = False,
    ) -> SupportsSubmit:
        """Create a Prefect task for non-execution flows."""

        def generate_task_name():
            """Generate task name."""
            parameters = task_run.parameters
            return parameters["task_name"]

        return task(
            task_run_name=generate_task_name,
            retries=retries,
            persist_result=persist_result,
        )(main_task)

    def execute_operator_flow(self, *, op_flow, data_access, global_config):
        """
        Public method to execute operator flow - used by batch workers.

        This is the entry point for distributed batch workers to execute
        operator flows using the same logic as local execution.

        Args:
            op_flow: List of operator definitions
            data_access: DataAccess object containing batch data
            global_config: Global configuration dictionary
        """
        return self.__flow_impl(op_flow=op_flow, data_access=data_access, global_config=global_config)

    def __flow_impl(self, op_flow, data_access, global_config):
        """
        Execute the inner flow with Prefect task orchestration.

        This method builds and executes a DAG of operators using Prefect tasks,
        handling dependencies and parallelism automatically.
        """
        # In batch mode, get the ingest operator ID from global_config
        ingest_node_id = global_config.get(DocpipeConstants.INGEST_NODE_ID)
        batch_num = global_config.get(DocpipeConstants.BATCH_NUM)

        self.logger.info(
            f"inner_flow: batch_num={batch_num}, ingest_node_id={ingest_node_id}, op_flow_length={len(op_flow)}",
            extra=self.common_log_arguments,
        )

        def get_prev_results(
            op_definitions, results_: FuturedList, initial_batch_result
        ) -> PrefectFuture | dict[str, PrefectFuture]:
            """Get prev results."""
            prev_res: dict[str, PrefectFuture] = {}
            has_ingest_dependency = False

            for prev_node in op_definitions.get(DocpipeConstants.INPUT_EDGES, []):
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
                    self.logger.error(
                        f"Node {node_id_ref} not found in flow. ingest_node_id={ingest_node_id}",
                        extra=self.common_log_arguments,
                    )
                    raise FlowExecutionFailedException(f"Node {node_id_ref} not found in flow")

                prev_index = node_id_to_index_map[node_id_ref]
                prev_res[prev_node.get(DocpipeConstants.LINK_NAME)] = results_.get_future(prev_index)

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

        # Handle ingest-only flows (no downstream operators)
        if not op_flow:
            self.logger.info(
                "Ingest-only flow detected - no downstream operators to process. "
                "Returning ingested data without further processing.",
                extra=self.common_log_arguments,
            )
            # Create initial batch result with ingested data
            batch_table = data_access.get_table("")[0]
            return ExecuteStepResults([data_access], [batch_table], {})

        results: FuturedList = FuturedList.from_size(len(op_flow))
        destinations: list[tuple[PrefectFuture, Any]] = []
        node_id_to_index_map = create_node_id_to_index_map(flow_def=op_flow)
        deleted_docs_count = 0
        incremental_update_util = get_incremental_update_service()

        is_sequential_flow = (
            False
            if op_flow[0].get(DocpipeConstants.INPUT_EDGES) or op_flow[0].get(DocpipeConstants.OUTPUT_EDGES)
            else True
        )
        prev_index = None

        # Create initial batch result for first operator after ingest
        batch_table = data_access.get_table("")[0]
        initial_batch_result = ExecuteStepResults([data_access], [batch_table], {})

        for op_def in op_flow:
            # In fail-fast mode, stop submitting new tasks if a failure has occurred
            if self.orchestrator.job_status == ExecutionStatus.FAILING:
                # Skip remaining operators - they will be recorded as skipped by _inner_task
                continue

            index = node_id_to_index_map[op_def[OperatorConstants.Columns.ID]]
            try:
                link_id = op_def.get(OperatorConstants.Misc.LINK_ID, None)
                if prev_index is None:
                    prev_results = initial_batch_result
                else:
                    prev_results = (
                        results.get_future(prev_index)
                        if is_sequential_flow
                        else get_prev_results(op_def, results, initial_batch_result)
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
                    if not op_def.get(DocpipeConstants.OUTPUT_EDGES):
                        destinations.append((future, op_def))
                    else:
                        results.set_entry(index, future, len(op_def.get(DocpipeConstants.OUTPUT_EDGES)))
                prev_index = index
            except Exception as e:
                self.orchestrator._handle_node_failure(e=e, op_def=op_def, global_config=global_config)

        self.__wait_for_tasks(destinations=destinations)

        # Check if batch failed in fail-fast mode and raise exception immediately
        # This prevents unnecessary result collection and metadata saving
        # Exception is caught by _wait_for_sub_flows() which cancels remaining batches
        continue_on_batch_failure = global_config.get(
            DocpipeConstants.CONTINUE_ON_BATCH_FAILURE, DocpipeConstants.CONTINUE_ON_BATCH_FAILURE_DEFAULT
        )
        if self.orchestrator.job_status == ExecutionStatus.FAILING and not continue_on_batch_failure:
            batch_num = global_config.get(DocpipeConstants.BATCH_NUM, "unknown")
            micro_batching_enabled = global_config.get(DocpipeConstants.ENABLE_MICRO_BATCHING, False)
            raise FlowExecutionFailedException(
                f"Batch {batch_num}: One or more operators failed "
                f"(micro_batching_enabled={micro_batching_enabled}, continue_on_batch_failure={continue_on_batch_failure})"
            )

        # Only collect results and save metadata if batch succeeded
        failed_doc_ids = self._collect_failed_doc_ids()

        tables = [
            destination[0].result().tables[0]
            for destination in destinations
            if hasattr(destination[0], "result")
            and destination[0].result()
            and hasattr(destination[0].result(), "tables")
        ]

        # Get merged non-recoverable docs table from orchestrator
        non_recoverable_docs_table = self.orchestrator._merge_non_recoverable_docs(
            global_config=global_config, common_log_arguments=self.common_log_arguments
        )

        incremental_update_util.save_metadata_for_incremental_update(
            job_id=self.orchestrator.context_id,
            job_run_id=self.job_run_id,
            tables=tables,
            failed_doc_ids=failed_doc_ids,
            non_recoverable_docs_table=non_recoverable_docs_table,
        )

        # Reset non-recoverable docs for micro-batching support
        self.orchestrator._reset_non_recoverable_docs_for_batch(
            global_config=global_config, common_log_arguments=self.common_log_arguments
        )
        return None

    def __non_execute_inner_flow(
        self,
        task_type: TaskType,
        inner_task: Any,
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

                if not op_def.get(DocpipeConstants.OUTPUT_EDGES):
                    destinations.append((future, op_def))
                else:
                    results.set_entry(index, future, len(op_def.get(DocpipeConstants.OUTPUT_EDGES)))

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
        return None

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

        # Get job stats service from orchestrator
        job_stats_service = self.orchestrator.job_stats_service
        if not job_stats_service:
            logger.warning("Job stats service not available")
            return []

        job_stats = job_stats_service.get_job(job_run_id=self.job_run_id, include_node_stats=True)
        if not job_stats or not job_stats.node_stats:
            self.logger.warning(
                f"Job stats not available for job_run_id={self.job_run_id}, cannot collect failed doc IDs",
                extra=self.common_log_arguments,
            )
            return []

        failed_doc_ids: list[str] = []
        for node_stats in job_stats.node_stats.values():
            if hasattr(node_stats, "failed_docs") and node_stats.failed_docs:
                failed_doc_ids.extend(node_stats.failed_docs)
            elif isinstance(node_stats, dict) and node_stats.get("failed_docs"):
                failed_doc_ids.extend(node_stats["failed_docs"])
        return failed_doc_ids
