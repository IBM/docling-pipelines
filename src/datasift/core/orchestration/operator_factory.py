import importlib
import inspect
import os
import pkgutil
from typing import ClassVar

from datasift.core.constants.constants import DatasiftConstants, EnvironmentVariables, OrchestratorType
from datasift.core.operators.abstract_operator import AbstractOperator
from datasift.utils.infrastructure.logging import get_logger

logger = get_logger()


class OperatorFactoryProvider:
    operator_factories: ClassVar[dict[str, "OperatorFactory"]] = {}

    @staticmethod
    def get_operator_factory(
        *,
        orchestrator: str,
        package_names: list | None = None,
        enable_custom_operators: bool = True
    ) -> "OperatorFactory":
        """
        Get or create an operator factory with optional custom operator support.

        Parameters:
        - orchestrator: Type of orchestrator (python, spark)
        - package_names: Optional list of custom operator package paths
        - enable_custom_operators: Whether to enable custom operators (default: from env or True)

        Returns:
            OperatorFactory instance
        """
        # Check environment variable for custom operators
        env_packages = os.getenv(EnvironmentVariables.DATASIFT_CUSTOM_OPERATORS, "")
        if env_packages:
            # Validate that env_packages is a string to prevent .strip() errors
            if not isinstance(env_packages, str):
                logger.warning(
                    f"DATASIFT_CUSTOM_OPERATORS must be a string, got {type(env_packages).__name__}. "
                    "Ignoring environment variable."
                )
            else:
                env_package_list = [pkg.strip() for pkg in env_packages.split(",") if pkg.strip()]
                package_names = (package_names or []) + env_package_list

        # Create cache key including enable flag
        enable_flag = DatasiftConstants.FEATURE_ENABLED if enable_custom_operators else DatasiftConstants.FEATURE_DISABLED
        key = f"{orchestrator}_{enable_flag}_{'_'.join(package_names or [])}"
        logger.debug(f"operator_factory_key:{key}")

        if key in OperatorFactoryProvider.operator_factories:
            return OperatorFactoryProvider.operator_factories[key]

        operator_factory = OperatorFactory(
            orchestrator,
            package_names,
            enable_custom_operators=enable_custom_operators
        )
        OperatorFactoryProvider.operator_factories[key] = operator_factory
        return operator_factory

    @staticmethod
    def refresh_operator_factory(
        *,
        orchestrator: str,
        package_names: list | None = None,
        enable_custom_operators: bool = True
    ) -> "OperatorFactory":
        """
        Refreshes the operator factory by reloading custom operator classes dynamically.

        Parameters:
        - orchestrator: Type of orchestrator (python, spark)
        - package_names: Optional list of custom operator package paths
        - enable_custom_operators: Whether to enable custom operators

        Returns:
            OperatorFactory instance
        """
        enable_flag = DatasiftConstants.FEATURE_ENABLED if enable_custom_operators else DatasiftConstants.FEATURE_DISABLED
        key = f"{orchestrator}_{enable_flag}_{'_'.join(package_names or [])}"
        logger.info(f"Refreshing operator factory: {key}")

        if key in OperatorFactoryProvider.operator_factories:
            OperatorFactoryProvider.operator_factories[key].refresh_operators()
            return OperatorFactoryProvider.operator_factories[key]

        # If the factory does not exist, create a new one
        return OperatorFactoryProvider.get_operator_factory(
            orchestrator=orchestrator,
            package_names=package_names,
            enable_custom_operators=enable_custom_operators
        )


class OperatorFactory:
    """
    Factory class for loading operators from frozenset registry and custom packages.
    Supports priority-based operator resolution where lower number = higher priority.
    """

    # Priority map: lower number = higher priority
    PRIORITY_MAP: ClassVar[dict[str, int]] = {
        DatasiftConstants.OWNER_CUSTOM: 1,      # Custom operators have highest priority
        DatasiftConstants.OWNER_DATASIFT: 2,    # Base datasift operators have lower precedence
    }

    def __init__(
        self,
        orchestrator: str,
        package_names: list | None = None,
        enable_custom_operators: bool = True,
    ):
        """
        Initialize the factory with frozenset operators and optional custom packages.

        Parameters:
        - orchestrator: the operator classes for the given orchestrator will be loaded
        - package_names: list of module names for custom operators (optional)
        - enable_custom_operators: whether to load custom operators (default: from env or True)
        """
        self.orchestrator = orchestrator
        self.package_names = package_names or []
        self.operators: dict[str, type] = {}

        # Determine if custom operators are enabled
        # Priority: parameter > environment variable > default
        if enable_custom_operators is None:
            env_value = os.getenv(EnvironmentVariables.DATASIFT_ENABLE_CUSTOM_OPERATORS)
            if env_value is not None:
                enable_custom_operators = env_value.lower() in ("true", "1", "yes")
            else:
                enable_custom_operators = DatasiftConstants.ENABLE_CUSTOM_OPERATORS_DEFAULT

        self.enable_custom_operators = enable_custom_operators

        # Always load OSS operators from frozenset
        self._load_operators_from_frozenset()

        # Load custom operators ONLY if enabled
        if self.enable_custom_operators and self.package_names:
            logger.info("Custom operators ENABLED - loading from packages")
            self._load_custom_operators_from_packages()
        elif not self.enable_custom_operators:
            logger.warning("Custom operators DISABLED - only datasift operators will be available")
        else:
            logger.info("No custom operator packages specified")

    def _load_operators_from_frozenset(self):
        """Load operators from frozenset registry (OSS operators)."""
        from datasift.core.operators.operator_registry import get_datasift_operators

        logger.info(f"Loading datasift operators from frozenset for: {self.orchestrator}")
        for operator_class in get_datasift_operators():
            if operator_class.is_available():
                short_name = operator_class.short_name
                self.operators[short_name] = operator_class

        logger.info(f"Loaded {len(self.operators)} datasift operators from frozenset")

    def _load_custom_operators_from_packages(self):
        """Load custom operators from package paths with priority resolution."""
        if not self.enable_custom_operators:
            logger.warning("Attempted to load custom operators but feature is disabled")
            return

        logger.info(f"Loading custom operators from packages: {self.package_names}")
        temp_operator_dict = {}

        for package_name in self.package_names:
            self._load_classes_from_package(
                package_name=package_name,
                temp_operator_dict=temp_operator_dict
            )

        # Apply priority resolution
        self._apply_priority_resolution(temp_operator_dict=temp_operator_dict)

    def _apply_priority_resolution(self, *, temp_operator_dict: dict):
        """Apply priority resolution to select the highest priority operator for each short_name."""
        for short_name, classes in temp_operator_dict.items():
            # Filter by orchestrator type
            if self.orchestrator == OrchestratorType.SPARK:
                candidates = [cls for cls in classes if cls.__name__.startswith("Spark")]
            else:
                candidates = [cls for cls in classes if not cls.__name__.startswith("Spark")]

            if not candidates:
                candidates = classes

            # Select highest priority operator
            # None owner is treated as OWNER_CUSTOM for priority lookup
            selected_class = min(
                candidates,
                key=lambda cls: self.PRIORITY_MAP.get(
                    getattr(cls, DatasiftConstants.OWNER_ATTRIBUTE, None) or DatasiftConstants.OWNER_CUSTOM,
                    float("inf")
                )
            )

            if selected_class.is_available():
                owner = getattr(selected_class, DatasiftConstants.OWNER_ATTRIBUTE, None)
                # Check if we're overriding an existing operator
                if short_name in self.operators:
                    existing_owner = getattr(self.operators[short_name], DatasiftConstants.OWNER_ATTRIBUTE, None)
                    logger.info(
                        f"Priority resolution: {short_name} - {selected_class.__name__} "
                        f"(owner={owner or 'custom'}, priority={self.PRIORITY_MAP.get(owner or DatasiftConstants.OWNER_CUSTOM, 'unknown')}) "
                        f"overrides {self.operators[short_name].__name__} "
                        f"(owner={existing_owner or 'custom'}, priority={self.PRIORITY_MAP.get(existing_owner or DatasiftConstants.OWNER_CUSTOM, 'unknown')})"
                    )
                self.operators[short_name] = selected_class

    def refresh_operators(self):
        """Refreshes custom operators (non-core packages) with priority resolution."""
        if not self.enable_custom_operators:
            logger.warning("Cannot refresh operators: custom operators are disabled")
            return

        logger.info(f"Refreshing custom operators for: {self.orchestrator}")
        temp_operator_dict = {}

        for package_name in self.package_names:
            self._load_classes_from_package(
                package_name=package_name,
                temp_operator_dict=temp_operator_dict
            )

        # Apply priority resolution for refreshed operators
        self._apply_priority_resolution(temp_operator_dict=temp_operator_dict)

    def _load_classes_from_package(self, *, package_name, temp_operator_dict):
        """
        This is to load custom packages
        """
        package = ""
        try:
            package = importlib.import_module(package_name)
            logger.info(f"Package {package_name} in {package} found.")
        except ModuleNotFoundError:
            logger.debug(f"Package {package_name} in {package} not found, skipping.")
            return
        logger.info(f">> loading packages from {package}")
        for path, module_name, _is_pkg in pkgutil.walk_packages(package.__path__, package.__name__ + "."):
            try:
                module = importlib.import_module(module_name)
                self._process_module(
                    module=module,
                    module_name=module_name,
                    temp_operator_dict=temp_operator_dict,
                )
            except Exception as e:
                logger.warning(f"Module {module_name} in {path} not loaded due to error {e}")

    def _process_module(self, *, module, module_name, temp_operator_dict):
        from datasift.core.operators.operator_registry import get_datasift_operators

        datasift_operators = get_datasift_operators()

        for _name, cls in inspect.getmembers(module):
            if inspect.isclass(cls) and cls.__module__ == module_name:
                short_name = getattr(cls, "short_name", None)
                if short_name:
                    # Get owner attribute (None means custom operator)
                    owner = getattr(cls, DatasiftConstants.OWNER_ATTRIBUTE, None)

                    # Check if this is a custom operator (not in datasift frozenset) with datasift owner
                    if cls not in datasift_operators and owner == DatasiftConstants.OWNER_DATASIFT:
                        logger.error(
                            f"Custom operator '{cls.__name__}' (short_name='{short_name}') has incorrect owner='{owner}'. "
                            f"Custom operators should set owner='{DatasiftConstants.OWNER_CUSTOM}' or leave it as None. "
                            f"Skipping this operator."
                        )
                        continue  # Skip loading this operator

                    temp_operator_dict.setdefault(short_name, []).append(cls)

    def get_operator(self, *, operator_name: str) -> type[AbstractOperator] | None:  # | Type[AbstractSparkOperator]:
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
