from common.constants import OrchestratorType
from core.orchestrator.abstract_orchestrator import AbstractOrchestrator
from core.orchestrator.python.python_orchestrator import PythonOrchestrator

"""
statically defined list of available orchestrators
Additional orchestrators will be added in future
"""
orchestrators = {OrchestratorType.PYTHON: PythonOrchestrator}


class OrchestratorFactory:
    """
    Factory class to create an instance of an orchestrator
    """

    @staticmethod
    def create_orchestrator(*, orchestrator_name: str = OrchestratorType.PYTHON) -> AbstractOrchestrator:  # pragma: no cover
        """
        create an instance of the Python orchestrator
        """
        return orchestrators[orchestrator_name]()
