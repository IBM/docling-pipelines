from datasift_opensource.backend.core.orchestrator.python.python_operator_executor import PythonOperatorExecutor


class CommandLineOperatorExecutor(PythonOperatorExecutor):
    """
    Operator executor for command line orchestrator. Since the operator is loaded with
    Python, we reuse the PythonOperatorExecutor here.
    """ 

    def __init__(self, name: str, operator: str, params: dict):
        super().__init__(name, operator, params)

    