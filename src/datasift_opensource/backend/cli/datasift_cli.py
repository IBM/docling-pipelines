import argparse
import json
import os
import sys
import uuid
from logging import Logger
from typing import Any

from common.constants.constants import OrchestratorType
from common.util.job_tracker.tracker.job_tracker import JobTracker
from common.util.log import get_logger

logger = get_logger()


def run_command_line_executor(flow_def: dict) -> None:
    from common.constants.constants import DatasiftConstants
    from core.orchestrator.flow_executor import FlowExecutor
    from core.orchestrator.orchestrator_factory import OrchestratorFactory

    logger.info(">>> Creating the orchestrator")
    orchestrator = OrchestratorFactory.create_orchestrator(orchestrator_name=OrchestratorType.PYTHON)
    logger.info(">>> Creating the flow executor")
    executor = FlowExecutor(flow_def=flow_def, orchestrator=orchestrator)
    logger.info(">>> Setting up execution parameters")
    job_id = "001"
    job_run_id = str(uuid.uuid4())

    params: dict[str, Any] = {
        DatasiftConstants.JOB_ID: job_id,
        DatasiftConstants.JOB_RUN_ID: job_run_id,
    }
    os.environ["RUNTIME"] = "local"
    from common.models.session_info import (
        SessionInfo,
        create_session_info,
        set_session_info,
    )

    session_info: SessionInfo = create_session_info(
        job_id="001", job_run_id=job_run_id, orchestrator=orchestrator, flow_id="flow1"
    )
    set_session_info(session_info)

    logger.info(">>> Starting flow execution")
    executor.execute(orchestrator=orchestrator, params=params)
    logger.info(">>> Completed flow execution")


def load_flow_definition(file_path: str) -> dict[str, Any]:
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
        with open(file=file_path) as file:
            flow_def = json.load(file)

        # Check if the flow definition is nested under a 'flow' key
        if "flow" in flow_def:
            return flow_def["flow"]
        return flow_def
    except FileNotFoundError:
        print(f"Error: Flow definition file '{file_path}' not found.")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in flow definition file: {e}")
        sys.exit(1)


def main():  # pragma: no cover
    os.environ["CMD_LINE"] = "True"
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Execute a flow definition using the CommandLineOrchestrator.")
    parser.add_argument(
        "--flow-file",
        "-f",
        required=False,
        help="Path to the JSON file containing the flow definition",
    )
    parser.add_argument(
        "--log-level",
        "-l",
        choices=["debug", "info", "warning", "error", "critical"],
        default="info",
        help="Set the logging level (default: info)",
    )
    parser.add_argument(
        "--list-operators",
        "-lo",
        action="store_true",
        help="List all available operators with their details",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed information (use with --list-operators)",
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
    logger.info(">>> Completed execution")


# main entry point into the program; used for unit testing only
if __name__ == "__main__":  # pragma: no cover
    main()
