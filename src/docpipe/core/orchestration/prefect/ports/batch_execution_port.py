"""
Port (Interface) for batch execution strategies.

This defines the contract that all batch execution strategies must implement.
Following hexagonal architecture, this port is internal to PrefectEngine and
is NOT exposed to the domain layer (Orchestrator).
"""

from abc import ABC, abstractmethod

from docpipe.core.orchestration.batch_manager import BatchInfo


class BatchExecutionPort(ABC):
    """
    Abstract interface for batch execution strategies.

    This port defines how batches should be executed, but not the implementation details.
    Different adapters (ThreadPoolAdapter, WorkPoolAdapter) provide concrete implementations.

    Design Principles:
    - Port is INTERNAL to PrefectEngine (not exposed to domain layer)
    - Domain layer (Orchestrator) remains unaware of execution strategies
    - Strategies encapsulate ALL Prefect-specific details
    - Clean separation between local and distributed execution

    Implementations:
    - ThreadPoolAdapter: Local execution using ThreadPoolTaskRunner
    - WorkPoolAdapter: Distributed execution via Prefect work pools
    """

    @abstractmethod
    def execute_batches(
        self, *, batches: list[BatchInfo], op_flow: list[dict], global_config: dict, job_run_id: str
    ) -> None:
        """
        Execute batches using the strategy's execution model.

        This method is responsible for:
        1. Submitting batches for execution (local or distributed)
        2. Waiting for all batches to complete
        3. Handling failures with fail-fast cancellation
        4. Logging execution progress

        Args:
            batches: List of BatchInfo objects with batch_id, batch_num, and table
            op_flow: Operator flow definition (list of operator configs)
            global_config: Global configuration dict
            job_run_id: Unique identifier for this job run (for logging)

        Raises:
            FlowExecutionFailedException: If any batch fails during execution

        Note:
            This method does NOT return batch results to avoid loading all
            PyArrow tables into memory. Each batch saves its metadata incrementally.
        """
        pass

    @abstractmethod
    def get_strategy_name(self) -> str:
        """
        Return human-readable strategy name for logging.

        Examples:
            - "ThreadPool"
            - "WorkPool-process"
            - "WorkPool-docker"

        Returns:
            Strategy name string
        """
        pass
