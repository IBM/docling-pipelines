"""
ThreadPoolAdapter - Local batch execution using ThreadPoolTaskRunner.

This adapter wraps the existing PrefectEngine batch execution logic,
maintaining backward compatibility while following the strategy pattern.
"""

from docpipe.core.constants.constants import ExecutionStatus
from docpipe.core.orchestration.batch_manager import BatchInfo
from docpipe.core.orchestration.prefect.domain.models import ExecutionStrategyType
from docpipe.core.orchestration.prefect.ports.batch_execution_port import BatchExecutionPort
from docpipe.exceptions.docpipe_exceptions import FlowExecutionFailedException


class ThreadPoolAdapter(BatchExecutionPort):
    """
    Adapter: Local batch execution using Prefect's ThreadPoolTaskRunner.

    This strategy executes batches locally in the same process using threads.
    It wraps the existing PrefectEngine implementation without modification.

    Characteristics:
    - Synchronous: Blocks until all batches complete
    - Local: All batches run in same process
    - Thread-based: Uses ThreadPoolTaskRunner for parallelism
    - Fail-fast: First failure cancels remaining batches
    - No network dependency: Works without Prefect Server

    Use Cases:
    - Local development and testing
    - Single-machine deployments
    - When distributed execution is not needed
    - Default execution mode (backward compatible)
    """

    def __init__(self, *, prefect_engine, batch_manager):
        """
        Initialize ThreadPool adapter.

        Args:
            prefect_engine: PrefectEngine instance (for accessing existing methods)
            batch_manager: BatchManager instance (for batch operations)
        """
        self.prefect_engine = prefect_engine
        self.batch_manager = batch_manager

    def execute_batches(
        self, *, batches: list[BatchInfo], op_flow: list[dict], global_config: dict, job_run_id: str
    ) -> None:
        """
        Execute batches using thread pool (current implementation).

        This delegates to the existing PrefectEngine methods:
        1. batch_outer_flow_impl() - Submits batches as Prefect tasks
        2. _wait_for_sub_flows() - Waits for completion with fail-fast

        The failure raise happens here, after the outer flow returns — see below.
        """
        self.prefect_engine.logger.info(
            f"Executing {len(batches)} batches using ThreadPool strategy", extra={"job_run_id": job_run_id}
        )

        from docpipe.core.constants.constants import DocpipeConstants

        flow_def = global_config.get(DocpipeConstants.FLOW_DEFINITION, {})
        flow_name = flow_def.get(DocpipeConstants.FLOW_NAME) or flow_def.get(DocpipeConstants.NAME, "docpipe_flow")

        # Build the batch outer flow (wraps batch_outer_flow_impl with @flow decorator)
        batch_outer_flow = self.prefect_engine._build_flow(
            name=flow_name, flow_impl=self.prefect_engine.batch_outer_flow_impl
        )

        # Execute the flow (which now waits for all batches internally to keep the task runner alive)
        batch_outer_flow.with_options(flow_run_name=flow_name)(
            op_flow=op_flow, batches=batches, global_config=global_config
        )

        # Raise here, not inside _wait_for_sub_flows. By this point the flow has
        # returned and ThreadPoolTaskRunner.__exit__ has already run, so raising
        # cannot strand live batch threads in executor.shutdown(wait=True).
        #
        # The CLI and DocpipeFlowManager have no other way to see the failure.
        # The API path reads job stats instead and ignores this exception.
        # Only raise when FAILING — a partial continue-mode failure must not raise,
        # or the API path overwrites COMPLETED_WITH_ERRORS with FAILED.
        if self.prefect_engine.orchestrator.job_status == ExecutionStatus.FAILING:
            raise FlowExecutionFailedException(self.prefect_engine.orchestrator.message or "Batch execution failed")

        self.prefect_engine.logger.info("All batches completed successfully", extra={"job_run_id": job_run_id})

    def get_strategy_name(self) -> str:
        """Return strategy name for logging."""
        return ExecutionStrategyType.THREAD_POOL.value
