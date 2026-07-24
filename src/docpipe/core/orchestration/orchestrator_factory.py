from docpipe.core.constants import OrchestratorType
from docpipe.core.job_management.adapters.config.job_management_factory import get_default_factory
from docpipe.core.job_management.domain.ports import JobRunManager, JobStatsService
from docpipe.core.orchestration.abstract_orchestrator import AbstractOrchestrator
from docpipe.core.orchestration.python.python_orchestrator import PythonOrchestrator

"""
statically defined list of available orchestrators
Additional orchestrators will be added in future
"""
orchestrators = {OrchestratorType.PYTHON: PythonOrchestrator}


class OrchestratorFactory:
    """
    Factory class to create an instance of an orchestrator with dependency injection.
    """

    @staticmethod
    def create_orchestrator(
        *,
        orchestrator_name: str = OrchestratorType.PYTHON,
        job_stats_service: JobStatsService | None = None,
        job_run_manager: JobRunManager | None = None,
        enable_custom_operators: bool = True,
        custom_operator_packages: list[str] | None = None,
        execution_reporter=None,
    ) -> AbstractOrchestrator:  # pragma: no cover
        """
        Create an instance of the orchestrator with injected dependencies.

        Args:
            orchestrator_name: Type of orchestrator to create
            job_stats_service: Optional job stats service (uses default if None)
            job_run_manager: Optional job run manager for framework status updates
            enable_custom_operators: Whether to enable custom operators (passed to operator factory)
            custom_operator_packages: List of custom operator packages (passed to operator factory)
            execution_reporter: Optional output formatter for user-friendly console output

        Returns:
            Configured orchestrator instance
        """
        if job_stats_service is None:
            factory = get_default_factory()
            job_stats_service = factory.create_job_stats_service()

        orchestrator_class = orchestrators[orchestrator_name]
        orchestrator = orchestrator_class(
            job_stats_service=job_stats_service,
            job_run_manager=job_run_manager,
            enable_custom_operators=enable_custom_operators,
            custom_operator_packages=custom_operator_packages,
            execution_reporter=execution_reporter,
        )

        return orchestrator
