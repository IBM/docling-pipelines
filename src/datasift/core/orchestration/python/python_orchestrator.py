from datasift.core.constants import OrchestratorType
from datasift.core.job_management.domain.ports import JobRunManager, JobStatsService
from datasift.core.orchestration.abstract_operator_executor import AbstractOperatorExecutor
from datasift.core.orchestration.abstract_orchestrator import AbstractOrchestrator
from datasift.core.orchestration.python.python_operator_executor import PythonOperatorExecutor


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
    ):
        super().__init__(
            job_stats_service=job_stats_service,
            job_run_manager=job_run_manager,
            enable_custom_operators=enable_custom_operators,
            custom_operator_packages=custom_operator_packages,
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
        )

    def visualize(self):
        pass

    def get_type(self) -> str:
        return OrchestratorType.PYTHON
