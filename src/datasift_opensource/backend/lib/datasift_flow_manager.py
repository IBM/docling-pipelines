"""
Programmatic DatasiftFlowManager for embedding datasift in notebooks and applications.

This module provides a high-level API for executing datasift flows programmatically,
wrapping the CLI functionality in a class suitable for notebook and embedded usage.
"""

import json
import uuid
from logging import Logger
from pathlib import Path
from typing import Any

from common.constants.constants import DatasiftConstants
from common.exceptions.datasift_exceptions import DatasiftException
from common.models.session_info import SessionInfo, create_session_info
from common.util.infrastructure.logging import get_logger
from common.util.operators.display import list_operators as _list_operators
from core.orchestrator.flow_executor import FlowExecutor
from core.orchestrator.flow_validator import FlowValidator
from core.orchestrator.orchestrator_factory import OrchestratorFactory


class DatasiftFlowManager:
    """
    Programmatic interface for executing datasift flows.

    This class provides a high-level API for running datasift flows from Python code,
    notebooks, or embedded applications. It wraps the CLI functionality and provides
    a clean interface for programmatic execution.

    Attributes:
        flow_file (Optional[str]): Path to flow definition JSON file
        flow_def (dict): Flow definition as dictionary
        log_level (str): Logging level (debug, info, warning, error, critical)
        job_id (str): Unique job identifier
        job_run_id (str): Unique job run identifier
        flow_id (str): Flow identifier
        orchestrator: Orchestrator instance (created during execution)
        session_info: Session information (created during execution)
        executor: FlowExecutor instance (created during execution)

    Example:
        # Execute from file
        manager = DatasiftFlowManager(flow_file="path/to/flow.json")
        result = manager.execute()

        # Execute from dict
        flow_def = {
            "name": "My Flow",
            "dag": [...]
        }
        manager = DatasiftFlowManager(flow_def=flow_def)
        result = manager.execute()
    """

    def __init__(
        self,
        flow_file: str | None = None,
        flow_def: dict | None = None,
        log_level: str = "info",
        job_id: str | None = None,
        job_run_id: str | None = None,
        flow_id: str | None = None,
    ):
        """
        Initialize DatasiftFlowManager.

        Args:
            flow_file: Path to JSON file containing flow definition
            flow_def: Flow definition as dictionary (used if flow_file not provided)
            log_level: Logging level (debug, info, warning, error, critical)
            job_id: Unique job identifier (priority: parameter > flow_def > UUID)
            job_run_id: Unique job run identifier (defaults to job_id if not provided)
            flow_id: Flow identifier (priority: parameter > flow_def > job_id)

        Raises:
            DatasiftException: If neither flow_file nor flow_def is provided
            DatasiftException: If both flow_file and flow_def are provided
            FileNotFoundError: If flow_file doesn't exist
            json.JSONDecodeError: If flow_file contains invalid JSON
        """
        if flow_file is None and flow_def is None:
            raise DatasiftException("Either flow_file or flow_def must be provided", status_code=400)

        if flow_file is not None and flow_def is not None:
            raise DatasiftException("Only one of flow_file or flow_def should be provided", status_code=400)

        # Set up logging
        self.log_level = log_level.upper()
        self.logger: Logger = get_logger(level=self.log_level)

        # Load flow definition
        if flow_file is not None:
            self.flow_file = flow_file
            self.flow_def = self._load_flow_definition(flow_file)
        else:
            self.flow_file = None  # type: ignore[assignment]
            self.flow_def = flow_def  # type: ignore

        # Set up execution parameters with priority: parameter > flow_def > UUID
        flow_def_flow_id = self.flow_def.get(DatasiftConstants.FLOW_ID) if self.flow_def else None

        # job_id priority: parameter > flow_def > UUID
        self.job_id = job_id or flow_def_flow_id or str(uuid.uuid4())

        # job_run_id defaults to dynamically generated UUID if not provided
        self.job_run_id = job_run_id or str(uuid.uuid4())

        # flow_id priority: parameter > flow_def > job_id
        self.flow_id = flow_id or flow_def_flow_id or self.job_id

        # Execution state (initialized during execute())
        self.orchestrator: Any | None = None
        self.session_info: SessionInfo | None = None
        self.executor: FlowExecutor | None = None

    def _load_flow_definition(self, file_path: str) -> dict[str, Any]:
        """
        Load flow definition from JSON file.

        Args:
            file_path: Path to JSON file

        Returns:
            Flow definition dictionary (accepts root-level flow definition)

        Raises:
            FileNotFoundError: If file doesn't exist
            json.JSONDecodeError: If file contains invalid JSON
        """
        path_obj = Path(file_path)
        if not path_obj.exists():
            raise FileNotFoundError(f"Flow definition file '{file_path}' not found")

        try:
            with open(path_obj) as f:
                flow_data = json.load(f)

            # Accept flow definition at root level (no nested "flow" key required)
            return flow_data
        except json.JSONDecodeError as e:
            raise json.JSONDecodeError(f"Invalid JSON in flow definition file: {e.msg}", e.doc, e.pos) from e

    def _initialize_execution_environment(self) -> None:
        """Initialize orchestrator and session for execution."""
        # Create orchestrator
        self.orchestrator = OrchestratorFactory.create_orchestrator()

        # Validate flow definition is initialized
        if self.flow_def is None:
            raise DatasiftException("Flow definition must be initialized before use", status_code=500)

        # Set up session info
        self.session_info = create_session_info(
            job_id=self.job_id, job_run_id=self.job_run_id, orchestrator=self.orchestrator, flow_id=self.flow_id
        )

        # Initialize orchestrator
        self.orchestrator.initialize(job_id=self.job_id, job_run_id=self.job_run_id)

        # Create flow executor - must be done after session_info is set
        self.executor = FlowExecutor(flow_def=self.flow_def, orchestrator=self.orchestrator)

    def validate(self) -> dict[str, Any]:
        """
        Validate the flow definition without executing it.

        Returns:
            Dictionary containing validation results with keys:
                - 'valid': bool indicating if flow is valid
                - 'errors': list of validation errors (if any)
                - 'warnings': list of validation warnings (if any)

        Raises:
            DatasiftException: If flow definition is not initialized

        Example:
            manager = DatasiftFlowManager(flow_file="flow.json")
            validation_result = manager.validate()
            if validation_result['valid']:
                result = manager.execute()
        """
        if self.flow_def is None:
            raise DatasiftException("Flow definition must be initialized before validation", status_code=500)

        try:
            # Create a temporary orchestrator for validation
            temp_orchestrator = OrchestratorFactory.create_orchestrator()
            validator = FlowValidator(orchestrator=temp_orchestrator)

            # Prepare validation parameters
            params: dict[str, Any] = {
                DatasiftConstants.JOB_ID: self.job_id,
                DatasiftConstants.JOB_RUN_ID: self.job_run_id,
            }

            validation_result = validator.validate(flow_def=self.flow_def, params=params)

            # Handle None return or dict return
            if validation_result is None:
                return {"valid": True, "errors": [], "warnings": []}

            return {
                "valid": validation_result.get("status", "FAILED") == "SUCCEEDED",
                "errors": validation_result.get("errors", []),
                "warnings": validation_result.get("warnings", []),
            }
        except Exception as e:
            self.logger.error(f"Flow validation failed: {e}")
            return {"valid": False, "errors": [str(e)], "warnings": []}

    def execute(self) -> Any:
        """
        Execute the flow.

        Returns:
            DataAccess object containing execution results

        Raises:
            DatasiftException: If flow definition is not initialized or execution fails

        Example:
            manager = DatasiftFlowManager(flow_file="flow.json")
            result = manager.execute()
            print(f"Execution completed: {result}")
        """
        # Initialize execution environment
        self._initialize_execution_environment()

        # Set up execution parameters
        params: dict[str, Any] = {
            DatasiftConstants.JOB_ID: self.job_id,
            DatasiftConstants.JOB_RUN_ID: self.job_run_id,
        }

        try:
            # Delegate execution to FlowExecutor (logging moved to FlowExecutor.execute())
            result = self.executor.execute(orchestrator=self.orchestrator, params=params)  # type: ignore
            return result
        except Exception as e:
            self.logger.error(f"Flow execution failed: {e}")
            raise

    def get_execution_metadata(self) -> dict[str, Any]:
        """
        Get metadata about the execution.

        Returns:
            Dictionary containing execution metadata

        Example:
            manager = DatasiftFlowManager(flow_file="flow.json")
            result = manager.execute()
            metadata = manager.get_execution_metadata()
            print(f"Job ID: {metadata['job_id']}")
        """
        return {
            DatasiftConstants.JOB_ID: self.job_id,
            DatasiftConstants.JOB_RUN_ID: self.job_run_id,
            DatasiftConstants.FLOW_ID: self.flow_id,
            DatasiftConstants.FLOW_NAME: self.flow_def.get(DatasiftConstants.NAME, DatasiftConstants.UNNAMED_FLOW)
            if self.flow_def
            else DatasiftConstants.UNNAMED_FLOW,  # type: ignore
            DatasiftConstants.FLOW_DESCRIPTION: self.flow_def.get(DatasiftConstants.DESCRIPTION, "")
            if self.flow_def
            else "",  # type: ignore
            "num_operators": len(self.flow_def.get(DatasiftConstants.DAG, [])) if self.flow_def else 0,  # type: ignore
            "flow_file": self.flow_file,
        }

    def get_execution_logs(self) -> list[str]:
        """
        Get logs captured during flow execution.

        This method should be called after ``execute()`` has run. It reads logs
        from the orchestrator event handler when available and returns them as a
        list of log lines. If execution has not been run yet, or if no logs are
        available, an empty list is returned.

        Returns:
            List of log entries captured during execution, or an empty list if
            execution has not run or no logs are available.

        Example:
            manager = DatasiftFlowManager(flow_file="flow.json")
            result = manager.execute()
            logs = manager.get_execution_logs()
            print(logs)
        """
        if self.orchestrator is None:
            return []

        event_handler = getattr(self.orchestrator, DatasiftConstants.FLOW_EXECUTION_EVENT_HANDLER, None)
        job_log_path = getattr(event_handler, DatasiftConstants.JOB_LOG_PATH, None)

        if not job_log_path:
            return []

        log_dir = Path(job_log_path).parent
        flow_log_path = log_dir / DatasiftConstants.FLOW_EXECUTE_LOG

        if not flow_log_path.exists() or not flow_log_path.is_file():
            return []

        return flow_log_path.read_text(encoding="utf-8").splitlines()

    @staticmethod
    def list_operators(verbose: bool = False) -> str:
        """
        List all available operators.

        Args:
            verbose: If True, show detailed information about each operator

        Returns:
            Formatted string listing all operators

        Example:
            # List operators with summary
            print(DatasiftFlowManager.list_operators())

            # List operators with details
            print(DatasiftFlowManager.list_operators(verbose=True))
        """
        return _list_operators(verbose=verbose, summary_only=not verbose)
