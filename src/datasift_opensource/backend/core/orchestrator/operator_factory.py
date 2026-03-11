import importlib
import inspect
import pkgutil

from common.constants.constants import OperatorConstants, OrchestratorType
from common.util.log import get_logger
from core.operators.abstract_operator import AbstractOperator

logger = get_logger()


class OperatorFactoryProvider:
    operator_factories = {}

    @staticmethod
    def get_operator_factory(*, orchestrator: str, package_names: list = OperatorConstants.Misc.ALL_OPERATORS_PATH):
        key = orchestrator + "_" + "_".join(package_names)
        logger.debug(f"000_Spark_Logger operator_factory_key:{key}")
        if key in OperatorFactoryProvider.operator_factories:
            return OperatorFactoryProvider.operator_factories[key]
        operator_factory = OperatorFactory(orchestrator, package_names)
        OperatorFactoryProvider.operator_factories[key] = operator_factory
        return operator_factory

    @staticmethod
    def refresh_operator_factory(*, orchestrator: str, package_names: list = OperatorConstants.Misc.ALL_OPERATORS_PATH):
        """
        Refreshes the operator factory by reloading the operator classes dynamically.
        """
        key = orchestrator + "_" + "_".join(package_names)
        logger.info(f"Refreshing operator factory: {key}")

        if key in OperatorFactoryProvider.operator_factories:
            OperatorFactoryProvider.operator_factories[key].refresh_operators()
            return OperatorFactoryProvider.operator_factories[key]

        # If the factory does not exist, create a new one
        return OperatorFactoryProvider.get_operator_factory(orchestrator=orchestrator, package_names=package_names)


class OperatorFactory:
    """
    Factory class for searching all operator instances in the python path under given parent package names
    and building the operator short-name to class dictionary.
    """

    def __init__(
        self,
        orchestrator: str,
        package_names: list = OperatorConstants.Misc.ALL_OPERATORS_PATH,
    ):
        """
        Initialize the factory with the given package names for the given orchestrator.
        Parameters:
        - orchestrator: the operator classes for the given orchestrator will be loaded
        - package_names: list of module names from where operators are to be loaded
        """
        self.orchestrator = orchestrator
        self.package_names = package_names
        self.operators = {}
        self._load_classes_from_packages()

    def refresh_operators(self):
        """Refreshes only the operators from package locations other than 'datasift_core.operators'."""
        logger.info(f"Refreshing non-core operators for: {self.orchestrator}")
        temp_operator_dict = {}

        for package_name in self.package_names:
            if package_name != OperatorConstants.CORE_OPERATORS_PATH:
                self._load_classes_from_package(package_name=package_name, temp_operator_dict=temp_operator_dict)

        # Update only non-core operators
        for short_name, classes in temp_operator_dict.items():
            if self.orchestrator == OrchestratorType.SPARK:
                selected_class = next(
                    (cls for cls in classes if cls.__name__.startswith("Spark")),
                    classes[0],
                )
            else:
                selected_class = next(cls for cls in classes if not cls.__name__.startswith("Spark"))
            self.operators[short_name] = selected_class

    def _load_classes_from_packages(self):
        """
        This is to load packages from datasift_core.operators
        """
        temp_operator_dict = {}
        for package_name in self.package_names:
            self._load_classes_from_package(package_name=package_name, temp_operator_dict=temp_operator_dict)

        for short_name, classes in temp_operator_dict.items():
            if self.orchestrator == OrchestratorType.SPARK:
                selected_class = next(
                    (cls for cls in classes if cls.__name__.startswith("Spark")),
                    classes[0],
                )
            else:
                selected_class = next(cls for cls in classes if not cls.__name__.startswith("Spark"))

            if selected_class.is_available():
                self.operators[short_name] = selected_class

    def _load_classes_from_package(self, *, package_name, temp_operator_dict):
        """
        This is to load custom packages
        """
        package = ""
        try:
            package = importlib.import_module(package_name)
            importlib.reload(package)
            logger.info(f"Package {package_name} in {package} found.")
        except ModuleNotFoundError:
            logger.debug(f"Package {package_name} in {package} not found, skipping.")
            return
        logger.info(f">> loading packages from {package}")
        for path, module_name, is_pkg in pkgutil.walk_packages(package.__path__, package.__name__ + "."):
            try:
                module = importlib.import_module(module_name)
                module = importlib.reload(module)
                self._process_module(
                    module=module,
                    module_name=module_name,
                    temp_operator_dict=temp_operator_dict,
                )
            except Exception as e:
                logger.warning(f"Module {module_name} in {path} not loaded due to error {e}")

    def _process_module(self, *, module, module_name, temp_operator_dict):
        for name, cls in inspect.getmembers(module):
            if inspect.isclass(cls) and cls.__module__ == module_name:
                short_name = getattr(cls, "short_name", None)
                if short_name:
                    temp_operator_dict.setdefault(short_name, []).append(cls)

    def get_operator(self, *, operator_name: str) -> type[AbstractOperator]:  # | Type[AbstractSparkOperator]:
        return self.operators.get(operator_name)


def main():  # pragma: no cover
    """
    main entry point into the program; used for unit testing only
    """
    factory = OperatorFactoryProvider.get_operator_factory(orchestrator=OrchestratorType.SPARK)
    logger.info(f"Loaded {len(factory.operators)} operators")

    for key, value in factory.operators.items():
        print(f" short_name: {key} ==> class_name: {value.__name__}")

    factory = OperatorFactoryProvider.get_operator_factory(orchestrator=OrchestratorType.PYTHON)
    logger.info(f"Loaded {len(factory.operators)} operators")

    for key, value in factory.operators.items():
        print(f" short_name: {key} ==> class_name: {value.__name__}")


# main entry point into the program; used for unit testing only
if __name__ == "__main__":  # pragma: no cover
    main()
