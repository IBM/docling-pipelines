from abc import ABC, abstractmethod
from typing import Any


class AbstractFlowExecutionEventHandler(ABC):
    """
    This abstract class provides methods that handles events triggered while flow is executed.
    """

    @abstractmethod
    def before_flow_execution_start(self, *, orchestrator, flow_def: dict | None = None):
        pass

    @abstractmethod
    def after_flow_execution_complete(self, op_flow, present_job_status: str, message):
        pass

    @abstractmethod
    def before_step_execution_start(self, *, node_id, node_name, global_config, job_status, prev_results):
        pass

    @abstractmethod
    def after_step_execution_complete(
        self,
        *,
        node_id,
        node_name,
        operator_category,
        operator,
        global_config,
        is_last_step,
        metadata,
        start_time,
        tables=None,
    ):
        pass

    @abstractmethod
    def after_node_skipped(
        self,
        *,
        node_id,
        node_name,
        operator_type,
        global_config,
        start_time,
        end_time,
        column_names,
        reason: str | None = None,
    ):
        """
        Record node as SKIPPED.

        Args:
            node_id: Node identifier
            node_name: Human-readable node name
            operator_type: Operator type
            global_config: Global configuration containing batch context
            start_time: Start timestamp
            end_time: End timestamp
            column_names: Column names from node output
            reason: Optional reason for skipping (defaults to "Skipped - no input data to process")
        """
        pass

    @abstractmethod
    def after_node_failure(self, *, node_id, node_name, global_config, e):
        pass

    @abstractmethod
    def after_batches_prepared(
        self, *, batches: list[Any], op_flow: list[dict[str, Any]], global_config: dict[str, Any]
    ) -> None:
        """
        Initialize pending batch node stats after batches are materialized.

        Creates PENDING stats for all batch/node combinations for downstream
        batch-participating nodes (excludes ingest operator).

        Args:
            batches: List of BatchInfo objects with batch_id, batch_num, and table
            op_flow: Operator flow definition (DAG)
            global_config: Global configuration dictionary
        """
        pass
