from docpipe.core.job_management.domain.ports import JobStatsService
from docpipe.core.orchestration.python.python_operator_executor import PythonOperatorExecutor


class CommandLineOperatorExecutor(PythonOperatorExecutor):
    """
    Operator executor for command line orchestrator. Since the operator is loaded with
    Python, we reuse the PythonOperatorExecutor here.
    """

    def __init__(
        self,
        *,
        name: str,
        operator: str,
        params: dict,
        job_stats_service: JobStatsService | None = None,
    ):
        super().__init__(
            name=name,
            operator=operator,
            params=params,
            job_stats_service=job_stats_service,
        )
