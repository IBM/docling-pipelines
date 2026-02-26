import argparse
import json
import os
import sys
from logging import Logger
from typing import Any, Dict

import pyarrow as pa
from data_processing.data_access import DataAccess, DataAccessFactory

from common.exceptions.datasift_exceptions import FlowExecutionFailedException
from core.orchestrator.abstract_operator_executor import AbstractOperatorExecutor
from core.orchestrator.abstract_orchestrator import AbstractOrchestrator
from core.orchestrator.cmdline.cmd_line_operator_executor import CommandLineOperatorExecutor
from common.util.constants import OrchestratorType, DatasiftConstants, OperatorConstants
from common.util.job_tracker.tracker.job_tracker import JobTracker
from common.util.log import get_logger

logger = get_logger()


class CommandLineOrchestrator(AbstractOrchestrator):
    """
    This orchestrator is used for pure Python orchestration, but when datasift is
    executed from the commandline.
    """

    def __init__(self):
        super().__init__()

    def create_executor_impl(self, *, name: str, operator: str, params: dict) -> AbstractOperatorExecutor:
        return CommandLineOperatorExecutor(name, operator, params)

    def execute(self, *, flow_def: dict, params: dict) -> DataAccess | None:
        self.set_job_id(job_id=params.get(DatasiftConstants.JOB_ID))
        self.set_job_run_id(job_run_id=params.get(DatasiftConstants.JOB_RUN_ID))
        global_config = flow_def.get(OperatorConstants.GLOBAL_CONFIG, {}) | params | {
            DatasiftConstants.FLOW_DEFINITION: flow_def}

        if DatasiftConstants.DAG not in flow_def:
            raise FlowExecutionFailedException("Invalid flow: 'dag' not found in the flow definition")
        op_flow = flow_def.get(DatasiftConstants.DAG, [])

        # Create an empty DataAccess as input to the flow
        data_access_factory = DataAccessFactory()
        config = {"data_config": {"da_class": "data_processing.data_access.DataAccessMemory"}}
        data_access_factory.apply_input_params(args=config)
        data_access = data_access_factory.create_data_access()
        data_access.save_table(path="", table=pa.Table.from_arrays([], names=[]))

        job_tracker = JobTracker()
        job_tracker.start_tracking_job(orchestrator=self, 
                                       job_id=self.get_job_id(), 
                                       job_run_id=self.get_job_run_id())

        job_log_final_path = self.create_log_folders_cpd(job_id=self.get_job_id(), type_="job")
        self.context_id = params.get(DatasiftConstants.CONTEXT_ID, self.get_job_id())

        # execute flows
        return self.execute_flow(op_flow=op_flow,
                            data_access=data_access, 
                            global_config=global_config,
                            common_log_arguments={
                                DatasiftConstants.JOB_ID: self.get_job_id(), 
                                DatasiftConstants.JOB_RUN_ID: self.get_job_run_id()
                            }, 
                            job_log_final_path=job_log_final_path)

    def get_type(self):
        return OrchestratorType.CMDLINE


def run_command_line_executor(flow_def: dict)  -> None:
    from common.util.constants import DatasiftConstants
    from core.orchestrator.flow_executor import FlowExecutor
    from core.orchestrator.orchestrator_factory import OrchestratorFactory

    logger.info('>>> Creating the orchestrator')
    orchestrator = OrchestratorFactory.create_orchestrator(orchestrator_name=OrchestratorType.CMDLINE)
    logger.info('>>> Creating the flow executor')
    executor = FlowExecutor(flow_def=flow_def, orchestrator=orchestrator)
    logger.info('>>> Setting up execution parameters')
    
    params: dict[str, Any] = {
        DatasiftConstants.JOB_ID: "001", 
        DatasiftConstants.JOB_RUN_ID: "002"
    }
    os.environ["RUNTIME"] = "local"
    from common.models.session_info import SessionInfo, set_session_info, create_session_info
    session_info: SessionInfo = create_session_info(job_id="001", job_run_id="002",
                                                    orchestrator=orchestrator, flow_id="flow1")
    set_session_info(session_info)
    
    logger.info('>>> Starting flow execution')
    executor.execute(orchestrator=orchestrator, params=params)
    logger.info('>>> Completed flow execution')


def load_flow_definition(file_path: str) -> Dict[str, Any]:
    """
    Load a flow definition from a JSON file.
    
    Args:
        file_path: Path to the JSON file containing the flow definition
        
    Returns:
        Dictionary containing the flow definition
        
    Raises:
        FileNotFoundError: If the file doesn't exist
        json.JSONDecodeError: If the file contains invalid JSON
    """
    try:
        with open(file=file_path, mode='r') as file:
            flow_def = json.load(file)
            
        # Check if the flow definition is nested under a 'flow' key
        if 'flow' in flow_def:
            return flow_def['flow']
        return flow_def
    except FileNotFoundError:
        print(f"Error: Flow definition file '{file_path}' not found.")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in flow definition file: {e}")
        sys.exit(1)

def main():  # pragma: no cover
    os.environ["CMD_LINE"] = 'True'
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description='Execute a flow definition using the CommandLineOrchestrator.'
    )
    parser.add_argument(
        '--flow-file', '-f',
        required=False,
        help='Path to the JSON file containing the flow definition'
    )
    parser.add_argument(
        '--log-level', '-l',
        choices=['debug', 'info', 'warning', 'error', 'critical'],
        default='info',
        help='Set the logging level (default: info)'
    )
    parser.add_argument(
        '--list-operators', '-lo',
        action='store_true',
        help='List all available operators with their details'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Show detailed information (use with --list-operators)'
    )
    args = parser.parse_args()
    
    # Handle --list-operators command early (before heavy imports)
    if args.list_operators:
        from common.util.operator_display_utils import list_operators
        print(list_operators(verbose=args.verbose, summary_only=not args.verbose))
        return
    
    # Validate that flow-file is provided for execution
    if not args.flow_file:
        parser.error("--flow-file is required unless using --list-operators")
    
    log_level = args.log_level.upper()
    logger: Logger = get_logger(level=log_level)

    # Load the flow definition from the JSON file
    print(f"Loading flow definition from {args.flow_file}")
    flow_def = load_flow_definition(file_path=args.flow_file)
    
    logger.info(f"Loaded flow definition from {args.flow_file}")
    logger.info(f"Flow name: {flow_def.get('name', 'Unnamed flow')}")
    logger.info(f"Number of operators: {len(flow_def.get('sequence', flow_def.get('dag', [])))}")
    
    # Execute the flow using the CommandLineOrchestrator
    run_command_line_executor(flow_def=flow_def)
    logger.info('>>> Completed execution')
    
# main entry point into the program; used for unit testing only
if __name__ == '__main__':  # pragma: no cover
    main()
