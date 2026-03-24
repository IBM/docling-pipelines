from core.orchestrator.abstract_orchestrator import AbstractOrchestrator
from core.orchestrator.python.python_orchestrator import PythonOrchestrator


class OrchestratorFactory:
    """
    Factory class to create an instance of an orchestrator
    """

    @staticmethod
    def create_orchestrator() -> AbstractOrchestrator:  # pragma: no cover
        """
        create an instance of the Python orchestrator
        """
        return PythonOrchestrator()
