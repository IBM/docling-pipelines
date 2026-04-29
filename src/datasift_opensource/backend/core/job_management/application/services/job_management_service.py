"""
JobManagementService - High-level API for job management operations.

This service provides API-level operations for managing job runs,
coordinating between JobStatsService and JobRunManager.
"""

from concurrent.futures import ThreadPoolExecutor
from typing import Any

from common.constants.constants import DatasiftConstants, ExecutionStatus, OrchestratorType
from common.exceptions.datasift_exceptions import FlowNotFoundException
from common.models.session_info import create_session_info, set_session_info
from common.util.infrastructure.logging import get_logger
from core.assets_management.adapters.config.repository_factory import RepositoryFactory
from core.job_management.domain.models import JobStats
from core.job_management.domain.ports import JobRunManager, JobStatsService

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
        flow = self.flow_repository.find_by_id(flow_id)
        if flow is None:
            raise FlowNotFoundException(f"Flow not found for flow_id: {flow_id}")

        if hasattr(flow, DatasiftConstants.JOB_ID) and flow.job_id:
            flow_config[DatasiftConstants.JOB_ID] = flow.job_id

        result = self.job_run_manager.create_job_run(
            job_id=flow_id,
            job_config=flow_config,
        )

        job_id = result.get(DatasiftConstants.JOB_ID) if result else None
        job_run_id = result.get(DatasiftConstants.JOB_RUN_ID) if result else None
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

        self.executor.submit(
            self._execute_flow_async,
            job_id,
            job_run_id,
            flow.definition,
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
                    DatasiftConstants.JOB_RUN_ID,
                    DatasiftConstants.JOB_ID,
                    DatasiftConstants.STATUS,
                    DatasiftConstants.MESSAGE,
                    DatasiftConstants.START_TIME,
                    DatasiftConstants.END_TIME,
                    DatasiftConstants.DURATION,
                    DatasiftConstants.TOTAL_DOCS,
                    DatasiftConstants.PROCESSED_DOCS,
                    DatasiftConstants.COMPLETED_DOCS,
                    DatasiftConstants.FAILED_DOCS,
                    DatasiftConstants.SKIPPED_DOCS,
                    DatasiftConstants.ORCHESTRATOR,
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
            from core.orchestrator.flow_executor import FlowExecutor
            from core.orchestrator.orchestrator_factory import OrchestratorFactory

            orchestrator = OrchestratorFactory.create_orchestrator(
                orchestrator_name=OrchestratorType.PYTHON,
                job_stats_service=self.job_stats_service,
                job_run_manager=self.job_run_manager,
            )

            session = create_session_info(
                orchestrator=orchestrator,
                job_id=job_id,
                job_run_id=job_run_id,
                flow_id=flow_config.get(DatasiftConstants.FLOW_ID, job_id),
            )
            set_session_info(session)

            executable_flow = flow_definition.get(DatasiftConstants.FLOW, flow_definition)
            flow_executor = FlowExecutor(flow_def=executable_flow, orchestrator=orchestrator)
            params = {
                DatasiftConstants.JOB_ID: job_id,
                DatasiftConstants.JOB_RUN_ID: job_run_id,
                **flow_config,
            }
            flow_executor.execute(orchestrator=orchestrator, params=params)
            logger.info(f"Completed async flow execution for job_run_id={job_run_id}")
        except Exception as exc:
            logger.error(f"Async flow execution failed for job_run_id={job_run_id}: {exc}", exc_info=True)
            try:
                # Update status to Failed
                logger.info(f"Updating job run status to Failed: job_run_id={job_run_id}")
                try:
                    self.job_run_manager.update_job_run_status(
                        job_run_id=job_run_id,
                        status=ExecutionStatus.FAILED.value,
                        job_run_stats={DatasiftConstants.MESSAGE: str(exc)},
                    )
                except Exception as update_error:
                    logger.warning(f"Failed to update job run status to FAILED (non-critical): {update_error}")

                self.job_stats_service.end_job(
                    job_run_id=job_run_id,
                    status=ExecutionStatus.FAILED.value,
                    job_run_stats={DatasiftConstants.MESSAGE: str(exc)},
                )
            except Exception as end_exc:
                logger.error(
                    f"Failed to finalize error job_run_id={job_run_id}: {end_exc}",
                    exc_info=True,
                )

    def shutdown(self) -> None:
        """
        Shutdown the service and cleanup resources.
        """
        self.executor.shutdown(wait=True)
        logger.info("JobManagementService shutdown complete")
