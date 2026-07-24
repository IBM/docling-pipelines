import os
from typing import ClassVar

from docpipe.core.constants.constants import DocpipeConstants, EnvironmentVariables, OrchestratorType
from docpipe.core.operators.abstract_operator import AbstractOperator
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger()


class OperatorFactoryProvider:
    operator_factories: ClassVar[dict[str, "OperatorFactory"]] = {}

    @staticmethod
    def get_operator_factory(
        *, orchestrator: str, package_names: list | None = None, enable_custom_operators: bool = True
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
        env_packages = os.getenv(EnvironmentVariables.DOCPIPE_CUSTOM_OPERATORS, "")
        if env_packages:
            # Validate that env_packages is a string to prevent .strip() errors
            if not isinstance(env_packages, str):
                logger.warning(
                    f"DOCPIPE_CUSTOM_OPERATORS must be a string, got {type(env_packages).__name__}. "
                    "Ignoring environment variable."
                )
            else:
                env_package_list = [pkg.strip() for pkg in env_packages.split(",") if pkg.strip()]
                package_names = (package_names or []) + env_package_list

        # Create cache key including enable flag
        enable_flag = DocpipeConstants.FEATURE_ENABLED if enable_custom_operators else DocpipeConstants.FEATURE_DISABLED
        key = f"{orchestrator}_{enable_flag}_{'_'.join(package_names or [])}"
        logger.debug(f"operator_factory_key:{key}")

        if key in OperatorFactoryProvider.operator_factories:
            return OperatorFactoryProvider.operator_factories[key]

        operator_factory = OperatorFactory(orchestrator, package_names, enable_custom_operators=enable_custom_operators)
        OperatorFactoryProvider.operator_factories[key] = operator_factory
        return operator_factory

    @staticmethod
    def refresh_operator_factory(
        *, orchestrator: str, package_names: list | None = None, enable_custom_operators: bool = True
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
        enable_flag = DocpipeConstants.FEATURE_ENABLED if enable_custom_operators else DocpipeConstants.FEATURE_DISABLED
        key = f"{orchestrator}_{enable_flag}_{'_'.join(package_names or [])}"
        logger.info(f"Refreshing operator factory: {key}")

        if key in OperatorFactoryProvider.operator_factories:
            OperatorFactoryProvider.operator_factories[key].refresh_operators()
            return OperatorFactoryProvider.operator_factories[key]

        # If the factory does not exist, create a new one
        return OperatorFactoryProvider.get_operator_factory(
            orchestrator=orchestrator, package_names=package_names, enable_custom_operators=enable_custom_operators
        )


class OperatorFactory:
    """
    Factory class for loading operators from frozenset registry and custom packages.
    Supports priority-based operator resolution where lower number = higher priority.
    """

    # Priority map: lower number = higher priority
    PRIORITY_MAP: ClassVar[dict[str, int]] = {
        DocpipeConstants.OWNER_CUSTOM: 1,  # Custom operators have highest priority
        DocpipeConstants.OWNER_DOCPIPE: 2,  # Base docpipe operators have lower precedence
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
            env_value = os.getenv(EnvironmentVariables.DOCPIPE_ENABLE_CUSTOM_OPERATORS)
            if env_value is not None:
                enable_custom_operators = env_value.lower() in ("true", "1", "yes")
            else:
                enable_custom_operators = DocpipeConstants.ENABLE_CUSTOM_OPERATORS_DEFAULT

        self.enable_custom_operators = enable_custom_operators

        # Always load OSS operators from frozenset
        self._load_operators_from_frozenset()

        # Load custom operators ONLY if enabled
        if self.enable_custom_operators and self.package_names:
            logger.info("Custom operators ENABLED - loading from packages")
            self._load_custom_operators_from_packages()
        elif not self.enable_custom_operators:
            logger.warning("Custom operators DISABLED - only docpipe operators will be available")
        else:
            logger.info("No custom operator packages specified")

    def _load_operators_from_frozenset(self):
        """Load operators from frozenset registry (OSS operators)."""
        from docpipe.core.operators.operator_registry import get_docpipe_operators

        logger.info(f"Loading docpipe operators from frozenset for: {self.orchestrator}")
        for operator_class in get_docpipe_operators():
            if operator_class.is_available():
                short_name = operator_class.short_name
                self.operators[short_name] = operator_class

        logger.info(f"Loaded {len(self.operators)} docpipe operators from frozenset")

    def _load_custom_operators_from_packages(self, *, clear_cache: bool = False) -> dict[str, type]:
        """Load custom operators from all sources (packages, filesystem, S3) with priority resolution.

        Args:
            clear_cache: If True, clear adapter caches before loading (for refresh)

        Returns:
            Dictionary mapping operator short names to operator classes
        """
        if not self.enable_custom_operators:
            logger.warning("Attempted to load custom operators but feature is disabled")
            return {}

        logger.info(f"Loading custom operators from sources: {self.package_names}")

        try:
            # Use CustomOperatorLoader for unified loading from all sources
            from docpipe.core.orchestration.operator_loader.loader_service import CustomOperatorLoader

            # Create loader with auto-detection of source types
            loader = CustomOperatorLoader.from_paths(self.package_names)

            # Load and validate operators
            custom_operators = loader.validate_and_load(builtin_operators=self.operators, clear_cache=clear_cache)

            # Apply priority resolution between docpipe and custom operators
            self._apply_priority_resolution_with_custom(custom_operators=custom_operators)

            logger.info(f"Successfully loaded {len(custom_operators)} custom operator(s)")
            return custom_operators

        except Exception as e:
            logger.error(f"Failed to load custom operators: {e}", exc_info=True)
            return {}

    def _apply_priority_resolution_with_custom(self, *, custom_operators: dict[str, type]):
        """Apply priority resolution between docpipe and custom operators.

        Custom operators (priority 1) can override docpipe operators (priority 2).

        Args:
            custom_operators: Dictionary of custom operators (short_name -> class)
        """
        for short_name, operator_class in custom_operators.items():
            # Get owner and priority
            owner = getattr(operator_class, DocpipeConstants.OWNER_ATTRIBUTE, None) or DocpipeConstants.OWNER_CUSTOM
            priority = self.PRIORITY_MAP.get(owner, float("inf"))

            # Check if we should override existing docpipe operator
            if short_name in self.operators:
                existing_owner = getattr(self.operators[short_name], DocpipeConstants.OWNER_ATTRIBUTE, None)
                existing_priority = self.PRIORITY_MAP.get(existing_owner or DocpipeConstants.OWNER_CUSTOM, float("inf"))

                if priority <= existing_priority:
                    logger.info(
                        f"Custom operator '{short_name}' (priority={priority}) "
                        f"overrides existing operator (priority={existing_priority})"
                    )
                    self.operators[short_name] = operator_class
                else:
                    logger.warning(
                        f"Custom operator '{short_name}' (priority={priority}) "
                        f"cannot override existing operator (priority={existing_priority})"
                    )
            else:
                # No conflict, add the custom operator
                self.operators[short_name] = operator_class
                logger.debug(f"Added custom operator: {short_name}")

    def refresh_operators(self):
        """Refreshes custom operators (non-core packages) with priority resolution."""
        if not self.enable_custom_operators:
            logger.warning("Cannot refresh operators: custom operators are disabled")
            return

        logger.info(f"Refreshing custom operators for: {self.orchestrator}")

        # Use CustomOperatorLoader to reload operators from packages with cache clearing
        try:
            custom_operators = self._load_custom_operators_from_packages(clear_cache=True)
            self._apply_priority_resolution_with_custom(custom_operators=custom_operators)
            logger.info(f"Successfully refreshed {len(custom_operators)} custom operators")
        except Exception as e:
            logger.error(f"Failed to refresh custom operators: {e}")
            raise

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
