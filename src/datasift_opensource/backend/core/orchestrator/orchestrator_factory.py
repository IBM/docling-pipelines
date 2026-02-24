from datasift_opensource.backend.core.orchestrator.abstract_orchestrator import AbstractOrchestrator
from datasift_opensource.backend.core.orchestrator.cmdline.cmd_line_orchestrator import CommandLineOrchestrator
from datasift_opensource.backend.common.util.constants import OrchestratorType

"""
statically defined list of available orchestrators
"""
orchestrators = {
    OrchestratorType.CMDLINE: CommandLineOrchestrator
}


class OrchestratorFactory:
    """
    Factory class to create an instance of an orchestrator
    """
    @staticmethod
    def create_orchestrator(*, orchestrator_name: str) -> AbstractOrchestrator: # pragma: no cover
        """
        create an instance of the requested orchestrator
        Parameters
        - orchestrator_name: The name of the orchestrator to be created
        Returns:
        - An instance of the requested orchestrator
        """
        return orchestrators[orchestrator_name]()
