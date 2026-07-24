from docpipe.core.constants import OrchestratorType
from docpipe.core.job_management.domain.ports import JobRunManager, JobStatsService
from docpipe.core.orchestration.abstract_operator_executor import AbstractOperatorExecutor
from docpipe.core.orchestration.abstract_orchestrator import AbstractOrchestrator
from docpipe.core.orchestration.python.python_operator_executor import PythonOperatorExecutor


class PythonOrchestrator(AbstractOrchestrator):
    """
    This orchestrator is used for pure Python orchestrations
    """

    def __init__(
        self,
        job_stats_service: JobStatsService | None = None,
        job_run_manager: JobRunManager | None = None,
        enable_custom_operators: bool = True,
        custom_operator_packages: list[str] | None = None,
        execution_reporter=None,
    ):
        super().__init__(
            job_stats_service=job_stats_service,
            job_run_manager=job_run_manager,
            enable_custom_operators=enable_custom_operators,
            custom_operator_packages=custom_operator_packages,
            execution_reporter=execution_reporter,
        )

    def create_executor_impl(
        self,
        *,
        name: str,
        operator: str,
        params: dict,
        job_stats_service: JobStatsService | None = None,
    ) -> AbstractOperatorExecutor:
        return PythonOperatorExecutor(
            name=name,
            operator=operator,
            params=params,
            job_stats_service=job_stats_service,
            enable_custom_operators=self.enable_custom_operators,
            custom_operator_packages=self.custom_operator_packages,
        )

    def visualize(self):
        pass

    def get_type(self) -> str:
        return OrchestratorType.PYTHON
