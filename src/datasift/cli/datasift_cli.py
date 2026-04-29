import argparse
import json
import os
import sys
import uuid
from typing import Any

from datasift.utils.infrastructure.logging import get_logger

logger = get_logger()


def run_command_line_executor(flow_def: dict) -> None:
    from datasift.core.constants.constants import DatasiftConstants
    from datasift.core.orchestration.flow_executor import FlowExecutor
    from datasift.core.orchestration.orchestrator_factory import OrchestratorFactory

    logger.info(">>> Creating the orchestrator")
    orchestrator = OrchestratorFactory.create_orchestrator()
    logger.info(">>> Creating the flow executor")
    executor = FlowExecutor(flow_def=flow_def, orchestrator=orchestrator)
    logger.info(">>> Setting up execution parameters")
    job_id = "b639fbec-de29-487f-9798-45e2f44a9b4d"
    job_run_id = str(uuid.uuid4())

    params: dict[str, Any] = {
        DatasiftConstants.JOB_ID: job_id,
        DatasiftConstants.JOB_RUN_ID: job_run_id,
    }
    os.environ["RUNTIME"] = "local"
    from datasift.core.models.session_info import (
        SessionInfo,
        create_session_info,
        set_session_info,
    )

    session_info: SessionInfo = create_session_info(
        job_id=job_id, job_run_id=job_run_id, orchestrator=orchestrator, flow_id="flow1"
    )
    set_session_info(session_info)

    orchestrator.initialize(job_id=job_id, job_run_id=job_run_id)

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

    Exits:
        Terminates process on file/JSON errors
    """
    try:
        with open(file_path, encoding="utf-8") as file:
            flow_def: dict[str, Any] = json.load(file)

        # Handle optional nesting under "flow"
        return flow_def.get("flow", flow_def)

    except FileNotFoundError:
        cwd = os.getcwd()
        abs_path = os.path.abspath(file_path)

        logger.error("Flow definition file not found")
        logger.error("  Searched for: %s", abs_path)
        logger.error("  Current directory: %s", cwd)
        logger.error("Suggestions:")
        logger.error("  - Check if the file path is correct")
        logger.error("  - Verify the file exists in the specified location")
        logger.error("  - Use absolute path or path relative to: %s", cwd)

        sys.exit(1)

    except json.JSONDecodeError as e:
        logger.error("Invalid JSON in flow definition file")
        logger.error("  File: %s", file_path)
        logger.error("  Line %d, Column %d: %s", e.lineno, e.colno, e.msg)
        logger.error("Suggestions:")
        logger.error("  - Validate JSON syntax using: python -m json.tool %s", file_path)
        logger.error("  - Check for missing commas, brackets, or quotes")
        logger.error("  - Use a JSON validator: https://jsonlint.com/")

        sys.exit(1)


def validate_flow_definition(flow_file: str) -> bool:
    from datasift.core.models.session_info import create_session_info
    from datasift.core.orchestration.flow_validator import FlowValidator
    from datasift.core.orchestration.orchestrator_factory import OrchestratorFactory
    from datasift.exceptions.datasift_exceptions import FlowValidationException

    try:
        flow_def: dict[str, Any] = load_flow_definition(file_path=flow_file)
        flow_name: str = flow_def.get("name", "Unnamed flow")

        logger.info(
            "Validating flow: '%s' number of operators: %d",
            flow_name,
            len(flow_def.get("dag", [])),
        )

        orchestrator = OrchestratorFactory.create_orchestrator()
        validation_job_id = f"validation_{uuid.uuid4()}"
        validation_job_run_id = f"validation_run_{uuid.uuid4()}"

        create_session_info(
            job_id=validation_job_id,
            job_run_id=validation_job_run_id,
            orchestrator=orchestrator,
            flow_id="validation_flow",
        )

        orchestrator.initialize(job_id=validation_job_id, job_run_id=validation_job_run_id)

        FlowValidator(orchestrator).validate(flow_def=flow_def, params={})

        logger.info("Validation successful: '%s' is valid", flow_name)
        return True

    except FlowValidationException as e:
        errors: list[Any] = e.errors or []
        warnings: list[Any] = e.warnings or []

        for i, err in enumerate(errors, 1):
            logger.error("Error %d: %s", i, getattr(err, "message", str(err)))

        for i, warn in enumerate(warnings, 1):
            logger.warning("Warning %d: %s", i, getattr(warn, "message", str(warn)))

        # Fail on both errors and warnings
        return not (errors or warnings)

    except Exception:
        logger.exception("Validation failed with unexpected error")
        return False


def main() -> None:  # pragma: no cover
    os.environ["CMD_LINE"] = "True"

    parser = argparse.ArgumentParser(
        description="Execute or validate a flow definition using the CommandLineOrchestrator.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  datasift-orchestrator --flow-file flow.json
  datasift-orchestrator --flow-file flow.json --validate
  datasift-orchestrator validate-flow flow.json
  datasift-orchestrator --list-operators
        """,
    )

    subparsers = parser.add_subparsers(dest="command")

    # -------------------------
    # validate-flow subcommand
    # -------------------------
    validate_parser = subparsers.add_parser(
        "validate-flow",
        help="Validate a flow definition without executing it",
    )
    validate_parser.add_argument(
        "flow_file",
        help="Path to the flow definition JSON file to validate",
    )

    validate_parser.add_argument(
        "--log-level",
        "-l",
        choices=["debug", "info", "warning", "error", "critical"],
        default="info",
        help="Set logging level (default: info)",
    )

    # -------------------------
    # global args
    # -------------------------
    parser.add_argument(
        "--flow-file",
        "-f",
        help="Path to the flow definition JSON file",
    )
    parser.add_argument(
        "--log-level",
        "-l",
        choices=["debug", "info", "warning", "error", "critical"],
        default="info",
        help="Set logging level (default: info)",
    )
    parser.add_argument(
        "--list-operators",
        "-lo",
        action="store_true",
        help="List all available operators and exit",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output (use with --list-operators)",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate the flow definition without executing it",
    )

    args = parser.parse_args()

    # Setup logger early
    global logger
    logger = get_logger(level=args.log_level.upper())

    # -------------------------
    # subcommand: validate-flow
    # -------------------------
    if args.command == "validate-flow":
        success = validate_flow_definition(flow_file=args.flow_file)
        sys.exit(0 if success else 1)

    # -------------------------
    # list operators (fast exit path)
    # -------------------------
    if args.list_operators:
        from datasift.utils.operators.display import list_operators

        print(
            list_operators(
                verbose=args.verbose,
                summary_only=not args.verbose,
            )
        )
        return

    # -------------------------
    # validation or execution requires flow file
    # -------------------------
    if not args.flow_file:
        parser.error("--flow-file is required unless using a subcommand or --list-operators")

    # -------------------------
    # validation mode
    # -------------------------
    if args.validate:
        success = validate_flow_definition(flow_file=args.flow_file)
        sys.exit(0 if success else 1)

    # -------------------------
    # execution mode
    # -------------------------
    logger.info("Loading flow definition from %s", args.flow_file)

    flow_def = load_flow_definition(file_path=args.flow_file)

    logger.info("Loaded flow definition from %s", args.flow_file)
    logger.info("Flow name: %s", flow_def.get("name", "Unnamed flow"))
    logger.info("Number of operators: %d", len(flow_def.get("dag", [])))

    run_command_line_executor(flow_def=flow_def)

    logger.info("Execution completed")


if __name__ == "__main__":  # pragma: no cover
    main()
