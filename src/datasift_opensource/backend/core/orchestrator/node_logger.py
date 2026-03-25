"""
Node Logger Module

Handles node-specific logging functionality for orchestrator operations.
Extracted from AbstractOrchestrator to improve separation of concerns.
"""

import os

from common.constants.constants import DatasiftConstants
from common.constants.operator_constants import OperatorConstants
from common.util.log import get_logger
from common.models.session_info import get_session_info


class NodeLogger:
    """
    Manages node-specific logging operations for orchestrator workflows.
    
    This class encapsulates all node logger creation and logging operations
    that were previously scattered in AbstractOrchestrator.
    """
    
    def __init__(self, common_log_arguments: dict | None = None):
        """
        Initialize NodeLogger.
        
        Args:
            common_log_arguments: Common logging arguments (job_id, job_run_id)
        """
        self.common_log_arguments = common_log_arguments or {}
    
    def get_node_logger(self, *, node_id: str, node_name: str, global_config: dict):
        """
        Create and return a node-specific logger.
        
        Args:
            node_id: Unique identifier for the node
            node_name: Human-readable name of the node
            global_config: Global configuration containing job_id and job_run_id
            
        Returns:
            Logger instance configured for the specific node
        """
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
    
    def log_node_failure(
        self,
        *,
        node_id: str,
        node_name: str,
        error: Exception,
        global_config: dict
    ):
        """
        Log node failure with detailed error information.
        
        Args:
            node_id: Unique identifier for the failed node
            node_name: Human-readable name of the failed node
            error: Exception that caused the failure
            global_config: Global configuration containing job_id and job_run_id
        """
        node_logger = self.get_node_logger(
            node_id=node_id,
            node_name=node_name,
            global_config=global_config,
        )
        node_logger.error(
            ">>> Node %s failed and caused aborting the branch execution: %s transaction_ID: %s",
            node_name,
            error,
            get_session_info().transaction_id,
            extra=self.common_log_arguments
        )
    
    def log_skipped_execution(
        self,
        *,
        node_id: str,
        node_name: str,
        operator_type: str,
        global_config: dict
    ):
        """
        Log when a node execution is skipped due to no input data.
        
        Args:
            node_id: Unique identifier for the skipped node
            node_name: Human-readable name of the skipped node
            operator_type: Type of operator being skipped
            global_config: Global configuration containing job_id and job_run_id
        """
        op_logger = self.get_node_logger(
            node_id=node_id,
            node_name=node_name,
            global_config=global_config
        )
        op_logger.info(
            ">>> ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~",
            extra=self.common_log_arguments,
        )
        application_id: str = f" ApplicationId:{os.getenv('JOB_ID')}" if os.getenv("JOB_ID") else ""
        op_logger.info(f"Orchestrator Type: {str(get_session_info().orchestrator).upper()}{application_id}")
        op_logger.info("Step ID: %s", node_id, extra=self.common_log_arguments)
        op_logger.info(
            ">>> Skipped execution for Step Name: %s, operator: %s because no input data available for processing.",
            node_name,
            operator_type,
            extra=self.common_log_arguments,
        )
        op_logger.info(
            ">>> ================================================================",
            extra=self.common_log_arguments,
        )
    
    def log_error_in_previous_step(
        self,
        *,
        node_id: str,
        node_name: str,
        global_config: dict
    ):
        """
        Log when a node is skipped due to error in previous step.
        
        Args:
            node_id: Unique identifier for the node
            node_name: Human-readable name of the node
            global_config: Global configuration containing job_id and job_run_id
        """
        node_logger = self.get_node_logger(
            node_id=node_id,
            node_name=node_name,
            global_config=global_config
        )
        node_logger.info(
            ">>> Error detected in previous step — node %s skipped. ",
            node_name,
            extra=self.common_log_arguments
        )
    
    def log_cancellation_or_abort(
        self,
        *,
        node_id: str,
        node_name: str,
        is_cancelling: bool,
        global_config: dict
    ):
        """
        Log when execution is cancelled or aborted at a node.
        
        Args:
            node_id: Unique identifier for the node
            node_name: Human-readable name of the node
            is_cancelling: True if cancelling, False if aborting
            global_config: Global configuration containing job_id and job_run_id
        """
        msg = "Cancelling" if is_cancelling else "Aborting"
        node_logger = self.get_node_logger(
            node_id=node_id,
            node_name=node_name,
            global_config=global_config
        )
        node_logger.info(
            ">>> %s the branch execution at node name: %s ",
            msg,
            node_name,
            extra=self.common_log_arguments
        )
    
    def log_branch_completion(
        self,
        *,
        node_id: str,
        node_name: str,
        global_config: dict
    ):
        """
        Log when branch execution completes at a node.
        
        Args:
            node_id: Unique identifier for the node
            node_name: Human-readable name of the node
            global_config: Global configuration containing job_id and job_run_id
        """
        node_logger = self.get_node_logger(
            node_id=node_id,
            node_name=node_name,
            global_config=global_config
        )
        node_logger.info(
            ">>> Branch execution completed at node name: %s ",
            node_name,
            extra=self.common_log_arguments
        )

# Made with Bob
