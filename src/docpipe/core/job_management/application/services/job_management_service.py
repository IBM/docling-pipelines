"""
JobManagementService - High-level API for job management operations.

This service provides API-level operations for managing job runs,
coordinating between JobStatsService and JobRunManager.
"""

import json
import traceback
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from docpipe.core.assets.flows.adapters.config.repository_factory import (
    RepositoryFactory,
)
from docpipe.core.constants.constants import (
    DocpipeConstants,
    ExecutionStatus,
    OrchestratorType,
)
from docpipe.core.job_management.domain.models import JobStats
from docpipe.core.job_management.domain.ports import JobRunManager, JobStatsService
from docpipe.core.models.session_info import create_session_info, set_session_info
from docpipe.exceptions.docpipe_exceptions import (
    FlowInvalidDataException,
    FlowNotFoundException,
    FlowValidationException,
)
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger()


class JobManagementService:
    """
    High-level service for job management operations.

    This service coordinates between:
    - JobStatsService: For tracking job statistics
    - JobRunManager: For framework-specific job execution

    Provides API-level operations like:
    - Creating job runs
    - Getting job status
    - Cancelling jobs
    - Deleting job runs
    - Listing jobs
    """

    def __init__(
        self,
        *,
        job_stats_service: JobStatsService,
        job_run_manager: JobRunManager,
        executor: ThreadPoolExecutor | None = None,
    ):
        """
        Initialize JobManagementService.

        Args:
            job_stats_service: Service for job statistics tracking
            job_run_manager: Framework adapter for job execution
            executor: Optional thread pool for async operations
        """
        self.job_stats_service = job_stats_service
        self.job_run_manager = job_run_manager
        self.executor = executor or ThreadPoolExecutor(max_workers=10)
        self.flow_repository = RepositoryFactory.create_default_flow_repository()

    def create_job_run_from_request(self, *, request_body: Any) -> str:
        """
        Create and start a new job run from API request body.

        Extracts and validates job parameters from the request body,
        then delegates to create_job_run for execution.

        Args:
            request_body: JobsAPIExecuteModel containing job and job_run configuration

        Returns:
            job_run_id: Unique identifier for the created job run

        Raises:
            JobRunOperationFailedException: If required fields are missing or invalid
        """
        # Extract job and job_run from request
        job = request_body.entity.job
        job_run = request_body.entity.job_run

        # Extract job_id (required)
        flow_id = job.asset_ref if job else None
        if not flow_id:
            raise FlowNotFoundException(message="entity.job.asset_ref is required")

        # Extract flow_name
        flow_name = (job.name if job else None) or flow_id

        # Build flow_config from job and job_run configurations
        flow_config = dict(job.configuration if job else {})
        job_run_config_model = job_run.configuration if job_run and job_run.configuration else None
        job_run_config = job_run_config_model.model_dump(exclude_none=True) if job_run_config_model else {}
        if job_run_config:
            flow_config.update(job_run_config)

        # Extract user_id and metadata
        user_id = None
        metadata = {}
        if job_run_config_model:
            user_id = job_run_config_model.user_id
            metadata = dict(job_run_config_model.metadata)

        return self._create_job_run(
            flow_id=flow_id, flow_name=flow_name, flow_config=flow_config, user_id=user_id, metadata=metadata
        )

    def _create_job_run(
        self,
        *,
        flow_id: str,
        flow_name: str,
        flow_config: dict[str, Any],
        user_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """
        Create and start a new job run.

        Args:
            flow_id: flow identifier
            flow_name: Name of the flow being executed
            flow_config: Flow configuration dictionary
            user_id: Optional user identifier
            metadata: Optional metadata dictionary

        Returns:
            job_run_id: Unique identifier for this job run
        """
        from docpipe.utils.orchestration.elyra_converter import ElyraConverter

        flow = self.flow_repository.find_by_id(flow_id)
        if flow is None:
            raise FlowNotFoundException(f"Flow not found for flow_id: {flow_id}")

        if hasattr(flow, DocpipeConstants.JOB_ID) and flow.job_id:
            flow_config[DocpipeConstants.JOB_ID] = flow.job_id

        result = self.job_run_manager.create_job_run(
            job_id=flow_id,
            job_config=flow_config,
        )

        job_id = result.get(DocpipeConstants.JOB_ID) if result else None
        job_run_id = result.get(DocpipeConstants.JOB_RUN_ID) if result else None
        if not job_id:
            raise RuntimeError(f"Framework did not return job_id for flow_id: {flow_id}")
        if not job_run_id:
            raise RuntimeError(f"Framework did not return job_run_id for job_id: {job_id}")

        self.job_stats_service.start_tracking_job(
            job_id=job_id,
            job_run_id=job_run_id,
            flow_name=flow_name,
            user_id=user_id,
            metadata=metadata or {},
        )

        # Detect format and transform to Internal DAG format for execution

        # Authoring format has 'flow_name' key, Elyra format has 'doc_type' key
        if DocpipeConstants.FLOW_NAME in flow.definition:
            # Authoring format - compile to runtime DAG
            from docpipe.core.assets.flows.application.services.authoring_compiler import AuthoringCompiler
            from docpipe.core.assets.flows.domain.models.authoring_flow import AuthoringFlow

            logger.info(f"Flow {flow_id} is in authoring format, compiling to runtime DAG")
            authoring_flow = AuthoringFlow.from_dict(data=flow.definition)
            compiler = AuthoringCompiler()
            flow_dag_definition = compiler.compile(authoring_flow=authoring_flow)
        elif "doc_type" in flow.definition:
            # Elyra format - transform to internal DAG
            logger.info(f"Flow {flow_id} is in Elyra format, transforming to internal DAG")
            converter = ElyraConverter()
            flow_dag_definition = converter.transform_elyra_to_internal(elyra_json=flow.definition, flow_id=flow_id)
        else:
            # Unknown format
            raise FlowInvalidDataException(message=f"Flow {flow_id} has unknown format.", field_name="definition")

        self.executor.submit(
            self._execute_flow_async,
            job_id,
            job_run_id,
            flow_dag_definition,
            flow_config,
        )

        logger.info(f"Created job run: flow_id={flow_id}, job_id={job_id}, job_run_id={job_run_id}")
        return job_run_id

    def get_job_run_status(self, *, job_run_id: str) -> JobStats | None:
        """
        Get current status of a job run.

        Args:
            job_run_id: Job run identifier

        Returns:
            JobStats if found, None otherwise
        """
        return self.job_stats_service.get_job_run_stats(job_run_id=job_run_id)

    def cancel_job_run(self, *, job_run_id: str) -> None:
        """
        Request cancellation of a job run.

        Args:
            job_run_id: Job run identifier
        """
        # Request cancellation via stats service
        self.job_stats_service.request_cancel_job(job_run_id=job_run_id)

        # Notify framework manager
        self.job_run_manager.cancel_job_run(job_run_id=job_run_id)

        logger.info(f"Requested cancellation: job_run_id={job_run_id}")

    def delete_job_run(self, *, job_run_id: str) -> None:
        """
        Delete a job run and its statistics.

        Args:
            job_run_id: Job run identifier
        """
        # Request deletion via stats service
        self.job_stats_service.request_delete_job_run(job_run_id=job_run_id)

        # Delete from framework
        self.job_run_manager.delete_job_run(job_run_id=job_run_id)

        logger.info(f"Deleted job run: job_run_id={job_run_id}")

    def list_job_runs(
        self,
        *,
        job_id: str | None = None,
        status: ExecutionStatus | str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        """
        List job runs with optional filters, formatted for API response.

        Args:
            job_id: Optional filter by job_id
            status: Optional filter by status (ExecutionStatus or string)
            limit: Maximum number of results

        Returns:
            Dictionary with 'list', 'count', and 'total' keys ready for API response
        """
        job_runs = self.job_stats_service.list_job_runs(job_id=job_id, status=status, limit=limit)

        # Transform to API response format (projection of key fields)
        list_items = [
            job_run.model_dump(
                include={
                    DocpipeConstants.JOB_RUN_ID,
                    DocpipeConstants.JOB_ID,
                    DocpipeConstants.STATUS,
                    DocpipeConstants.MESSAGE,
                    DocpipeConstants.START_TIME,
                    DocpipeConstants.END_TIME,
                    DocpipeConstants.DURATION,
                    DocpipeConstants.TOTAL_DOCS,
                    DocpipeConstants.PROCESSED_DOCS,
                    DocpipeConstants.COMPLETED_DOCS,
                    DocpipeConstants.FAILED_DOCS,
                    DocpipeConstants.SKIPPED_DOCS,
                    DocpipeConstants.ORCHESTRATOR,
                }
            )
            for job_run in job_runs
        ]

        return {
            "list": list_items,
            "count": len(list_items),
            "total": len(list_items),
        }

    def _execute_flow_async(
        self,
        job_id: str,
        job_run_id: str,
        flow_definition: dict[str, Any],
        flow_config: dict[str, Any],
    ) -> None:
        """Execute the resolved flow definition in a background thread."""
        try:
            from docpipe.core.orchestration.flow_executor import FlowExecutor
            from docpipe.core.orchestration.orchestrator_factory import OrchestratorFactory

            orchestrator = OrchestratorFactory.create_orchestrator(
                orchestrator_name=OrchestratorType.PYTHON,
                job_stats_service=self.job_stats_service,
                job_run_manager=self.job_run_manager,
            )

            session = create_session_info(
                orchestrator=orchestrator,
                job_id=job_id,
                job_run_id=job_run_id,
                flow_id=flow_config.get(DocpipeConstants.FLOW_ID, job_id),
            )
            set_session_info(session)

            executable_flow = flow_definition.get(DocpipeConstants.FLOW, flow_definition)
            flow_executor = FlowExecutor(flow_def=executable_flow, orchestrator=orchestrator)
            params = {
                DocpipeConstants.JOB_ID: job_id,
                DocpipeConstants.JOB_RUN_ID: job_run_id,
                **flow_config,
            }
            flow_executor.execute(orchestrator=orchestrator, params=params)
            logger.info(f"Completed async flow execution for job_run_id={job_run_id}")
        except FlowValidationException as validation_exc:
            # Log detailed errors, warnings, and traceback (delegated to exception)
            validation_exc.log_details(job_run_id=job_run_id)

            # Format error message with structured details
            error_message = self._format_validation_error_message(validation_exc)

            try:
                # Update job run status with formatted error message
                logger.debug(f"Updating job run status to Failed with validation details: job_run_id={job_run_id}")
                try:
                    self.job_run_manager.update_job_run_status(
                        job_run_id=job_run_id,
                        status=ExecutionStatus.FAILED.value,
                        job_run_stats={DocpipeConstants.MESSAGE: error_message},
                    )
                except Exception as update_error:
                    logger.warning(
                        f"Failed to update job run status to FAILED (non-critical): {update_error}. "
                        f"Error message was: {error_message}"
                    )

                self.job_stats_service.end_job(
                    job_run_id=job_run_id,
                    status=ExecutionStatus.FAILED.value,
                    job_run_stats={DocpipeConstants.MESSAGE: error_message},
                )
            except Exception as end_exc:
                logger.error(
                    f"Failed to finalize validation error for job_run_id={job_run_id}: {end_exc}",
                    exc_info=True,
                )
        except Exception as exc:
            # Handle all other exceptions (extraction failures, runtime errors, etc.)
            tb_lines = traceback.format_exception(type(exc), exc, exc.__traceback__)
            full_traceback = "".join(tb_lines)

            # Logging traceback as prefect consumes stacktrace
            logger.error(f"Async flow execution failed for job_run_id={job_run_id}: {full_traceback}", exc_info=True)

            # Build error message with more context
            error_message = self._build_detailed_error_message(exc)

            try:
                # Update status to Failed
                logger.info(f"Updating job run status to Failed: job_run_id={job_run_id}")
                try:
                    self.job_run_manager.update_job_run_status(
                        job_run_id=job_run_id,
                        status=ExecutionStatus.FAILED.value,
                        job_run_stats={DocpipeConstants.MESSAGE: error_message},
                    )
                except Exception as update_error:
                    logger.warning(f"Failed to update job run status to FAILED (non-critical): {update_error}")

                self.job_stats_service.end_job(
                    job_run_id=job_run_id,
                    status=ExecutionStatus.FAILED.value,
                    job_run_stats={DocpipeConstants.MESSAGE: error_message},
                )
            except Exception as end_exc:
                logger.error(
                    f"Failed to finalize error job_run_id={job_run_id}: {end_exc}",
                    exc_info=True,
                )

    def _serialize_validation_alerts(self, alerts: list[Any]) -> list[dict[str, Any]]:
        """
        Serialize ValidationAlert objects to user-friendly dictionaries for API response.
        Only includes fields that are actionable for end users: node_name, operator, message.

        Args:
            alerts: List of ValidationAlert objects or dictionaries

        Returns:
            List of user-friendly dictionaries with validation alert details
        """
        serialized = []
        for alert in alerts:
            try:
                alert_dict: dict[str, Any] | None = None

                # Handle ValidationAlert objects with to_dict method
                if hasattr(alert, "to_dict") and callable(alert.to_dict):
                    alert_dict = alert.to_dict()  # type: ignore[assignment]
                # Handle dict-like objects (ValidationAlert inherits from dict)
                elif isinstance(alert, dict):
                    alert_dict = dict(alert)
                # Handle ValidationMessage objects
                elif hasattr(alert, "model_dump"):
                    alert_dict = alert.model_dump(exclude_none=True)  # type: ignore[assignment]
                else:
                    # Fallback: convert to string representation
                    logger.warning(f"Unknown validation alert type: {type(alert)}, converting to string")
                    serialized.append({"message": str(alert)})
                    continue

                # Filter to user-friendly fields only (node_name, operator, message)
                user_friendly: dict[str, Any] = {}
                if alert_dict and "node_name" in alert_dict:
                    user_friendly["node_name"] = alert_dict["node_name"]
                if alert_dict and "operator" in alert_dict:
                    user_friendly["operator"] = alert_dict["operator"]
                if alert_dict and "message" in alert_dict:
                    user_friendly["message"] = alert_dict["message"]

                # Ensure we always have at least a message
                if not user_friendly.get("message"):
                    user_friendly["message"] = str(alert)

                serialized.append(user_friendly)

            except Exception as e:
                logger.error(f"Failed to serialize validation alert: {e}", exc_info=True)
                # Include error info but don't fail the entire serialization
                serialized.append({"message": str(alert), "serialization_error": str(e)})

        return serialized

    def _format_validation_error_message(self, exc: FlowValidationException) -> str:
        """
        Format validation exception into detailed error message .
        Matches enterprise implementation for consistency.

        Args:
            exc: FlowValidationException with errors and warnings

        Returns:
            Formatted error message with JSON-structured details
        """
        # Serialize errors and warnings
        error_dicts = self._serialize_validation_alerts(exc.errors) if exc.errors else []
        warning_dicts = self._serialize_validation_alerts(exc.warnings) if exc.warnings else []

        # Build structured error details
        error_details = {"errors": error_dicts, "warnings": warning_dicts}

        # Format: "Flow validation error: <summary>\n<JSON details>"
        return f"Flow validation error: {exc!s}\n{json.dumps(error_details, indent=2)}"

    def _build_detailed_error_message(self, exc: Exception) -> str:
        """
        Build a detailed error message from an exception, extracting useful context.

        Args:
            exc: The exception to build a message from

        Returns:
            Detailed error message string
        """
        error_message = str(exc)

        # Add exception type for clarity
        exc_type = type(exc).__name__
        if exc_type not in error_message:
            error_message = f"{exc_type}: {error_message}"

        # Extract additional context from specific exception types
        # Use hasattr with getattr to safely access errors attribute
        if hasattr(exc, "errors"):
            try:
                errors = getattr(exc, "errors", None)
                if errors and isinstance(errors, list):
                    error_details = []
                    for error in errors[:5]:  # Limit to first 5 errors
                        if isinstance(error, dict):
                            loc = " -> ".join(str(location) for location in error.get("loc", []))
                            msg = error.get("msg", "")
                            error_details.append(f"{loc}: {msg}")
                    if error_details:
                        error_message += f". Details: {'; '.join(error_details)}"
            except Exception as e:
                logger.debug(f"Could not extract error details: {e}")

        return error_message

    def shutdown(self) -> None:
        """
        Shutdown the service and cleanup resources.
        """
        self.executor.shutdown(wait=True)
        logger.info("JobManagementService shutdown complete")
