from common.constants import OrchestratorType
from core.job_management.domain.ports import JobRunManager, JobStatsService
from core.orchestrator.abstract_operator_executor import AbstractOperatorExecutor
from core.orchestrator.abstract_orchestrator import AbstractOrchestrator
from core.orchestrator.python.python_operator_executor import PythonOperatorExecutor


class PythonOrchestrator(AbstractOrchestrator):
    """
    This orchestrator is used for pure Python orchestrations
    """

    def __init__(
        self,
        job_stats_service: JobStatsService | None = None,
        job_run_manager: JobRunManager | None = None,
    ):
        super().__init__(job_stats_service=job_stats_service, job_run_manager=job_run_manager)

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
