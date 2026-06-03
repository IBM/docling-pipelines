"""Factory for creating repository instances.

Provides centralized repository creation based on environment configuration.
Supports multiple repository types through the Abstract Factory pattern with
registry-based extensibility.

Architecture:
    - AbstractRepositoryType: Base enum for all repository types
    - RepositoryType: Concrete repository types (LOCAL)
    - get_available_repository_types(): Registry mapping types to implementation classes
    - create_flow_repository(): Factory method using registry pattern

Extension Pattern:
    This factory can be extended without modifying existing code by:

    1. Creating a new repository type enum:
        ```python
        class CustomRepositoryType(AbstractRepositoryType):
            CUSTOM = "custom"
        ```

    2. Creating an extended factory:
        ```python
        class ExtendedRepositoryFactory(RepositoryFactory):
            @classmethod
            def get_available_repository_types(cls):
                base_types = super().get_available_repository_types()
                return {
                    **base_types,
                    CustomRepositoryType.CUSTOM: CustomFlowRepository
                }
        ```

    3. Using the extended factory:
        ```python
        repository = ExtendedRepositoryFactory.create_flow_repository()
        ```
"""

import logging
import os
from enum import Enum
from pathlib import Path

import yaml

from datasift.core.assets.flows.adapters.repositories.local.local_flow_repository import LocalFlowRepository
from datasift.core.assets.flows.domain.ports.flow_repository import FlowRepository
from datasift.exceptions.datasift_exceptions import RepositoryConfigurationException

logger = logging.getLogger(__name__)


class AbstractRepositoryType(Enum):
    """Base enumeration for repository types.

    Empty base class that allows different implementations to define their own
    repository types without conflicts. Can be extended to add custom repository
    types in derived implementations.
    """

    pass


class RepositoryType(AbstractRepositoryType):
    """Enumeration of available repository types."""

    LOCAL = "local"


DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[5] / "datasift-config.yaml"
ENV_CONFIG_PATH_KEY = "DATASIFT_CONFIG_PATH"


class RepositoryFactory:
    """Factory for creating FlowRepository instances.

    Enables switching between repository implementations via environment
    configuration. Follows the Abstract Factory pattern for extensibility.

    Configuration precedence:
        1. Environment variables
        2. datasift-config.yaml
        3. Built-in defaults

    Environment Variables:
        FLOW_REPOSITORY_TYPE: Repository type (default: "local")
                             Valid values: "local"
        LOCAL_FLOWS_DIR: Directory for local repository storage
                        Overrides yaml/base default when set
    """

    @classmethod
    def get_available_repository_types(cls) -> dict[AbstractRepositoryType, type[FlowRepository]]:
        """Get available repository types and their implementation classes.

        Returns a mapping of repository type enums to their corresponding
        FlowRepository implementation classes. This enables dynamic repository
        instantiation and allows extended implementations to add additional
        repository types by overriding this method.

        Note:
            This is a classmethod (not staticmethod) to support inheritance.
            When a subclass overrides this method, other methods in the class
            will automatically use the subclass's version via the cls parameter.

        Returns:
            Dictionary mapping AbstractRepositoryType to FlowRepository class

        Example:
            {
                RepositoryType.LOCAL: LocalFlowRepository
            }
        """
        return {RepositoryType.LOCAL: LocalFlowRepository}

    @classmethod
    def _get_valid_types(cls) -> list[str]:
        """Get list of valid repository type values.

        Note:
            Uses cls.get_available_repository_types() instead of
            RepositoryFactory.get_available_repository_types() to ensure
            subclass overrides are respected.

        Returns:
            List of valid repository type strings from available repository types
        """
        available_types = cls.get_available_repository_types()
        return [repo_type.value for repo_type in available_types.keys()]

    @staticmethod
    def _load_yaml_config() -> dict:
        config_path = Path(os.getenv(ENV_CONFIG_PATH_KEY, str(DEFAULT_CONFIG_PATH)))
        if not config_path.exists():
            return {}

        try:
            with open(config_path) as file:
                yaml_config = yaml.safe_load(file)
        except yaml.YAMLError as exc:
            logger.warning(f"Invalid repository YAML configuration at {config_path}: {exc}")
            return {}

        return yaml_config or {}

    @staticmethod
    def _get_repository_config() -> tuple[str, dict]:
        yaml_config = RepositoryFactory._load_yaml_config()
        assets_config = yaml_config.get("assets_management", {}) or {}
        repo_config = assets_config.get("flow_repository", {}) or {}

        repo_type_str = os.getenv("FLOW_REPOSITORY_TYPE", repo_config.get("type", RepositoryType.LOCAL.value))
        resolved_config = repo_config.get("config", {}) or {}

        return repo_type_str, resolved_config

    @classmethod
    def create_flow_repository(cls) -> FlowRepository:
        """Create a flow repository based on environment configuration and datasift-config.yaml.

        Uses a registry pattern to dynamically instantiate repository implementations.
        This allows extended implementations to add additional repository types
        without modifying existing code.

        Note:
            This is a classmethod to support inheritance. When called on a subclass,
            it will use the subclass's get_available_repository_types() registry.

        Returns:
            FlowRepository: Configured repository instance

        Raises:
            RepositoryConfigurationException: If repository type is invalid
                                             or not yet implemented
        """
        repo_type_str, repository_config = cls._get_repository_config()
        available_types = cls.get_available_repository_types()
        valid_types = cls._get_valid_types()

        logger.info(f"Creating flow repository of type: '{repo_type_str}'")

        if repo_type_str.lower() not in valid_types:
            logger.info(
                f"Invalid repository type: '{repo_type_str}'. Must be one of: {', '.join(valid_types)}",
            )
            raise RepositoryConfigurationException(
                f"Invalid repository type: '{repo_type_str}'. Must be one of: {', '.join(valid_types)}",
                repository_type=repo_type_str,
                valid_types=valid_types,
            )

        # Find matching repository type enum from registry
        repository_type = None
        for repo_enum in available_types.keys():
            if repo_enum.value == repo_type_str.lower():
                repository_type = repo_enum
                break

        if not repository_type:
            raise RepositoryConfigurationException(
                f"Repository type '{repo_type_str}' not found in registry",
                repository_type=repo_type_str,
                valid_types=valid_types,
            )

        # Get repository class from registry and instantiate
        repository_class = available_types[repository_type]

        try:
            if repository_type == RepositoryType.LOCAL:
                # Filter out configs, keep only constructor parameters for local repository type
                filtered_config = {
                    k: v
                    for k, v in repository_config.items()
                    if k in ("enable_locking", "lock_timeout", "lock_retry_interval")
                }
                return repository_class(**filtered_config)

            # For other repository types, pass all configuration
            return repository_class(**repository_config)
        except TypeError as e:
            raise RepositoryConfigurationException(
                f"Failed to instantiate repository '{repository_type.value}': {e}",
                repository_type=repository_type.value,
                valid_types=valid_types,
            ) from e

    @staticmethod
    def create_default_flow_repository() -> FlowRepository:
        """Create a FlowRepository with default configuration sources."""
        logger.info("Creating default FlowRepository")
        return RepositoryFactory.create_flow_repository()
