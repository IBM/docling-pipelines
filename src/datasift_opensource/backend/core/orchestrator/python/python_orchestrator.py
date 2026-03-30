from common.constants import OrchestratorType
from core.orchestrator.abstract_operator_executor import AbstractOperatorExecutor
from core.orchestrator.abstract_orchestrator import AbstractOrchestrator
from core.orchestrator.python.python_operator_executor import PythonOperatorExecutor


class PythonOrchestrator(AbstractOrchestrator):
    """
    This orchestrator is used for pure Python orchestrations
    """

    def __init__(self):
        super().__init__()

    def create_executor_impl(self, *, name: str, operator: str, params: dict) -> AbstractOperatorExecutor:
        return PythonOperatorExecutor(name, operator, params)

    def visualize(self):
        pass

    def get_type(self):
        return OrchestratorType.PYTHON
