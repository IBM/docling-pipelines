import os

from common.constants import DatasiftConstants, ExecutionStatus
from common.exceptions.error_codes import ErrorCode
from common.models.session_info import get_session_info
from common.util import get_data_path, get_logger, log_elapsed_time
from common.util.job_tracker.tracker.job_tracker import JobTracker
from core.operators.operator_utils import OperatorUtils
from core.orchestrator.abstract_flow_execution_event_handler import AbstractFlowExecutionEventHandler
from core.orchestrator.node_logger import NodeLogger

logger = get_logger()


class OpenSourceFlowExecutionEventHandler(AbstractFlowExecutionEventHandler):
    """
    This class implement the methods that handles events triggered while flow is executed in open source version.
    """
    def __init__(self):
        self.job_tracker = JobTracker()
        self.node_logger: NodeLogger | None = None

    def initialize(self, *, job_id, job_run_id, common_log_arguments):
        self.flow_id = get_session_info().flow_id
        self.job_id = job_id
        self.job_run_id = job_run_id
        self.job_log_path = self._create_log_folders(job_id=self.job_id, type_="job")
        self.common_log_arguments = common_log_arguments
        self.node_logger = NodeLogger(common_log_arguments=self.common_log_arguments)

    def before_flow_execution_start(self, *, orchestrtor):
        if self.job_tracker.cancel_job_run_if_cancelling(job_run_id=self.job_run_id, job_log_path=self.job_log_path):
            return
        self.job_tracker.start_tracking_job(orchestrator=orchestrtor, job_id=self.job_id, job_run_id=self.job_run_id)

    def after_flow_execution_complete(self, op_flow, present_job_status: str, message):
        if present_job_status == ExecutionStatus.CANCELING:
            job_status = ExecutionStatus.CANCELED
        elif present_job_status == ExecutionStatus.FAILING:
            job_status = ExecutionStatus.FAILED
        else:
            job_stats = self.job_tracker.get_job(job_run_id=self.job_run_id)
            self.job_tracker.determine_and_update_final_documents_count(job_stats=job_stats, dag_nodes=op_flow)
            job_status = OperatorUtils.determine_final_job_status(node_stats_list=job_stats.node_stats)
            job_stats.status = job_status

        self.job_tracker.end_job(
            job_run_id=self.job_run_id, status=job_status, message=message, job_log_path=self.job_log_path
        )
        logger.info(f">>> Job status is {job_status}.", extra=self.common_log_arguments)

    def before_step_execution_start(self, *, node_id, node_name, global_config, job_status, prev_results):
        if prev_results is None:
            if self.node_logger:
                self.node_logger.log_error_in_previous_step(
                    node_id=node_id,
                    node_name=node_name,
                    global_config=global_config
                )
        self.node_logger.log_cancellation_or_abort_if_needed(
                    node_id=node_id,
                    node_name=node_name,
                    job_status=job_status,
                    global_config=global_config
                )

    def after_step_execution_complete(self, *, node_id, node_name, operator_category, operator, global_config, is_last_step, metadata, start_time):
        """
        This method is called after a step is executed or skipped
        """
        self.job_tracker.update_doc_counts(
            job_run_id=self.job_run_id,
            metadata=metadata,
            operator_category=operator_category
        )
        log_elapsed_time(start_time=start_time, operator=operator)

        if is_last_step:
            self.node_logger.log_branch_completion(node_id=node_id, node_name=node_name, global_config=global_config)

    def after_node_skipped(self, *, node_id, node_name, operator, global_config, start_time, end_time, column_names):
        node_stats = {
            "name": node_name,
            "node_status": ExecutionStatus.SKIPPED.value,
            "start_time": start_time,
            "end_time": end_time,
            "col_names": column_names,
            "time_taken": end_time - start_time,
        }

        if self.node_logger:
            self.node_logger.log_skipped_execution(
                node_id=node_id, node_name=node_name, operator=operator, global_config=global_config
            )

        self.job_tracker.update_node_stats(self.job_run_id, node_id=node_id, node_stats=node_stats)

    def after_node_failure(self, *, node_id, node_name, global_config, e):
        node_stats = {
            "name": node_name,
            "node_status": ExecutionStatus.FAILED.value,
            "error": str(e),
            "error_code": ErrorCode.OPERATOR_EXECUTION_FAILED.value
        }
        self.job_tracker.update_node_stats(
            job_run_id=self.job_run_id,
            node_id=node_id,
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
                node_id=node_id,
                node_name=node_name,
                error=e,
                global_config=global_config
            )

    def _create_log_folders(self, *, job_id, type_):
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
