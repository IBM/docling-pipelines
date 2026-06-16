import argparse
import hashlib
import json
import os
import re
import sys
import uuid
from typing import Any

from datasift.utils.infrastructure.flow_execution_reporter import FlowExecutionReporter
from datasift.utils.infrastructure.logging import get_logger, set_dpk_log_level_from_ds_log_level

logger = get_logger()


def sanitize_flow_name_for_job_id(*, flow_name: str) -> str:
    """
    Sanitize flow_name to create a valid job_id.
    Converts to lowercase and replaces special characters/spaces with hyphens.
    Preserves Unicode word characters (letters from any language, digits, underscores).

    Args:
        flow_name: The flow name to sanitize

    Returns:
        Sanitized flow name suitable for use as job_id

    Raises:
        ValueError: If flow_name is empty or contains only whitespace
    """
    if not flow_name or not flow_name.strip():
        raise ValueError("flow_name cannot be empty")

    # Convert to lowercase and replace non-word chars (preserves Unicode letters/digits) with hyphens
    sanitized = re.sub(r"[^\w]+", "-", flow_name.lower(), flags=re.UNICODE)
    # Remove leading/trailing hyphens
    sanitized = sanitized.strip("-")

    return sanitized


def generate_job_id_from_flow_name(*, flow_name: str) -> str:
    """
    Generate a deterministic job_id from flow_name using UUID v5.

    Process:
    1. Sanitize flow_name (lowercase, replace special chars with hyphens)
    2. Generate 8-char hash from original flow_name
    3. Create intermediate string: {sanitized}_{hash}
    4. Generate UUID v5 from intermediate string

    This ensures:
    - Deterministic: Same flow_name always generates same job_id
    - Compatible: 36-character UUID format works with PostgreSQL job_stats_store
    - Standard: Same format as UUID v4 (8-4-4-4-12 with hyphens)
    - Unique: Different flow_names generate different job_ids

    Format: Standard UUID (8-4-4-4-12 format, 36 chars total)
    Example: "a1b2c3d4-e5f6-5789-a012-b3c4d5e6f7a8"

    Args:
        flow_name: The flow name from the flow definition

    Returns:
        Generated job_id as UUID v5 string (36 characters)
    """
    # Sanitize flow_name for consistency
    sanitized = sanitize_flow_name_for_job_id(flow_name=flow_name)

    # Generate deterministic hash (first 8 chars of SHA256)
    hash_value = hashlib.sha256(flow_name.encode("utf-8")).hexdigest()[:8]

    # Create intermediate string: {sanitized}_{hash}
    intermediate = f"{sanitized}_{hash_value}"

    # Generate deterministic UUID v5 from intermediate string
    # Using DNS namespace ensures global uniqueness
    job_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, intermediate))

    logger.info("Generated job_id '%s' from flow_name '%s' (intermediate: '%s')", job_id, flow_name, intermediate)
    return job_id


def run_command_line_executor(flow_def: dict) -> None:
    from datasift.core.constants.constants import DatasiftConstants
    from datasift.core.orchestration.flow_executor import FlowExecutor
    from datasift.core.orchestration.orchestrator_factory import OrchestratorFactory

    # Create execution reporter for user-friendly console output
    execution_reporter = FlowExecutionReporter()

    logger.info(">>> Creating the orchestrator")
    orchestrator = OrchestratorFactory.create_orchestrator(execution_reporter=execution_reporter)
    logger.info(">>> Creating the flow executor")
    executor = FlowExecutor(flow_def=flow_def, orchestrator=orchestrator)
    logger.info(">>> Setting up execution parameters")
    # Generate job_id from flow name (required field in compiled flow)
    flow_name = flow_def.get("name")
    if not flow_name:
        raise ValueError("Flow definition must include a 'name' field (compiled from 'flow_name' in authoring format)")
    job_id = generate_job_id_from_flow_name(flow_name=flow_name)
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
    Load and compile an authoring format flow definition from a JSON file.

    The authoring format is automatically compiled to runtime DAG format for execution.

    Args:
        file_path: Path to the JSON file containing the flow definition

    Returns:
        Dictionary containing the compiled runtime DAG format flow definition

    Raises:
        FileNotFoundError: If the flow definition file is not found
        json.JSONDecodeError: If the file contains invalid JSON
        FlowInvalidDataException: If the flow definition is invalid
        KeyError: If required fields are missing from the flow definition
        Exception: For other compilation errors
    """
    from datasift.core.assets.flows.application.services.authoring_compiler import AuthoringCompiler
    from datasift.core.assets.flows.domain.models.authoring_flow import AuthoringFlow

    with open(file_path, encoding="utf-8") as file:
        flow_data: dict[str, Any] = json.load(file)

    logger.info("Loading authoring format flow from %s", file_path)

    # Parse and validate authoring flow
    authoring_flow = AuthoringFlow.from_dict(data=flow_data)

    # Compile to runtime DAG format
    compiler = AuthoringCompiler()
    runtime_dag = compiler.compile(authoring_flow=authoring_flow)

    logger.info("Successfully compiled authoring format to runtime DAG")
    return runtime_dag


def validate_flow_definition(flow_file: str) -> bool:
    """
    Validate a flow definition file.

    Args:
        flow_file: Path to the flow definition JSON file

    Returns:
        True if validation succeeds, False otherwise
    """
    from datasift.core.models.session_info import create_session_info
    from datasift.core.orchestration.flow_validator import FlowValidator
    from datasift.core.orchestration.orchestrator_factory import OrchestratorFactory
    from datasift.exceptions.datasift_exceptions import FlowInvalidDataException, FlowValidationException

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

        FlowValidator(orchestrator=orchestrator).validate(flow_def=flow_def, params={})

        logger.info("Validation successful: '%s' is valid", flow_name)
        return True

    except FileNotFoundError:
        cwd = os.getcwd()
        abs_path = os.path.abspath(flow_file)
        logger.error("Flow definition file not found")
        logger.error("  Searched for: %s", abs_path)
        logger.error("  Current directory: %s", cwd)
        return False

    except json.JSONDecodeError as e:
        logger.error("Invalid JSON in flow definition file")
        logger.error("  File: %s", flow_file)
        logger.error("  Line %d, Column %d: %s", e.lineno, e.colno, e.msg)
        return False

    except (FlowInvalidDataException, KeyError) as e:
        logger.error("Flow validation failed")
        logger.error("  File: %s", flow_file)
        logger.error("  Error: %s", str(e))
        return False

    except FlowValidationException as e:
        errors: list[Any] = e.errors or []
        warnings: list[Any] = e.warnings or []

        for i, err in enumerate(errors, 1):
            logger.error("Error %d: %s", i, getattr(err, "message", str(err)))

        for i, warn in enumerate(warnings, 1):
            logger.warning("Warning %d: %s", i, getattr(warn, "message", str(warn)))

        # Only fail on errors, not warnings
        return not errors

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
  datasift-orchestrator --list-operators --verbose
  datasift-orchestrator --list-global-config
  datasift-orchestrator --list-global-config --verbose
  datasift-orchestrator --list-global-config --category "Micro-Batching"
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

    # -------------------------
    # list-global-config subcommand
    # -------------------------
    list_global_config_parser = subparsers.add_parser(
        "list-global-config",
        help="List all global configuration parameters",
    )
    list_global_config_parser.add_argument(
        "--category",
        "-c",
        type=str,
        help="Filter by category (e.g., 'Execution Control', 'Incremental Processing', 'Orchestration configuration')",
    )
    list_global_config_parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed parameter information",
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
        "--list-operators",
        "-lo",
        action="store_true",
        help="List all available operators and exit",
    )
    parser.add_argument(
        "--list-global-config",
        "-lgc",
        action="store_true",
        help="List all global configuration parameters and exit",
    )
    parser.add_argument(
        "--category",
        "-c",
        type=str,
        help="Filter by category (use with --list-global-config)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output (use with --list-operators or --list-global-config)",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate the flow definition without executing it",
    )

    args = parser.parse_args()

    # Configure DPK log level to match DS_LOG_LEVEL
    set_dpk_log_level_from_ds_log_level()

    # Setup logger early
    global logger
    logger = get_logger()

    # -------------------------
    # subcommand: validate-flow
    # -------------------------
    if args.command == "validate-flow":
        success = validate_flow_definition(flow_file=args.flow_file)
        sys.exit(0 if success else 1)

    # -------------------------
    # subcommand: list-global-config
    # -------------------------
    if args.command == "list-global-config":
        from datasift.utils.global_config.display import list_global_config

        print(list_global_config(category=args.category, verbose=args.verbose))
        return

    # -------------------------
    # list operators (fast exit path)
    # -------------------------
    if args.list_operators:
        from datasift.utils.operators.display import list_operators

        print(
            list_operators(
                verbose=args.verbose,
                summary_only=not args.verbose,  # Default: summary table, Verbose: detailed view
            )
        )
        return

    # -------------------------
    # list global config (fast exit path)
    # -------------------------
    if args.list_global_config:
        from datasift.utils.global_config.display import list_global_config

        print(
            list_global_config(
                verbose=args.verbose,
                category=args.category,
            )
        )
        return

    # -------------------------
    # validation or execution requires flow file
    # -------------------------
    if not args.flow_file:
        parser.error("--flow-file is required unless using a subcommand or --list-operators or --list-global-config")

    # -------------------------
    # validation mode
    # -------------------------
    if args.validate:
        success = validate_flow_definition(flow_file=args.flow_file)
        sys.exit(0 if success else 1)

    # -------------------------
    # execution mode
    # -------------------------
    from datasift.exceptions.datasift_exceptions import FlowInvalidDataException

    logger.info("Loading flow definition from %s", args.flow_file)

    try:
        flow_def = load_flow_definition(file_path=args.flow_file)
    except FileNotFoundError:
        cwd = os.getcwd()
        abs_path = os.path.abspath(args.flow_file)
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
        logger.error("  File: %s", args.flow_file)
        logger.error("  Line %d, Column %d: %s", e.lineno, e.colno, e.msg)
        logger.error("Suggestions:")
        logger.error("  - Validate JSON syntax using: python -m json.tool %s", args.flow_file)
        logger.error("  - Check for missing commas, brackets, or quotes")
        logger.error("  - Use a JSON validator: https://jsonlint.com/")
        sys.exit(1)
    except FlowInvalidDataException as e:
        logger.error("Flow validation failed")
        logger.error("  File: %s", args.flow_file)
        logger.error("%s", str(e))
        logger.error("Suggestions:")
        logger.error("  - Review the authoring format documentation")
        logger.error("  - Check operator names and dependencies")
        logger.error("  - Ensure all required fields are present")
        logger.error("  - Verify operator types are valid")
        sys.exit(1)
    except KeyError as e:
        logger.error("Missing required field in flow")
        logger.error("  File: %s", args.flow_file)
        logger.error("  Missing field: %s", str(e))
        logger.error("Suggestions:")
        logger.error("  - Ensure 'flow_name' field is present")
        logger.error("  - Ensure 'flow' array is present with operators")
        logger.error("  - Check that all operators have required fields (type, name)")
        sys.exit(1)
    except Exception as e:
        logger.error("Failed to compile flow")
        logger.error("  File: %s", args.flow_file)
        logger.error("  Error: %s", str(e))
        logger.exception("Compilation error details:")
        sys.exit(1)

    logger.info("Loaded flow definition from %s", args.flow_file)
    logger.info("Flow name: %s", flow_def.get("name", "Unnamed flow"))
    logger.info("Number of operators: %d", len(flow_def.get("dag", [])))

    run_command_line_executor(flow_def=flow_def)

    logger.info("Execution completed")


if __name__ == "__main__":  # pragma: no cover
    main()
