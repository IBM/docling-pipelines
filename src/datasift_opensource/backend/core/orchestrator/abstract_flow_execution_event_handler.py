from abc import ABC, abstractmethod


class AbstractFlowExecutionEventHandler(ABC):
    """
    This abstract class provides methods that handles events triggered while flow is executed.
    """

    @abstractmethod
    def before_flow_execution_start(self, *, orchestrtor):
        pass

    @abstractmethod
    def after_flow_execution_complete(self, op_flow, present_job_status: str, message):
        pass

    @staticmethod
    def before_step_execution_start(self, *, node_id, node_name, global_config, job_status, prev_results):
        pass

    @abstractmethod
    def after_step_execution_complete(
        self, *, node_id, node_name, operator_category, operator, global_config, is_last_step, metadata, start_time
    ):
        pass

    @abstractmethod
    def after_node_skipped(
        self, *, node_id, node_name, operator_type, global_config, start_time, end_time, column_names
    ):
        pass

    @abstractmethod
    def after_node_failure(self, *, node_id, node_name, global_config, e):
        pass
